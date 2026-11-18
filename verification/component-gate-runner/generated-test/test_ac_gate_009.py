# hotdocs-criterion: sha256:eecc8743c417a910370f462b06bbf3610a238f66e06200d028374c2760f9cf9f
import json
import os
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = '''import json
import dataclasses
from dataclasses import dataclass, field as _dc_field
from pathlib import Path


def _log(repo_root, entry):
    with open(Path(repo_root) / "fake_calls.log", "a") as fh:
        fh.write(json.dumps(entry, default=str) + "\\n")


def _cfg(repo_root):
    p = Path(repo_root) / "fake_config.json"
    if p.is_file():
        return json.loads(p.read_text())
    return {}

'''

PROVENANCE_CHECKER = PRELUDE + '''
GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log(repo_root, {"call": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log(repo_root, {"call": "current_provenance_key", "component_id": component_id})
    return ProvenanceKey("sha256:" + "0" * 64, dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(repo_root, {"call": "check_provenance", "component_id": component_id})
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log(repo_root, {"call": "check_sealed_provenance", "component_id": component_id})
    return {
        "hit": False, "sealed": False, "reason": "not_sealed",
        "verification_report": None, "license_scan": None, "secret_scan": None,
        "owners": None, "source_hash": None, "written_at": None,
    }
'''

SPEC_BUNDLE_ASSEMBLER = PRELUDE + '''
class _Mapping:
    def __getitem__(self, key):
        if key in [f.name for f in dataclasses.fields(self)]:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


@dataclass
class SpecBundle(_Mapping):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = _dc_field(default_factory=dict)
    dependency_context: dict = _dc_field(default_factory=dict)
    dependency_usage: dict = _dc_field(default_factory=dict)
    vars: dict = _dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None


@dataclass
class CriterionBundle(_Mapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = _dc_field(default_factory=dict)


def assemble(component_id, repo_root, mode="cold"):
    _log(repo_root, {"call": "assemble", "component_id": component_id, "mode": mode})
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="Foo doubles a number.",
        interface="foo(x: int) -> int",
        constraints="None.",
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log(repo_root, {"call": "assemble_criterion", "criterion_id": criterion_id})
    return CriterionBundle(
        component_id=component_id, criterion_id=criterion_id, covers="R-FOO-001",
        criterion_text="Given x = 2", requirement_text="foo(x) MUST return 2 * x",
        interface="foo(x: int) -> int", glossary="",
    )
'''

GENERATOR = PRELUDE + '''
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


@dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict
    model_call_error: object
    refused: object
    retry_feedback: object


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log(repo_root, {"call": "generate", "model": model, "retry_feedback": retry_feedback})
    cfg = _cfg(repo_root)
    component_id = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    sbh = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash")
    error = cfg.get("model_call_error")
    if error:
        return GenerationResult(
            component_id=component_id, spec_bundle_hash=sbh, model=model,
            prompt_version=PROMPT_VERSION, cache_hit=False, files={},
            model_call_error=error, refused=None, retry_feedback=retry_feedback,
        )
    return GenerationResult(
        component_id=component_id, spec_bundle_hash=sbh, model=model,
        prompt_version=PROMPT_VERSION, cache_hit=False,
        files={"foo.py": "def foo(x):\\n    return 2 * x\\n"},
        model_call_error=None, refused=None, retry_feedback=retry_feedback,
    )
'''

VERIFIER_ORCHESTRATOR = PRELUDE + '''
GATE_VERSION = "verifier-orchestrator@2.2.0"


@dataclass
class VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    mutation_error: object
    overall: str

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}


DEFAULT = {
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "overall": "pass",
}


def verify(component_id, repo_root, judge=None, test_author=None):
    _log(repo_root, {"call": "verify", "component_id": component_id})
    cfg = _cfg(repo_root)
    data = cfg.get("verify") or DEFAULT
    criteria = [dict(c) for c in data["criteria"]]
    if cfg.get("actual_as_set"):
        for c in criteria:
            fd = c.get("failure_detail")
            if isinstance(fd, dict) and "actual" in fd:
                fd = dict(fd)
                fd["actual"] = set(fd["actual"])
                c["failure_detail"] = fd
    return VerificationReport(
        component_id=component_id,
        criteria=criteria,
        requirement_results=dict(data["requirement_results"]),
        interface_drift=data["interface_drift"],
        mutation_score=data["mutation_score"],
        mutation_error=data["mutation_error"],
        overall=data["overall"],
    )
'''

