# hotdocs-criterion: sha256:ca4eae0eef0e595097e9d0072016b197a8452a739caa6c49063fdce0bdb32c89
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HELPERS = '''
def _j(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): _j(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_j(x) for x in v]
    if hasattr(v, "__fspath__"):
        return str(v)
    if callable(v):
        return {"callable": getattr(v, "__name__", repr(v))}
    if hasattr(v, "to_dict"):
        return _j(v.to_dict())
    if hasattr(v, "__dict__"):
        return {k: _j(x) for k, x in vars(v).items() if not k.startswith("_")}
    return repr(v)


def _log(fn, **kw):
    with open(LOG, "a") as f:
        f.write(json.dumps({"fn": fn, "args": _j(kw)}) + "\\n")
'''

PROVENANCE_CHECKER = '''
class _Key:
    def __init__(self):
        self.spec_bundle_hash = CONFIG["spec_bundle_hash"]
        self.spec_bundle_parts = dict(CONFIG["spec_bundle_parts"])
        self.gate_versions = dict(CONFIG["gate_versions"])
        self.assets = [{"kind": "python", "path": ".", "definition_sha256": None,
                        "adapter_sha256": "sha256:aa", "versions": {"python": "3.12.4"},
                        "lockfile_sha256": None}]
        self.drivers = []


def current_sealed_key(component_id, repo_root):
    _log("provenance_checker.current_sealed_key", component_id=component_id, repo_root=repo_root)
    return None


def current_provenance_key(component_id, repo_root):
    _log("provenance_checker.current_provenance_key", component_id=component_id, repo_root=repo_root)
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):
    _log("provenance_checker.check_provenance", component_id=component_id,
         spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions,
         repo_root=repo_root, spec_bundle_parts=spec_bundle_parts)
    return {"hit": False, "reason": CONFIG["reason"], "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("provenance_checker.check_sealed_provenance", component_id=component_id, repo_root=repo_root)
    return {"hit": False, "sealed": False, "reason": "not_sealed", "verification_report": None,
            "license_scan": None, "secret_scan": None, "owners": None,
            "source_hash": None, "written_at": None}
'''

GENERATION_LOOP = '''
RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


def fake_test_author(bundle):
    return {"model_call_error": None, "file": None}


def fake_judge(bundle):
    return {"result": "pass", "rationale": None}


def make_closures(model, seed, repo_root, llm_backend=None):
    _log("generation_loop.make_closures", model=model, seed=seed, repo_root=repo_root,
         llm_backend=llm_backend)
    return (fake_test_author, fake_judge)


def run_attempts(component_id, bundle, repo_root, model, *, mode="single", max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,
                 on_attempt=None):
    _log("generation_loop.run_attempts", component_id=component_id, bundle=bundle,
         repo_root=repo_root, model=model, mode=mode, max_attempts=max_attempts,
         retry_feedback=retry_feedback, seed=seed, llm_backend=llm_backend,
         allow_unisolated_exec=allow_unisolated_exec, on_attempt=on_attempt)
    return CONFIG["loop_result"]
'''

VERIFIER = '''
GATE_VERSION = "verifier-orchestrator@4.0.0"
DEFAULT_TEST_TIMEOUT = 300.0


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verifier_orchestrator.verify", component_id=component_id, repo_root=repo_root,
         judge=judge, test_author=test_author)
    return CONFIG["verify_report"]
'''

LICENSE = '''
def scan(component_id, repo_root):
    _log("license_scanner.scan", component_id=component_id, repo_root=repo_root)
    return CONFIG["license_result"]


def gate_version(repo_root):
    _log("license_scanner.gate_version", repo_root=repo_root)
    return "license_scanner@4.0.0-no-reference-corpus"
'''

SECRET = '''
class AllowlistInvalidError(Exception):
    pass


def scan(repo_root):
    _log("secret_scanner.scan", repo_root=repo_root)
    return CONFIG["secret_result"]


def scan_files(paths, repo_root=None):
    _log("secret_scanner.scan_files", paths=paths, repo_root=repo_root)
    return CONFIG["secret_result"]


def gate_version(repo_root):
    _log("secret_scanner.gate_version", repo_root=repo_root)
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def propose(repo_root):
    _log("secret_scanner.propose", repo_root=repo_root)
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

ASSEMBLER = '''
def assemble(component_id, repo_root, mode="cold"):
    _log("spec_bundle_assembler.assemble", component_id=component_id, repo_root=repo_root, mode=mode)
    return {"component_id": component_id, "spec_bundle_hash": "sha256:k", "spec": "s",
            "interface": "i", "constraints": "", "dependency_interfaces": {},
            "dependency_context": {}, "dependency_usage": {}, "vars": {}, "glossary": "",
            "hint_code": None, "spec_bundle_parts": {"spec": "s", "dependency_code": "d"}}


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("spec_bundle_assembler.assemble_criterion", component_id=component_id,
         criterion_id=criterion_id, repo_root=repo_root)
    return {"component_id": component_id, "criterion_id": criterion_id, "covers": "R-FOO-001",
            "criterion_text": "", "requirement_text": "", "interface": "", "glossary": "",
            "dependency_interfaces": {}, "testing": ""}
