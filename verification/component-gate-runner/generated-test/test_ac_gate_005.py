import json
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_RUNNER_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = '''import json
import os


def _log(fn, **kw):
    path = os.environ["GATE_RUNNER_TEST_LOG"]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(fn=fn, **kw), default=str) + "\\n")


class _Obj:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self._keys = list(kw)

    def to_dict(self):
        return {k: getattr(self, k) for k in self._keys}

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)
'''


PROVENANCE_CHECKER = PRELUDE + '''

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}

HIT = __HIT__


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id, repo_root=str(repo_root))
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id, repo_root=str(repo_root))
    return _Obj(spec_bundle_hash="sha256:abc123", gate_versions=dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id, repo_root=str(repo_root))
    if HIT:
        return {
            "hit": True,
            "verification_report": {
                "component_id": component_id,
                "criteria": [
                    {"id": "AC-FOO-001", "covers": "R-FOO-001",
                     "kind": "generated-test", "result": "pass"}
                ],
                "requirement_results": {"R-FOO-001": "pass"},
                "interface_drift": False,
                "mutation_score": 0.9,
                "overall": "pass",
            },
            "license_scan": {
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
            },
            "secret_scan": {
                "scope": "full",
                "gate_version": "secret_scanner@0.0.0",
                "flagged": False,
                "matches": [],
                "allowed": [],
                "unused_allowlist_entries": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
        }
    return {"hit": False, "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {"hit": False, "sealed": False, "reason": "not_sealed",
            "verification_report": None, "license_scan": None,
            "secret_scan": None, "owners": None, "source_hash": None,
            "written_at": None}
'''


SPEC_BUNDLE_ASSEMBLER = PRELUDE + '''

def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, repo_root=str(repo_root), mode=mode)
    return _Obj(
        component_id=component_id,
        spec_bundle_hash="sha256:abc123",
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
        criterion_text="Given x\\nWhen y\\nThen z",
        requirement_text="R-FOO-001",
        interface="foo(x: int) -> int",
        glossary="",
        dependency_interfaces={},
    )
'''


GENERATOR = PRELUDE + '''

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", model=model, repo_root=str(repo_root))
    return _Obj(
        component_id="comp-foo",
        spec_bundle_hash="sha256:abc123",
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={},
        model_call_error={"category": "rate_limit", "message": "429 from backend"},
        refused=None,
        retry_feedback=retry_feedback,
    )
'''


VERIFIER_ORCHESTRATOR = PRELUDE + '''

GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id, repo_root=str(repo_root))
    return _Obj(
        component_id=component_id,
        criteria=[],
        requirement_results={},
        interface_drift=False,
        mutation_score=None,
        overall="fail",
    )
'''


LICENSE_SCANNER = PRELUDE + '''

def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id, repo_root=str(repo_root))
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
'''


SECRET_SCANNER = PRELUDE + '''

class AllowlistInvalidError(Exception):
    pass


def gate_version(repo_root):
    return "secret_scanner@9.9.9+fake"


def _result(scope):
    return _Obj(
        scope=scope,
        gate_version="secret_scanner@9.9.9+fake",
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
    return _result("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return _result("precommit")


def propose(repo_root):
    _log("secret_propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_TRACKER = PRELUDE + '''
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    d = Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.iterdir()))
    attempt_id = "2026-11-15T00:00:0%dZ-aaa" % n
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-15T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {"component_id": component_id},
        "verification": None,
    }
    (d / (attempt_id + ".json")).write_text(json.dumps(record), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures")
    return []
'''


PROVENANCE_WRITER = PRELUDE + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''


TEST_AUTHOR = PRELUDE + '''

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model)
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": {"category": "network", "message": "fake"},
    }
'''


LLM_ENDPOINT = PRELUDE + '''

DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "fake", "model_call_error": None}
'''


def _write(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{module_name}.py").write_text(source, encoding="utf-8")


def _build_repo(tmp_path, hit):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
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
        "Foo doubles a number.\n",
        encoding="utf-8",
    )
    _write(repo_root, "provenance-checker",
           PROVENANCE_CHECKER.replace("__HIT__", "True" if hit else "False"))
    _write(repo_root, "spec-bundle-assembler", SPEC_BUNDLE_ASSEMBLER)
    _write(repo_root, "generator", GENERATOR)
    _write(repo_root, "verifier-orchestrator", VERIFIER_ORCHESTRATOR)
    _write(repo_root, "license-scanner", LICENSE_SCANNER)
    _write(repo_root, "secret-scanner", SECRET_SCANNER)
    _write(repo_root, "provenance-tracker", PROVENANCE_TRACKER)
    _write(repo_root, "provenance-writer", PROVENANCE_WRITER)
    _write(repo_root, "test-author", TEST_AUTHOR)
    _write(repo_root, "llm-endpoint", LLM_ENDPOINT)
    return repo_root


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / "invocations.log"
    monkeypatch.setenv(LOG_ENV, str(path))
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    return path


def test_miss_with_model_call_error_runs_both_scanners(tmp_path, log_path):
    repo_root = _build_repo(tmp_path, hit=False)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "fake-model", seed=0
    )

    log = _read_log(log_path)
    license_calls = [r for r in log if r["fn"] == "license_scan"]
    secret_calls = [r for r in log if r["fn"] == "secret_scan"]

    assert len(license_calls) == 1, log
    assert license_calls[0]["component_id"] == "comp-foo"
    assert Path(license_calls[0]["repo_root"]).resolve() == repo_root.resolve()

    assert len(secret_calls) == 1, log
    assert Path(secret_calls[0]["repo_root"]).resolve() == repo_root.resolve()

    # The generation outcome really was a model_call_error on a miss.
    assert field(result, "provenance_hit") is False
    assert field(result, "block_reason") == "model_call_error"

    license_scan = field(result, "license_scan")
    secret_scan = field(result, "secret_scan")
    assert license_scan is not None
    assert secret_scan is not None
    assert field(license_scan, "component_id") == "comp-foo"
    assert field(license_scan, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"
    assert field(license_scan, "reason") == "no-reference-corpus"
    assert field(secret_scan, "gate_version") == "secret_scanner@9.9.9+fake"
    assert field(secret_scan, "scope") == "full"
    assert field(secret_scan, "flagged") is False


def test_short_circuiting_hit_calls_neither_scanner(tmp_path, log_path):
    repo_root = _build_repo(tmp_path, hit=True)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "fake-model", seed=0
    )

    log = _read_log(log_path)
    scanner_calls = [r for r in log if r["fn"] in ("license_scan", "secret_scan", "secret_scan_files")]
    assert scanner_calls == [], log

    assert field(result, "provenance_hit") is True