LICENSE_SCANNER = PRELUDE + '''
DEFAULT = {
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


def scan(component_id, repo_root):
    _log(repo_root, {"call": "license_scan", "component_id": component_id})
    cfg = _cfg(repo_root)
    result = dict(cfg.get("license") or DEFAULT)
    result["component_id"] = component_id
    return result


def gate_version(repo_root):
    cfg = _cfg(repo_root)
    return (cfg.get("license") or DEFAULT)["gate_version"]
'''

SECRET_SCANNER = PRELUDE + '''
GATE = "secret_scanner@3.1.0+detect-secrets.1.5.0"


class AllowlistInvalidError(Exception):
    pass


@dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: object
    cache_hit: bool

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}


def _clean(scope):
    return SecretScanResult(
        scope=scope, gate_version=GATE, flagged=False, matches=[], allowed=[],
        unused_allowlist_entries=[], notified=False,
        notification_delivery_error=None, cache_hit=False,
    )


def scan(repo_root):
    _log(repo_root, {"call": "secret_scan"})
    return _clean("full")


def scan_files(paths, repo_root=None):
    if repo_root is not None:
        _log(repo_root, {"call": "secret_scan_files"})
    return _clean("precommit")


def gate_version(repo_root):
    return GATE


def propose(repo_root):
    _log(repo_root, {"call": "secret_propose"})
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_TRACKER = PRELUDE + '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log(repo_root, {"call": "write_attempt_record", "component_id": component_id})
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    d = Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.iterdir()))
    attempt_id = "2026-11-17T00:00:0" + str(n % 10) + "Z-fake" + str(n)
    record = {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": "2026-11-17T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {"component_id": component_id},
        "verification": None if verification_report is None else {"component_id": component_id},
    }
    (d / (attempt_id + ".json")).write_text(json.dumps(record))
    return record


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log(repo_root, {"call": "check_readiness"})
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log(repo_root, {"call": "last_requirement_failures"})
    return []
'''

PROVENANCE_WRITER = PRELUDE + '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log(repo_root, {"call": "write_provenance", "component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log(repo_root, {"call": "write_sealed_provenance", "component_id": component_id})
    return None
'''

TEST_AUTHOR = PRELUDE + '''
GATE_VERSION = "generated_test@1.1.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    if repo_root is not None:
        _log(repo_root, {"call": "author_test", "model": model})
    cid = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
    comp = bundle["component_id"] if isinstance(bundle, dict) else getattr(bundle, "component_id")
    return {
        "component_id": comp,
        "criterion_id": cid,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_x.py", "content": "def test_x():\\n    pass\\n"},
        "model_call_error": None,
    }
'''

LLM_ENDPOINT = PRELUDE + '''
DEFAULT_TIMEOUT_SECONDS = 600


class ModelResolutionError(Exception):
    pass


def complete(prompt, model, *, backend=None, **params):
    return {"text": "pass", "model": model, "backend": "fake", "model_call_error": None}


def parse_model(model):
    return (None, model)
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

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)


def build_repo(repo_root, config=None):
    repo_root = Path(repo_root)
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text("# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "interface" / "library.md").write_text("# Library\n\n```\nfoo(x: int) -> int\n```\n")
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source)
    if config is not None:
        (repo_root / "fake_config.json").write_text(json.dumps(config))
    return repo_root


