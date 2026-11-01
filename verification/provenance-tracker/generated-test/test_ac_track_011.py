import json
from pathlib import Path

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_module(repo_root, dependency_slug, module_name, source):
    module_dir = repo_root / "gen" / dependency_slug
    module_dir.mkdir(parents=True, exist_ok=True)
    module_path = module_dir / f"{module_name}.py"
    module_path.write_text(source)
    return module_path


IMPACT_ANALYZER_TEMPLATE = r'''
import json

INVOCATION_LOG = __INVOCATION_LOG_PATH__
IMPACTED_IDS = __IMPACTED_IDS__


def compute_blast_radius(changed_ids, repo_root):
    with open(INVOCATION_LOG, "a") as f:
        f.write(
            json.dumps(
                {"changed_ids": list(changed_ids), "repo_root": str(repo_root)}
            )
            + "\n"
        )
    return {
        "impacted": [
            {"component_id": cid, "reason": "direct", "via": None}
            for cid in IMPACTED_IDS
        ],
        "precondition_error": None,
    }
'''

PROVENANCE_CHECKER_TEMPLATE = r'''
import json

INVOCATION_LOG = __INVOCATION_LOG_PATH__


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    with open(INVOCATION_LOG, "a") as f:
        f.write(
            json.dumps(
                {
                    "fn": "current_provenance_key",
                    "component_id": component_id,
                    "repo_root": str(repo_root),
                }
            )
            + "\n"
        )
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    with open(INVOCATION_LOG, "a") as f:
        f.write(
            json.dumps(
                {
                    "fn": "check_provenance",
                    "component_id": component_id,
                    "repo_root": str(repo_root),
                }
            )
            + "\n"
        )
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
            "gate_version": "license_scanner@3.1.0",
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
            "gate_version": "secret_scanner@2.0.0",
            "flagged": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }
'''

CAPABILITY_SCENARIO_VERIFIER_SOURCE = r'''
def check_capability_provenance(capability_id, repo_root):
    return {"hit": False, "capability_scenario_report": None}


def run_capability_gates(capability_id, repo_root, judge=None, test_author=None):
    return {"hit": False, "capability_scenario_report": None}
'''


def _setup_repo(repo_root, impacted_ids, impact_log_path, provenance_log_path):
    impact_source = IMPACT_ANALYZER_TEMPLATE.replace(
        "__INVOCATION_LOG_PATH__", repr(str(impact_log_path))
    ).replace("__IMPACTED_IDS__", repr(list(impacted_ids)))
    _write_module(repo_root, "impact-analyzer", "impact_analyzer", impact_source)

    provenance_source = PROVENANCE_CHECKER_TEMPLATE.replace(
        "__INVOCATION_LOG_PATH__", repr(str(provenance_log_path))
    )
    _write_module(repo_root, "provenance-checker", "provenance_checker", provenance_source)

    _write_module(
        repo_root,
        "capability-scenario-verifier",
        "capability_scenario_verifier",
        CAPABILITY_SCENARIO_VERIFIER_SOURCE,
    )


def test_check_readiness_resolves_impact_analyzer_per_repo_root(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()

    impact_log_a = repo_a / "impact_analyzer_invocations.log"
    impact_log_b = repo_b / "impact_analyzer_invocations.log"
    provenance_log_a = repo_a / "provenance_checker_invocations.log"
    provenance_log_b = repo_b / "provenance_checker_invocations.log"

    ids_a = ["comp-alpha-fixture", "comp-alpha2-fixture"]
    ids_b = ["comp-beta-fixture", "comp-beta2-fixture"]

    _setup_repo(repo_a, ids_a, impact_log_a, provenance_log_a)
    _setup_repo(repo_b, ids_b, impact_log_b, provenance_log_b)

    changed_ids = ["SPEC-FIXTURE-001"]

    call_sequence = [
        (repo_a, ids_a, ids_b),
        (repo_b, ids_b, ids_a),
        (repo_b, ids_b, ids_a),
        (repo_a, ids_a, ids_b),
    ]

    for repo_root, expected_ids, other_ids in call_sequence:
        result = provenance_tracker.check_readiness(
            repo_root=repo_root, changed_ids=changed_ids
        )
        components = _get(result, "components", {}) or {}
        actual_ids = set(components.keys())

        assert actual_ids == set(expected_ids), (
            f"expected components {set(expected_ids)} for repo_root {repo_root}, "
            f"got {actual_ids}"
        )
        for oid in other_ids:
            assert oid not in actual_ids, (
                f"result for repo_root {repo_root} leaked id {oid!r} from the "
                f"other repo_root's fake"
            )

    for impact_log_path, repo_root in (
        (impact_log_a, repo_a),
        (impact_log_b, repo_b),
    ):
        lines = impact_log_path.read_text().strip().splitlines()
        assert lines, f"expected at least one invocation recorded in {impact_log_path}"
        for line in lines:
            entry = json.loads(line)
            assert entry["repo_root"] == str(repo_root), (
                f"fake impact-analyzer at {impact_log_path} was invoked with "
                f"repo_root {entry['repo_root']!r}, expected {str(repo_root)!r}"
            )