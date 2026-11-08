import json

import component_gate_runner


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: ratified
owners: [acme]
sealed: true
source_path: fixtures/foo/
last_ratified_commit: 0000000000000000000000000000000000000
---

# Foo

Purpose: a fixture component for AC-GATE-001.
"""


LOG_HELPER_TEMPLATE = """import json

LOG_PATH = __LOG_PATH__


def _log(dep, fn, args):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": dep, "fn": fn, "args": args}) + "\\n")
"""


PROVENANCE_CHECKER_TEMPLATE = LOG_HELPER_TEMPLATE + """

class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("provenance-checker", "current_sealed_key", {"component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log("provenance-checker", "current_provenance_key", {"component_id": component_id})
    return ProvenanceKey("sha256:k", {"verifier": "v@1"})


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("provenance-checker", "check_provenance", {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gate_versions,
    })
    return __CHECK_RESULT__
"""


ASSEMBLER_TEMPLATE = LOG_HELPER_TEMPLATE + """

def assemble(component_id, repo_root, mode="cold"):
    _log("spec-bundle-assembler", "assemble", {"component_id": component_id, "mode": mode})
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:m",
        "spec": "",
        "interface": "",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("spec-bundle-assembler", "assemble_criterion", {
        "component_id": component_id,
        "criterion_id": criterion_id,
    })
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
    }
"""


GENERATOR_TEMPLATE = LOG_HELPER_TEMPLATE + """

def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generator", "generate", {"model": model})
    return {
        "component_id": bundle["component_id"],
        "spec_bundle_hash": bundle["spec_bundle_hash"],
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "fixture failure"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


VERIFIER_TEMPLATE = LOG_HELPER_TEMPLATE + """

GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verifier-orchestrator", "verify", {"component_id": component_id})
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "fail",
    }
"""


LICENSE_TEMPLATE = LOG_HELPER_TEMPLATE + """

def scan(component_id, repo_root):
    _log("license-scanner", "scan", {"component_id": component_id})
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0+abc",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    _log("license-scanner", "gate_version", {})
    return "license_scanner@4.0.0+abc"
"""


SECRET_TEMPLATE = LOG_HELPER_TEMPLATE + """

def scan(repo_root):
    _log("secret-scanner", "scan", {})
    return {
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


def scan_files(paths, repo_root=None):
    _log("secret-scanner", "scan_files", {})
    return {
        "scope": "precommit",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    _log("secret-scanner", "gate_version", {})
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def propose(repo_root):
    _log("secret-scanner", "propose", {})
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
"""


TRACKER_TEMPLATE = LOG_HELPER_TEMPLATE + """

def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("provenance-tracker", "check_readiness", {})
    return {
        "scope": "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("provenance-tracker", "write_attempt_record", {"component_id": component_id})
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result if isinstance(generation_result, dict) else {},
        "verification": verification_report if isinstance(verification_report, dict) else None,
    }


def last_requirement_failures(component_id, repo_root):
    _log("provenance-tracker", "last_requirement_failures", {"component_id": component_id})
    return []
"""


WRITER_TEMPLATE = LOG_HELPER_TEMPLATE + """

def write_provenance(component_id, inputs, repo_root):
    _log("provenance-writer", "write_provenance", {"component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("provenance-writer", "write_sealed_provenance", {"component_id": component_id})
    return None
"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _write_module(gen_dir, slug, module_name, content):
    path = gen_dir / slug / (module_name + ".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "components" / "foo").mkdir(parents=True)
    (repo_root / "specs" / "components" / "foo" / "component.md").write_text(COMPONENT_MD)
    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    return repo_root, log_path


def _write_fakes(repo_root, log_path, overall):
    gen_dir = repo_root / "gen"
    log_path_literal = repr(str(log_path))

    check_result = {
        "hit": True,
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": overall,
        },
        "license_scan": {
            "component_id": "comp-foo",
            "gate_version": "license_scanner@4.0.0+abc",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.1,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }

    def materialize(template, extra=None):
        src = template.replace("__LOG_PATH__", log_path_literal)
        if extra:
            for key, value in extra.items():
                src = src.replace(key, value)
        return src

    _write_module(
        gen_dir, "provenance-checker", "provenance_checker",
        materialize(PROVENANCE_CHECKER_TEMPLATE, {"__CHECK_RESULT__": repr(check_result)}),
    )
    _write_module(gen_dir, "spec-bundle-assembler", "spec_bundle_assembler", materialize(ASSEMBLER_TEMPLATE))
    _write_module(gen_dir, "generator", "generator", materialize(GENERATOR_TEMPLATE))
    _write_module(gen_dir, "verifier-orchestrator", "verifier_orchestrator", materialize(VERIFIER_TEMPLATE))
    _write_module(gen_dir, "license-scanner", "license_scanner", materialize(LICENSE_TEMPLATE))
    _write_module(gen_dir, "secret-scanner", "secret_scanner", materialize(SECRET_TEMPLATE))
    _write_module(gen_dir, "provenance-tracker", "provenance_tracker", materialize(TRACKER_TEMPLATE))
    _write_module(gen_dir, "provenance-writer", "provenance_writer", materialize(WRITER_TEMPLATE))

    return check_result


def _read_log(log_path):
    lines = log_path.read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_provenance_hit_short_circuits(tmp_path):
    repo_root, log_path = _setup_repo(tmp_path)
    check_result = _write_fakes(repo_root, log_path, overall="pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_log(log_path)
    other_dep_calls = [c for c in calls if c["dep"] != "provenance-checker"]
    assert other_dep_calls == []

    check_calls = [c for c in calls if c["dep"] == "provenance-checker" and c["fn"] == "check_provenance"]
    assert len(check_calls) == 1
    assert check_calls[0]["args"]["spec_bundle_hash"] == "sha256:k"
    assert check_calls[0]["args"]["gate_versions"] == {"verifier": "v@1"}

    assert _get(result, "provenance_hit") is True
    assert _get(result, "blocked") is False
    assert _get(result, "verification") == check_result["verification_report"]


def test_provenance_miss_proceeds_to_generation(tmp_path):
    repo_root, log_path = _setup_repo(tmp_path)
    _write_fakes(repo_root, log_path, overall="fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_log(log_path)
    generator_calls = [c for c in calls if c["dep"] == "generator" and c["fn"] == "generate"]
    assert len(generator_calls) == 1

    assert _get(result, "provenance_hit") is False