def read_log(repo_root):
    p = Path(repo_root) / "fake_calls.log"
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def run_main(argv):
    try:
        return component_gate_runner.main(argv)
    except SystemExit as exc:  # tolerate sys.exit-style exits
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 2)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def test_json_pass_with_seed_and_retry_feedback(repo, capsys):
    build_repo(repo)
    rc = run_main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002", "--repo-root=" + str(repo),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "blocked") is False
    gen_calls = [e for e in read_log(repo) if e["call"] == "generate"]
    assert len(gen_calls) == 1
    assert gen_calls[0]["model"] == "m"
    assert gen_calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_text_pass_with_separate_flag_values(repo, capsys):
    build_repo(repo)
    rc = run_main([
        "generate", "comp-foo", "--model", "m", "--repo-root", str(repo),
        "--format", "text",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "comp-foo" in out
    assert "passed" in out
    gen_calls = [e for e in read_log(repo) if e["call"] == "generate"]
    assert len(gen_calls) == 1
    assert gen_calls[0]["model"] == "m"


def test_model_call_error_exits_1(repo, capsys):
    build_repo(repo, {"model_call_error": {"category": "empty_response", "message": "no files"}})
    rc = run_main(["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "model_call_error: empty_response: no files" in out


def test_test_authoring_failed_exits_1(repo, capsys):
    build_repo(repo, {
        "verify": {
            "criteria": [{
                "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
                "result": "fail", "failure_origin": "test",
                "failure_detail": {"message": "test authoring failed: network: dropped"},
            }],
            "requirement_results": {"R-FOO-001": "fail"},
            "interface_drift": False,
            "mutation_score": None,
            "mutation_error": None,
            "overall": "fail",
        }
    })
    rc = run_main(["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "test_authoring_failed" in out
    assert "AC-FOO-001: test authoring failed: network: dropped" in out


def test_json_converts_set_actual_to_sorted_list(repo, capsys):
    build_repo(repo, {
        "actual_as_set": True,
        "verify": {
            "criteria": [{
                "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
                "result": "fail", "failure_origin": "implementation",
                "failure_detail": {"message": "mismatch", "expected": ["a"], "actual": ["b", "a"]},
            }],
            "requirement_results": {"R-FOO-001": "fail"},
            "interface_drift": False,
            "mutation_score": 0.5,
            "mutation_error": None,
            "overall": "fail",
        },
    })
    rc = run_main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo), "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    verification = field(data, "verification")
    criteria = field(verification, "criteria")
    assert len(criteria) == 1
    assert field(field(criteria[0], "failure_detail"), "actual") == ["a", "b"]


def test_mutation_error_is_printed(repo, capsys):
    msg = "mutation baseline failed in the sandbox: pytest exited 1"
    build_repo(repo, {
        "verify": {
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": None,
            "mutation_error": msg,
            "overall": "fail",
        }
    })
    rc = run_main(["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "mutation_error: " + msg in out


def test_license_scan_not_evaluated_is_printed(repo, capsys):
    build_repo(repo, {
        "license": {
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
    })
    run_main(["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo)])
    out = capsys.readouterr().out
    assert "license_scan not evaluated: no-reference-corpus" in out


USAGE_ERRORS = [
    ("no_model", ["generate", "comp-foo", "--repo-root=<R>"]),
    ("unknown_component", ["generate", "comp-nope", "--model=m", "--repo-root=<R>"]),
    ("bad_seed", ["generate", "comp-foo", "--model=m", "--seed=x", "--repo-root=<R>"]),
    ("bad_format", ["generate", "comp-foo", "--model=m", "--format=bogus", "--repo-root=<R>"]),
    ("unknown_argument", ["generate", "comp-foo", "--model=m", "--bogus=1", "--repo-root=<R>"]),
    ("wrong_first_word", ["build", "comp-foo", "--model=m", "--repo-root=<R>"]),
    ("model_last_no_value", ["generate", "comp-foo", "--repo-root=<R>", "--model"]),
]


@pytest.mark.parametrize("name,argv", USAGE_ERRORS, ids=[n for n, _ in USAGE_ERRORS])
def test_usage_errors_exit_2_without_calling_dependencies(repo, capsys, name, argv):
    build_repo(repo)
    real_argv = [a.replace("<R>", str(repo)) for a in argv]
    rc = run_main(real_argv)
    capsys.readouterr()
    assert rc == 2
    assert read_log(repo) == []
    assert not (Path(repo) / "fake_calls.log").exists()