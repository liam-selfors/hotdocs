import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_PROVENANCE_CHECKER_SRC = '''
def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return {
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "gate_versions": {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@1.0.0",
            "secret_scanner": "secret_scanner@1.0.0",
        },
    }


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
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
            "gate_version": "license_scanner@1.0.0",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@1.0.0",
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

_CAPABILITY_VERIFIER_SRC = '''
GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def check_capability_provenance(capability_id, repo_root):
    return {
        "hit": True,
        "capability_scenario_report": {
            capability_id: {"overall": "pass", "scenarios": []}
        },
    }


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    return {
        "hit": True,
        "capability_scenario_report": {
            capability_id: {"overall": "pass", "scenarios": []}
        },
    }
'''


def _impact_analyzer_src(component_id):
    return (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {\n"
        "        \"impacted\": [\n"
        "            {\"component_id\": " + repr(component_id) + ", \"reason\": \"direct\", \"via\": None}\n"
        "        ],\n"
        "        \"precondition_error\": None,\n"
        "    }\n"
    )


def _write_module(repo_root, slug, module_name, source):
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / (module_name + ".py")).write_text(source)


def _make_repo(tmp_path_factory, label, component_id):
    repo_root = tmp_path_factory.mktemp("repo_" + label)
    _write_module(
        repo_root, "impact-analyzer", "impact_analyzer",
        _impact_analyzer_src(component_id),
    )
    _write_module(
        repo_root, "provenance-checker", "provenance_checker",
        _PROVENANCE_CHECKER_SRC,
    )
    _write_module(
        repo_root, "capability-scenario-verifier", "capability_scenario_verifier",
        _CAPABILITY_VERIFIER_SRC,
    )
    return repo_root


def _assert_reflects_own_repo(result, expected_id, other_id):
    components = _get(result, "components")
    assert expected_id in components, (
        "expected component id %r missing from components: %r"
        % (expected_id, components)
    )
    assert other_id not in components, (
        "found other repo's component id %r leaked into components: %r"
        % (other_id, components)
    )
    own_entry = components[expected_id]
    assert _get(own_entry, "hit") is True
    verification_report = _get(own_entry, "verification_report")
    assert _get(verification_report, "component_id") == expected_id


def test_check_readiness_resolves_impact_analyzer_per_repo_root(tmp_path_factory):
    component_id_a = "comp-alpha-a"
    component_id_b = "comp-beta-b"
    repo_a = _make_repo(tmp_path_factory, "a", component_id_a)
    repo_b = _make_repo(tmp_path_factory, "b", component_id_b)

    result_a_first = provenance_tracker.check_readiness(
        repo_a, changed_ids=["spec-x"],
    )
    result_b_first = provenance_tracker.check_readiness(
        repo_b, changed_ids=["spec-x"],
    )
    _assert_reflects_own_repo(result_a_first, component_id_a, component_id_b)
    _assert_reflects_own_repo(result_b_first, component_id_b, component_id_a)

    # Repeat in the opposite order on the same process to catch any
    # resolution that was cached under a bare, repo_root-independent key.
    result_b_second = provenance_tracker.check_readiness(
        repo_b, changed_ids=["spec-x"],
    )
    result_a_second = provenance_tracker.check_readiness(
        repo_a, changed_ids=["spec-x"],
    )
    _assert_reflects_own_repo(result_b_second, component_id_b, component_id_a)
    _assert_reflects_own_repo(result_a_second, component_id_a, component_id_b)