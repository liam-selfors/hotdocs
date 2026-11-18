# hotdocs-criterion: sha256:76175e53eb91b213a987286399ebed6b6978ad1cab42c2557285d0c129dc7a1e
import json
import sys
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_TEST_INVOCATION_LOG"

DEPENDENCY_SLUGS = [
    "provenance-checker",
    "spec-bundle-assembler",
    "generator",
    "verifier-orchestrator",
    "license-scanner",
    "secret-scanner",
    "provenance-tracker",
    "provenance-writer",
    "test-author",
    "llm-endpoint",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_hit_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "generated-test",
                "result": "pass" if overall == "pass" else "fail",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": overall,
    }


HIT_LICENSE = {
    "component_id": "comp-foo",
    "gate_version": "license_scanner@4.0.0-no-reference-corpus",
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

HIT_SECRET = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


COMMON_PRELUDE = '''
import json
import os
from pathlib import Path


def _log(fn, **kw):
    with open(os.environ[LOG_ENV], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"module": MODULE, "fn": fn, "args": kw}, sort_keys=True, default=repr) + "\\n")


class _Obj:
    def __init__(self, **kw):
        self._fields = list(kw.keys())
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, k):
        if k not in self._fields:
            raise KeyError(k)
        return getattr(self, k)

    def get(self, k, default=None):
        return getattr(self, k) if k in self._fields else default

    def keys(self):
        return list(self._fields)

    def __iter__(self):
        return iter(self._fields)

    def __len__(self):
        return len(self._fields)

    def to_dict(self):
        return {k: getattr(self, k) for k in self._fields}
'''


PROVENANCE_CHECKER = '''
def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return _Obj(spec_bundle_hash="sha256:k", gate_versions={"verifier": "v@1"})


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash, gate_versions=dict(gate_versions))
    return {
        "hit": True,
        "verification_report": HIT_REPORT,
        "license_scan": HIT_LICENSE,
        "secret_scan": HIT_SECRET,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {
        "hit": False, "sealed": False, "reason": "not_sealed",
        "verification_report": None, "license_scan": None, "secret_scan": None,
        "owners": None, "source_hash": None, "written_at": None,
    }
'''

SPEC_BUNDLE_ASSEMBLER = '''
def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return _Obj(
        component_id=component_id,
        spec_bundle_hash="sha256:k",
        spec="Foo doubles a number.",
        interface="# Library",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** - a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root=None):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return _Obj(
        component_id=component_id, criterion_id=criterion_id, covers="R-FOO-001",
        criterion_text="", requirement_text="", interface="", glossary="",
        dependency_interfaces={},
    )
'''

GENERATOR = '''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", model=model, retry_feedback=retry_feedback)
    return _Obj(
        component_id="comp-foo",
        spec_bundle_hash="sha256:k",
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
'''

VERIFIER_ORCHESTRATOR = '''
GATE_VERSION = "verifier-orchestrator@2.2.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return _Obj(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        mutation_error=None,
        overall="pass",
    )
'''

LICENSE_SCANNER = '''
def gate_version(repo_root):
    _log("gate_version")
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("scan", component_id=component_id)
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

SECRET_SCANNER = '''
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
    _log("scan")
    return _result("full")


def scan_files(paths, repo_root=None):
    _log("scan_files")
    return _result("precommit")


def gate_version(repo_root):
    _log("gate_version")
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def propose(repo_root):
    _log("propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_TRACKER = '''
_COUNTER = [0]


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id, spec_bundle_hash=spec_bundle_hash)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    d = Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    _COUNTER[0] += 1
    attempt_id = "2026-01-01T00:00:00Z-" + str(_COUNTER[0])
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": None,
    }
    (d / (attempt_id.replace(":", "-") + ".json")).write_text(json.dumps(record), encoding="utf-8")
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures", component_id=component_id)
    return []
'''

PROVENANCE_WRITER = '''
def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''

TEST_AUTHOR = '''
GATE_VERSION = "generated_test@1.1.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test", model=model, seed=seed)
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_001.py", "content": "def test_x():\\n    pass\\n"},
        "model_call_error": None,
    }
'''

LLM_ENDPOINT = '''
def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}
'''

BODIES = {
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


def write_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    (comp / "component.md").write_text(
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
        "Foo doubles a number.\n",
        encoding="utf-8",
    )
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n", encoding="utf-8"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
        encoding="utf-8",
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")


def write_fakes(repo_root, hit_report):
    for slug in DEPENDENCY_SLUGS:
        module_name = slug.replace("-", "_")
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        source = (
            "MODULE = " + repr(slug) + "\n"
            + "LOG_ENV = " + repr(LOG_ENV) + "\n"
            + "HIT_REPORT = " + repr(hit_report) + "\n"
            + "HIT_LICENSE = " + repr(HIT_LICENSE) + "\n"
            + "HIT_SECRET = " + repr(HIT_SECRET) + "\n"
            + COMMON_PRELUDE
            + BODIES[slug]
        )
        (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def setup_repo(tmp_path, monkeypatch):
    def _make(overall):
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        log_path = tmp_path / "invocations.log"
        monkeypatch.setenv(LOG_ENV, str(log_path))
        for slug in DEPENDENCY_SLUGS:
            monkeypatch.delitem(sys.modules, slug.replace("-", "_"), raising=False)
        write_corpus(repo_root)
        report = make_hit_report(overall)
        write_fakes(repo_root, report)
        return repo_root, log_path, report

    return _make


def test_passing_hit_short_circuits(setup_repo):
    repo_root, log_path, report = setup_repo("pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = read_log(log_path)
    checks = [e for e in entries if e["module"] == "provenance-checker" and e["fn"] == "check_provenance"]
    assert len(checks) == 1
    assert checks[0]["args"]["spec_bundle_hash"] == "sha256:k"
    assert checks[0]["args"]["gate_versions"] == {"verifier": "v@1"}

    others = [e for e in entries if e["module"] != "provenance-checker"]
    assert others == [], "unexpected dependency calls: " + repr(others)
    checker_fns = {e["fn"] for e in entries}
    assert checker_fns <= {"current_sealed_key", "current_provenance_key", "check_provenance"}

    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False
    assert field(result, "verification") == report


def test_failed_hit_proceeds_as_miss(setup_repo):
    repo_root, log_path, report = setup_repo("fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = read_log(log_path)
    generate_calls = [e for e in entries if e["module"] == "generator" and e["fn"] == "generate"]
    assert len(generate_calls) == 1
    assert field(result, "provenance_hit") is False