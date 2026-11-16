import json
import os
from pathlib import Path

import pytest

import component_gate_runner


# ---------------------------------------------------------------------------
# Fake dependency sources. Each fake logs every call it receives to a file
# under the repo root named by the HOTDOCS_FAKE_ROOT environment variable
# (falling back to the repo root derived from its own path), and reads its
# per-test behavior from a JSON config file there.
# ---------------------------------------------------------------------------

COMMON = r'''
import json
import os
from pathlib import Path


def _root():
    env = os.environ.get("HOTDOCS_FAKE_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def _log(fn, **data):
    rec = {"fn": fn}
    rec.update(data)
    with open(_root() / "fake_calls.log", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")


def _config():
    p = _root() / "fake_config.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _f(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


class _Obj:
    def __init__(self, **fields):
        self.__dict__.update(fields)

    def to_dict(self):
        out = {}
        for k, v in self.__dict__.items():
            out[k] = v.to_dict() if hasattr(v, "to_dict") else v
        return out

    def __getitem__(self, key):
        return self.__dict__[key]

    def get(self, key, default=None):
        return self.__dict__.get(key, default)
'''

GATE_VERSIONS = r'''
_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}
_HASH = "sha256:" + "ab" * 32
'''

PROVENANCE_CHECKER = COMMON + GATE_VERSIONS + r'''

def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id, repo_root=str(repo_root))
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id, repo_root=str(repo_root))
    return _Obj(spec_bundle_hash=_HASH, gate_versions=dict(_GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash, repo_root=str(repo_root))
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id, repo_root=str(repo_root))
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

SPEC_BUNDLE_ASSEMBLER = COMMON + GATE_VERSIONS + r'''

def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, repo_root=str(repo_root), mode=mode)
    return _Obj(
        component_id=component_id,
        spec_bundle_hash=_HASH,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** — a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id,
         criterion_id=criterion_id, repo_root=str(repo_root))
    return _Obj(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-001",
        criterion_text="Given x = 2 When foo(x) is called Then it returns 4",
        requirement_text="foo(x) MUST return 2 * x.",
        interface="foo(x: int) -> int",
        glossary="- **Foo** — a test term.",
        dependency_interfaces={},
    )
