import json
from pathlib import Path

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


IMPACT_ANALYZER_TEMPLATE = '''\
LOG_PATH = __LOG_PATH__


def compute_blast_radius(changed_ids, repo_root):
    with open(LOG_PATH, "a") as f:
        f.write("compute_blast_radius:" + ",".join(changed_ids) + "\\n")
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None}
        ],
        "precondition_error": None,
    }
'''


PROVENANCE_CHECKER_TEMPLATE = '''\
LOG_PATH = __LOG_PATH__


def _log(name, component_id):
    with open(LOG_PATH, "a") as f:
        f.write(name + ":" + component_id + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id)
    return {
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "gate_versions": {
            "compiler": "criterion_compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier_orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    }


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id)
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": component_id,
            "gate_version": "license_scanner@4.0.3",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.70,
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


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id)
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


def test_check_readiness_reads_dict_shaped_results(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "specs" / "product").mkdir(parents=True)

    log_path = repo_root / "invocations.log"
    log_literal = json.dumps(str(log_path))

    impact_analyzer_src = IMPACT_ANALYZER_TEMPLATE.replace(
        "__LOG_PATH__", log_literal
    )
    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        impact_analyzer_src,
    )

    provenance_checker_src = PROVENANCE_CHECKER_TEMPLATE.replace(
        "__LOG_PATH__", log_literal
    )
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        provenance_checker_src,
    )

    report = provenance_tracker.check_readiness(
        repo_root, changed_ids=["comp-foo"]
    )

    assert _get(report, "scope") == "blast-radius"

    components = _get(report, "components")
    assert components is not None
    assert "comp-foo" in components

    foo_result = components["comp-foo"]
    assert _get(foo_result, "hit") is True
    verification_report = _get(foo_result, "verification_report")
    assert _get(verification_report, "overall") == "pass"
    license_scan = _get(foo_result, "license_scan")
    assert _get(license_scan, "blocked") is False
    secret_scan = _get(foo_result, "secret_scan")
    assert _get(secret_scan, "flagged") is False

    capabilities = _get(report, "capabilities", {})
    assert capabilities == {}

    assert _get(report, "ready") is True
    assert _get(report, "not_ready_reasons") == []

    assert log_path.exists()
    log_text = log_path.read_text()
    assert "compute_blast_radius:comp-foo" in log_text
    assert "current_sealed_key:comp-foo" in log_text
    assert "check_provenance:comp-foo" in log_text