'''

WRITER = '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_provenance", component_id=component_id, inputs=inputs,
         repo_root=repo_root)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_sealed_provenance", component_id=component_id, inputs=inputs,
         repo_root=repo_root)
    return None
'''

TRACKER = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("provenance_tracker.write_attempt_record", component_id=component_id,
         generation_result=generation_result, verification_report=verification_report,
         spec_bundle_hash=spec_bundle_hash, repo_root=repo_root)
    return {"attempt_id": "2026-01-01T00:00:00Z-aaaaaa", "component_id": component_id,
            "timestamp": "2026-01-01T00:00:00Z", "spec_bundle_hash": spec_bundle_hash,
            "generation": _j(generation_result), "verification": _j(verification_report)}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("provenance_tracker.check_readiness", repo_root=repo_root)
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {},
            "secret_scan": None, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("provenance_tracker.last_requirement_failures", component_id=component_id, repo_root=repo_root)
    return []
'''

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("generation-loop", "generation_loop"): GENERATION_LOOP,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER,
    ("license-scanner", "license_scanner"): LICENSE,
    ("secret-scanner", "secret_scanner"): SECRET,
    ("spec-bundle-assembler", "spec_bundle_assembler"): ASSEMBLER,
    ("provenance-writer", "provenance_writer"): WRITER,
    ("provenance-tracker", "provenance_tracker"): TRACKER,
}


def make_report(overall):
    if overall == "pass":
        crit = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        rr = {"R-FOO-001": "pass"}
        score = 0.9
    else:
        crit = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "fail",
                "failure_detail": {"message": "x equals 1 failed", "expected": 1, "actual": 2},
                "failure_origin": "implementation"}
        rr = {"R-FOO-001": "fail"}
        score = 0.5
    return {
        "component_id": "comp-foo",
        "criteria": [crit],
        "requirement_results": rr,
        "interface_drift": False,
        "mutation_score": score,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:aa", "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "drivers": [],
        "overall": overall,
    }


def make_license(blocked):
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9 if blocked else 0.1,
        "block_threshold": 0.7,
        "blocked": blocked,
        "matches": [{"reference_id": "ref-1", "license_family": "gpl-3.0",
                     "risk_tier": "high", "score": 0.9}] if blocked else [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def make_secret(flagged):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": flagged,
        "matches": [{"rule_id": "AWS Access Key", "risk_tier": "high",
                     "file": "gen/foo/config.py", "line": 3}] if flagged else [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def make_loop_result():
    gen = {
        "component_id": "comp-foo", "spec_bundle_hash": "sha256:k", "model": "m",
        "prompt_version": "v9", "cache_hit": False, "files": {"foo.py": "x = 1\n"},
        "model_call_error": None, "refused": None, "retry_feedback": None, "mode": "single",
        "transcript_sha256": None, "turns": 1, "tool_calls": 0, "isolation": None,
    }
    return {
        "passed": True,
        "stop_reason": "passed",
        "attempts": [{"number": 1, "outcome": "passed", "retry_feedback": [],
                      "error_category": None, "surface_ok": True, "overall": "pass",
                      "failed_requirements": [], "transcript_sha256": None,
                      "reauthored_tests": []}],
        "generation_result": gen,
        "verification_report": make_report("pass"),
        "surface_report": {"ok": True, "findings": []},
    }


MANIFEST = {
    "model_pin": "m0",
    "prompt_version": "v9",
    "retry_feedback": None,
    "attempts": 2,
    "attempt_history": [{"number": 1, "outcome": "passed"}],
    "generation": {"mode": "agentic", "generator_version": "g@1", "transcript_sha256": None,
                   "turns": 4, "tool_calls": 7, "isolation": "seatbelt"},
}


def run_scenario(tmp_path, reason="environment differs", overall="pass", license_blocked=False,
                 secret_flagged=False, spec_bundle_parts=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    log.write_text("")
    config = {
        "spec_bundle_hash": "sha256:k",
        "spec_bundle_parts": spec_bundle_parts if spec_bundle_parts is not None
        else {"spec": "sha256:s0", "dependency_code": "sha256:d0"},
        "gate_versions": {"verifier": "v@1"},
        "reason": reason,
        "verify_report": make_report(overall),
        "license_result": make_license(license_blocked),
        "secret_result": make_secret(secret_flagged),
        "loop_result": make_loop_result(),
    }
    prelude = "import json\nLOG = " + repr(str(log)) + "\nCONFIG = " + repr(config) + "\n"
    for (slug, module), body in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (module + ".py")).write_text(prelude + HELPERS + body)
    manifest_dir = repo_root / "gen" / "foo"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / ".provenance.json").write_text(json.dumps(MANIFEST))

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    entries = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    return result, entries, config, repo_root


def calls(entries, fn):
    return [e for e in entries if e["fn"] == fn]


def index_of(entries, fn):
    return [i for i, e in enumerate(entries) if e["fn"] == fn]


def test_reverify_pass_writes_provenance_from_manifest(tmp_path):
    result, entries, config, repo_root = run_scenario(tmp_path)

    verifies = calls(entries, "verifier_orchestrator.verify")
    assert len(verifies) == 1
    v = verifies[0]["args"]
    assert v["component_id"] == "comp-foo"
    assert v["repo_root"] == str(repo_root)
    assert len(calls(entries, "generation_loop.make_closures")) == 1
    assert v["judge"] == {"callable": "fake_judge"}
    assert v["test_author"] == {"callable": "fake_test_author"}

    assert calls(entries, "spec_bundle_assembler.assemble") == []
    assert calls(entries, "generation_loop.run_attempts") == []
    assert calls(entries, "provenance_tracker.write_attempt_record") == []

    writes = index_of(entries, "provenance_writer.write_provenance")
    assert len(writes) == 1
    lic = index_of(entries, "license_scanner.scan")
    sec = index_of(entries, "secret_scanner.scan")
    assert lic and sec
    assert writes[0] > max(lic) and writes[0] > max(sec)

    w = entries[writes[0]]["args"]
    assert w["component_id"] == "comp-foo"
    inputs = w["inputs"]
    assert inputs["verification_report"] == config["verify_report"]
    assert inputs["license_scan_result"] == config["license_result"]
    assert inputs["secret_scan_result"] == config["secret_result"]
    assert inputs["attempts"] == 2
    assert inputs["attempt_history"] == [{"number": 1, "outcome": "passed"}]
    assert inputs["provenance_hit"] is False
    assert inputs["gate_versions"] == {"verifier": "v@1"}
    gen = inputs["generation_result"]
    assert gen["files"] == {}
    assert gen["spec_bundle_hash"] == "sha256:k"
    assert gen["model"] == "m0"
    assert gen["prompt_version"] == "v9"
    assert gen["mode"] == "agentic"
    assert gen["turns"] == 4
    assert gen["tool_calls"] == 7
    assert gen["isolation"] == "seatbelt"
    assert "generator_version" not in gen

    assert field(result, "reverified") is True
    assert field(result, "blocked") is False
    assert field(result, "provenance_hit") is False
    assert list(field(result, "attempts")) == []
    assert field(result, "verification") == config["verify_report"]


def test_secret_flag_does_not_prevent_reverification(tmp_path):
    result, entries, config, repo_root = run_scenario(tmp_path, secret_flagged=True)
    assert field(result, "reverified") is True
    assert calls(entries, "generation_loop.run_attempts") == []


def test_failed_reverification_proceeds_as_miss(tmp_path):
    result, entries, config, repo_root = run_scenario(tmp_path, overall="fail", license_blocked=True)
    cp = index_of(entries, "provenance_checker.check_provenance")
    assert len(cp) == 1
    after = [e["fn"] for e in entries[cp[0] + 1:] if e["fn"] != "generation_loop.make_closures"]
    assert after == [
        "verifier_orchestrator.verify",
        "license_scanner.scan",
        "secret_scanner.scan",
        "spec_bundle_assembler.assemble",
        "generation_loop.run_attempts",
        "license_scanner.scan",
        "secret_scanner.scan",
        "provenance_writer.write_provenance",
    ]
    writes = calls(entries, "provenance_writer.write_provenance")
    assert len(writes) == 1
    assert writes[0]["args"]["inputs"]["generation_result"] == config["loop_result"]["generation_result"]
    assert field(result, "reverified") is False


def test_dependency_code_differs_reverifies_with_parts(tmp_path):
    parts = {"spec": "s", "dependency_code": "d"}
    result, entries, config, repo_root = run_scenario(
        tmp_path, reason="dependency code differs", spec_bundle_parts=parts)
    assert field(result, "reverified") is True
    assert calls(entries, "generation_loop.run_attempts") == []
    writes = calls(entries, "provenance_writer.write_provenance")
    assert len(writes) == 1
    assert writes[0]["args"]["inputs"]["spec_bundle_parts"] == {"spec": "s", "dependency_code": "d"}


def test_other_miss_reason_does_not_reverify(tmp_path):
    result, entries, config, repo_root = run_scenario(tmp_path, reason="assets differ")
    assert calls(entries, "verifier_orchestrator.verify") == []
    assert len(calls(entries, "generation_loop.run_attempts")) == 1
    assert field(result, "reverified") is False