'''

GENERATOR = COMMON + r'''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", model=model, retry_feedback=retry_feedback,
         repo_root=str(repo_root))
    cfg = _config()
    component_id = _f(bundle, "component_id", "comp-foo")
    spec_bundle_hash = _f(bundle, "spec_bundle_hash")
    err = cfg.get("generator_error")
    if err:
        return _Obj(
            component_id=component_id,
            spec_bundle_hash=spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error=err,
            refused=None,
            retry_feedback=retry_feedback,
        )
    return _Obj(
        component_id=component_id,
        spec_bundle_hash=spec_bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\n    return 2 * x\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''

VERIFIER_ORCHESTRATOR = COMMON + r'''

GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id, repo_root=str(repo_root))
    overall = _config().get("verify_overall", "pass")
    result = "pass" if overall == "pass" else "fail"
    return _Obj(
        component_id=component_id,
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001",
             "kind": "generated-test", "result": result},
        ],
        requirement_results={"R-FOO-001": result},
        interface_drift=False,
        mutation_score=0.9,
        overall=overall,
    )
'''

LICENSE_SCANNER = COMMON + r'''


def gate_version(repo_root):
    _log("license_gate_version", repo_root=str(repo_root))
    if _config().get("license_not_evaluated"):
        return "license_scanner@4.0.0-no-reference-corpus"
    return "license_scanner@4.0.3+9f2c41ab07de"


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id, repo_root=str(repo_root))
    if _config().get("license_not_evaluated"):
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
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
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

SECRET_SCANNER = COMMON + r'''


def _clean(scope):
    return _Obj(
        scope=scope,
        gate_version="secret_scanner@0.0.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def scan(repo_root):
    _log("secret_scan", repo_root=str(repo_root))
    return _clean("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files", repo_root=str(repo_root))
    return _clean("precommit")


def gate_version(repo_root):
    _log("secret_gate_version", repo_root=str(repo_root))
    return "secret_scanner@0.0.0"


class AllowlistInvalidError(Exception):
    pass


def propose(repo_root):
    _log("secret_propose", repo_root=str(repo_root))
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_TRACKER = COMMON + r'''


def _plain(value):
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return dict(value)
    return dict(vars(value))


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash, repo_root=str(repo_root))
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    d = Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.iterdir()))
    attempt_id = "2026-11-15T00:00:0%dZ-fake%02d" % (n % 10, n)
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": _plain(generation_result),
        "verification": _plain(verification_report),
    }
    (d / (attempt_id + ".json")).write_text(json.dumps(record, default=str), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness", repo_root=str(repo_root))
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures", component_id=component_id, repo_root=str(repo_root))
    return []
'''

PROVENANCE_WRITER = COMMON + r'''


class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id, repo_root=str(repo_root))
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id, repo_root=str(repo_root))
    return None
'''

TEST_AUTHOR = COMMON + r'''


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed, repo_root=str(repo_root))
    criterion_id = _f(bundle, "criterion_id", "AC-FOO-001")
    return {
        "component_id": _f(bundle, "component_id", "comp-foo"),
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py",
                 "content": "def test_x():\n    assert True\n"},
        "model_call_error": None,
    }
'''

LLM_ENDPOINT = COMMON + r'''

DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "fake", "model_call_error": None}
'''

FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generator": GENERATOR,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-tracker": PROVENANCE_TRACKER,
    "provenance-writer": PROVENANCE_WRITER,
    "test-author": TEST_AUTHOR,
    "llm-endpoint": LLM_ENDPOINT,
}

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    for slug, source in FAKES.items():
        d = root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")
    comp_dir = root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    monkeypatch.setenv("HOTDOCS_FAKE_ROOT", str(root))
    monkeypatch.chdir(root)
    return root


def set_config(root, **cfg):
    (root / "fake_config.json").write_text(json.dumps(cfg), encoding="utf-8")


def read_calls(root):
    log = root / "fake_calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_main(argv):
    try:
        return component_gate_runner.main(argv)
    except SystemExit as exc:  # tolerate argparse-style exits
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2


def test_json_output_pass_with_equals_form_and_retry_feedback(repo_root, capsys):
    set_config(repo_root, verify_overall="pass")
    rc = run_main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002",
        "--repo-root=" + str(repo_root), "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "blocked") is False

    gen_calls = [c for c in read_calls(repo_root) if c["fn"] == "generate"]
    assert len(gen_calls) == 1
    assert gen_calls[0]["model"] == "m"
    assert gen_calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_text_output_pass_with_next_argument_form(repo_root, capsys):
    set_config(repo_root, verify_overall="pass")
    rc = run_main([
        "generate", "comp-foo", "--model", "m",
        "--repo-root", str(repo_root), "--format", "text",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "comp-foo" in out
    assert "passed" in out


def test_model_call_error_exits_one_and_prints_error(repo_root, capsys):
    set_config(
        repo_root,
        generator_error={"category": "empty_response", "message": "no files"},
    )
    rc = run_main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "model_call_error: empty_response: no files" in out


def test_license_scan_not_evaluated_is_reported(repo_root, capsys):
    set_config(repo_root, verify_overall="pass", license_not_evaluated=True)
    run_main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert "license_scan not evaluated: no-reference-corpus" in out


USAGE_CASES = [
    ["generate", "comp-foo", "--repo-root=<repo_root>"],
    ["generate", "comp-nope", "--model=m", "--repo-root=<repo_root>"],
    ["generate", "comp-foo", "--model=m", "--seed=x", "--repo-root=<repo_root>"],
    ["generate", "comp-foo", "--model=m", "--format=bogus", "--repo-root=<repo_root>"],
    ["generate", "comp-foo", "--model=m", "--bogus-flag=1", "--repo-root=<repo_root>"],
    ["build", "comp-foo", "--model=m", "--repo-root=<repo_root>"],
    ["generate", "comp-foo", "--repo-root=<repo_root>", "--model"],
]


@pytest.mark.parametrize(
    "argv_template",
    USAGE_CASES,
    ids=["no-model", "unknown-component", "bad-seed", "bad-format",
         "unknown-arg", "wrong-first-word", "flag-last-no-value"],
)
def test_usage_errors_exit_two_without_calling_dependencies(repo_root, capsys, argv_template):
    set_config(repo_root, verify_overall="pass")
    argv = [a.replace("<repo_root>", str(repo_root)) for a in argv_template]
    rc = run_main(argv)
    capsys.readouterr()
    assert rc == 2
    assert read_calls(repo_root) == []