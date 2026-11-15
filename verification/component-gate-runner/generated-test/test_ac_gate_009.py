import json
import os
import textwrap
from pathlib import Path

import pytest

import component_gate_runner


# ---------------------------------------------------------------------------
# Fake dependency modules (flat-module shape under <repo_root>/gen/<slug>/)
# ---------------------------------------------------------------------------

_COMMON = textwrap.dedent(
    '''
    import json
    import os


    def _log(fn, **kw):
        path = os.environ.get("GATE_FAKE_LOG")
        if not path:
            return
        record = {"fn": fn}
        record.update(kw)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\\n")


    class _Obj:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

        def to_dict(self):
            return dict(self.__dict__)

        def __getitem__(self, key):
            return self.__dict__[key]

        def get(self, key, default=None):
            return self.__dict__.get(key, default)

        def keys(self):
            return self.__dict__.keys()

        def __iter__(self):
            return iter(self.__dict__)

        def __len__(self):
            return len(self.__dict__)
    '''
)

_FAKES = {
    "provenance-checker": textwrap.dedent(
        '''
        def current_sealed_key(component_id, repo_root):
            _log("current_sealed_key", component_id=component_id)
            return None


        def current_provenance_key(component_id, repo_root):
            _log("current_provenance_key", component_id=component_id)
            return _Obj(
                spec_bundle_hash="sha256:" + "a" * 64,
                gate_versions={
                    "compiler": "criterion-compiler@1.0.0",
                    "generated_test": "generated_test@1.0.0",
                    "verifier": "verifier-orchestrator@2.0.0",
                    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
                    "secret_scanner": "secret_scanner@0.0.0",
                },
            )


        def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
            _log("check_provenance", component_id=component_id)
            return {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            }


        def check_sealed_provenance(component_id, repo_root):
            _log("check_sealed_provenance", component_id=component_id)
            return {
                "hit": False,
                "sealed": False,
                "reason": "not_sealed",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
                "owners": None,
                "source_hash": None,
                "written_at": None,
            }
        '''
    ),
    "spec-bundle-assembler": textwrap.dedent(
        '''
        def assemble(component_id, repo_root, mode="cold"):
            _log("assemble", component_id=component_id, mode=mode)
            return _Obj(
                component_id=component_id,
                spec_bundle_hash="sha256:" + "a" * 64,
                spec="Foo doubles a number.",
                interface="foo(x: int) -> int",
                constraints="None.",
                dependency_interfaces={},
                dependency_context={},
                dependency_usage={},
                vars={},
                glossary="",
                hint_code=None,
            )


        def assemble_criterion(component_id, criterion_id, repo_root):
            _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
            return _Obj(
                component_id=component_id,
                criterion_id=criterion_id,
                covers="R-FOO-001",
                criterion_text="Given x = 2 When foo(x) is called Then it returns 4",
                requirement_text="foo(x) MUST return 2 * x.",
                interface="foo(x: int) -> int",
                glossary="",
                dependency_interfaces={},
            )
        '''
    ),
    "generator": textwrap.dedent(
        '''
        GATE_VERSION = "generator@2.0.0"
        PROMPT_VERSION = "v10"


        def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
            _log("generate", model=model, retry_feedback=retry_feedback)
            mode = os.environ.get("GATE_FAKE_GEN_MODE", "files")
            if mode == "error":
                return _Obj(
                    component_id="comp-foo",
                    spec_bundle_hash="sha256:" + "a" * 64,
                    model=model,
                    prompt_version=PROMPT_VERSION,
                    cache_hit=False,
                    files={},
                    model_call_error={"category": "empty_response", "message": "no files"},
                    refused=None,
                    retry_feedback=retry_feedback,
                )
            return _Obj(
                component_id="comp-foo",
                spec_bundle_hash="sha256:" + "a" * 64,
                model=model,
                prompt_version=PROMPT_VERSION,
                cache_hit=False,
                files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
                model_call_error=None,
                refused=None,
                retry_feedback=retry_feedback,
            )
        '''
    ),
    "verifier-orchestrator": textwrap.dedent(
        '''
        GATE_VERSION = "verifier-orchestrator@2.0.0"


        def verify(component_id, repo_root, judge=None, test_author=None):
            _log("verify", component_id=component_id)
            return _Obj(
                component_id=component_id,
                criteria=[
                    {"id": "AC-FOO-001", "covers": "R-FOO-001",
                     "kind": "generated-test", "result": "pass"},
                ],
                requirement_results={"R-FOO-001": "pass"},
                interface_drift=False,
                mutation_score=0.9,
                overall="pass",
            )
        '''
    ),
    "license-scanner": textwrap.dedent(
        '''
        def gate_version(repo_root):
            _log("license_gate_version")
            if os.environ.get("GATE_FAKE_LICENSE_MODE", "evaluated") == "noref":
                return "license_scanner@4.0.0-no-reference-corpus"
            return "license_scanner@4.0.1+abcdefabcdef"


        def scan(component_id, repo_root):
            _log("license_scan", component_id=component_id)
            if os.environ.get("GATE_FAKE_LICENSE_MODE", "evaluated") == "noref":
                return {
                    "component_id": component_id,
                    "gate_version": "license_scanner@4.0.0-no-reference-corpus",
                    "evaluated": False,
                    "reason": "no-reference-corpus",
                    "similarity_score": None,
                    "block_threshold": None,
                    "blocked": False,
                    "matches": [],
                    "notified": False,
                    "notification_delivery_error": None,
                    "cache_hit": False,
                }
            return {
                "component_id": component_id,
                "gate_version": "license_scanner@4.0.1+abcdefabcdef",
                "evaluated": True,
                "reason": None,
                "similarity_score": 0.1,
                "block_threshold": 0.7,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }
        '''
    ),
    "secret-scanner": textwrap.dedent(
        '''
        def _result(scope):
            return _Obj(
                scope=scope,
                gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
                flagged=False,
                matches=[],
                allowed=[],
                unused_allowlist_entries=[],
                notified=False,
                notification_delivery_error=None,
                cache_hit=False,
            )


        def scan(repo_root):
            _log("secret_scan")
            return _result("full")


        def scan_files(paths, repo_root=None):
            _log("secret_scan_files")
            return _result("precommit")


        def gate_version(repo_root):
            _log("secret_gate_version")
            return "secret_scanner@3.1.0+detect-secrets.1.5.0"


        def propose(repo_root):
            _log("secret_propose")
            return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
        '''
    ),
    "provenance-tracker": textwrap.dedent(
        '''
        from pathlib import Path


        def write_attempt_record(component_id, generation_result, verification_report,
                                 spec_bundle_hash, repo_root):
            _log("write_attempt_record", component_id=component_id)
            slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
            d = Path(repo_root) / ".hotdocs" / "attempts" / slug
            d.mkdir(parents=True, exist_ok=True)
            existing = len(list(d.iterdir()))
            attempt_id = "2026-11-15T00:00:00Z-%06d" % existing
            record = {
                "attempt_id": attempt_id,
                "component_id": component_id,
                "timestamp": "2026-11-15T00:00:00Z",
                "spec_bundle_hash": spec_bundle_hash,
                "generation": {},
                "verification": None,
            }
            (d / (attempt_id.replace(":", "-") + ".json")).write_text(
                json.dumps(record), encoding="utf-8")
            return record


        def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
            _log("check_readiness")
            return {"scope": "whole-corpus", "ready": True, "components": {},
                    "capabilities": {}, "not_ready_reasons": []}


        def last_requirement_failures(component_id, repo_root):
            _log("last_requirement_failures", component_id=component_id)
            return []
        '''
    ),
    "provenance-writer": textwrap.dedent(
        '''
        class InvalidSealedInputError(Exception):
            pass


        def write_provenance(component_id, inputs, repo_root):
            _log("write_provenance", component_id=component_id)
            return None


        def write_sealed_provenance(component_id, inputs, repo_root):
            _log("write_sealed_provenance", component_id=component_id)
            return None
        '''
    ),
    "test-author": textwrap.dedent(
        '''
        def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
            _log("author_test", model=model, seed=seed)
            return {
                "component_id": "comp-foo",
                "criterion_id": "AC-FOO-001",
                "model": model,
                "seed": seed,
                "prompt_version": "v1",
                "cache_hit": False,
                "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py",
                         "content": "def test_x():\\n    assert True\\n"},
                "model_call_error": None,
            }
        '''
    ),
    "llm-endpoint": textwrap.dedent(
        '''
        def complete(prompt, model, *, backend=None, **params):
            _log("complete", model=model)
            return {"text": "pass", "model": model, "backend": "fake",
                    "model_call_error": None}
        '''
    ),
}

_COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)


def _write_fakes(repo_root: Path) -> None:
    for slug, body in _FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(_COMMON + "\n" + body, encoding="utf-8")


def _write_spec(repo_root: Path) -> None:
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(_COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n", encoding="utf-8")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
        encoding="utf-8")
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8")
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fakes(repo_root)
    _write_spec(repo_root)
    log_path = tmp_path / "fake_calls.log"
    monkeypatch.setenv("GATE_FAKE_LOG", str(log_path))
    monkeypatch.setenv("GATE_FAKE_GEN_MODE", "files")
    monkeypatch.setenv("GATE_FAKE_LICENSE_MODE", "evaluated")
    monkeypatch.chdir(repo_root)
    return repo_root, log_path


def _calls(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

def test_json_output_equals_form_and_retry_feedback_split(repo, capsys):
    repo_root, log_path = repo
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002", f"--repo-root={repo_root}",
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["blocked"] is False

    gen_calls = [c for c in _calls(log_path) if c["fn"] == "generate"]
    assert len(gen_calls) == 1
    assert gen_calls[0]["model"] == "m"
    assert gen_calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_text_output_next_argument_form(repo, capsys):
    repo_root, _ = repo
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model", "m", "--repo-root",
        str(repo_root), "--format", "text",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "comp-foo" in out
    assert "passed" in out


def test_model_call_error_exits_1(repo, capsys, monkeypatch):
    repo_root, _ = repo
    monkeypatch.setenv("GATE_FAKE_GEN_MODE", "error")
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", f"--repo-root={repo_root}",
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "model_call_error: empty_response: no files" in out


def test_license_scan_not_evaluated_text(repo, capsys, monkeypatch):
    repo_root, _ = repo
    monkeypatch.setenv("GATE_FAKE_LICENSE_MODE", "noref")
    component_gate_runner.main([
        "generate", "comp-foo", "--model=m", f"--repo-root={repo_root}",
    ])
    out = capsys.readouterr().out
    assert "license_scan not evaluated: no-reference-corpus" in out


@pytest.mark.parametrize(
    "make_argv",
    [
        pytest.param(lambda r: ["generate", "comp-foo", f"--repo-root={r}"], id="no-model"),
        pytest.param(lambda r: ["generate", "comp-nope", "--model=m", f"--repo-root={r}"],
                     id="unknown-component"),
        pytest.param(lambda r: ["generate", "comp-foo", "--model=m", "--seed=x",
                                f"--repo-root={r}"], id="non-integer-seed"),
        pytest.param(lambda r: ["generate", "comp-foo", "--model=m", "--format=bogus",
                                f"--repo-root={r}"], id="bad-format"),
        pytest.param(lambda r: ["generate", "comp-foo", "--model=m", "--bogus-flag",
                                f"--repo-root={r}"], id="unknown-argument"),
        pytest.param(lambda r: ["build", "comp-foo", "--model=m"], id="wrong-first-word"),
        pytest.param(lambda r: ["generate", "comp-foo", f"--repo-root={r}", "--model"],
                     id="flag-last-no-value"),
    ],
)
def test_usage_errors_exit_2_without_calling_dependencies(repo, capsys, make_argv):
    repo_root, log_path = repo
    argv = make_argv(str(repo_root))
    rc = component_gate_runner.main(argv)
    capsys.readouterr()
    assert rc == 2
    assert _calls(log_path) == []