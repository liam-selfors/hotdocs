import pytest

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_PROVENANCE_CHECKER_MODULE = '''
def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return {
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "gate_versions": {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
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
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": True,
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
            "cache_hit": True,
        },
    }


def check_sealed_provenance(component_id, repo_root):
    raise AssertionError(
        "check_sealed_provenance must not be called when current_sealed_key returns None"
    )
'''


_CAPABILITY_VERIFIER_TEMPLATE = '''
_OUTCOMES = __OUTCOMES__
_CHECK_LOG = __CHECK_LOG__
_GATES_LOG = __GATES_LOG__


def check_capability_provenance(capability_id, repo_root):
    with open(_CHECK_LOG, "a", encoding="utf-8") as f:
        f.write(capability_id + "\\n")
    return {"hit": False, "capability_scenario_report": None}


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    with open(_GATES_LOG, "a", encoding="utf-8") as f:
        f.write(capability_id + "\\n")
    overall = _OUTCOMES[capability_id]
    return {
        "hit": False,
        "capability_scenario_report": {
            capability_id: {
                "overall": overall,
                "scenarios": [
                    {"id": capability_id + "-001", "kind": "generated-test", "result": overall}
                ],
            }
        },
    }
'''


def _write_provenance_checker(repo_root):
    mod_dir = repo_root / "gen" / "provenance-checker"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "provenance_checker.py").write_text(_PROVENANCE_CHECKER_MODULE)


def _write_capability_verifier(repo_root, outcomes, check_log, gates_log):
    mod_dir = repo_root / "gen" / "capability-scenario-verifier"
    mod_dir.mkdir(parents=True, exist_ok=True)
    content = (
        _CAPABILITY_VERIFIER_TEMPLATE.replace("__OUTCOMES__", repr(outcomes))
        .replace("__CHECK_LOG__", repr(str(check_log)))
        .replace("__GATES_LOG__", repr(str(gates_log)))
    )
    (mod_dir / "capability_scenario_verifier.py").write_text(content)


def _write_component(repo_root, slug, comp_id, realizes_id):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        f"id: {comp_id}\n"
        f"title: {slug.capitalize()}\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "sealed: false\n"
        f"realizes: [{realizes_id}]\n"
        "---\n\n"
        f"{slug.capitalize()} component.\n"
    )


def _write_capability_spec(repo_root, name, cap_id, cs_id):
    prod_dir = repo_root / "specs" / "product"
    prod_dir.mkdir(parents=True, exist_ok=True)
    (prod_dir / f"{name}.md").write_text(
        "---\n"
        f"id: {cap_id}\n"
        f"title: {name.capitalize()} Capability\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000\n"
        "---\n\n"
        f"### {cs_id}\n\n"
        f"Covers: {cap_id}\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        f"Given {name}\n"
        f"When {name} runs\n"
        f"Then {name} passes\n"
        "```\n"
    )


def _build_two_capability_repo(tmp_path):
    repo_root = tmp_path / "repo"
    _write_component(repo_root, "alpha", "comp-alpha", "P-ALPHA")
    _write_component(repo_root, "beta", "comp-beta", "P-BETA")
    _write_capability_spec(repo_root, "p-alpha", "P-ALPHA", "CS-ALPHA-001")
    _write_capability_spec(repo_root, "p-beta", "P-BETA", "CS-BETA-001")
    _write_provenance_checker(repo_root)
    return repo_root


def _build_single_capability_repo(tmp_path):
    repo_root = tmp_path / "repo"
    _write_component(repo_root, "alpha", "comp-alpha", "P-ALPHA")
    _write_capability_spec(repo_root, "p-alpha", "P-ALPHA", "CS-ALPHA-001")
    _write_provenance_checker(repo_root)
    return repo_root


def test_all_components_and_capabilities_pass(tmp_path):
    repo_root = _build_two_capability_repo(tmp_path)
    check_log = tmp_path / "check.log"
    gates_log = tmp_path / "gates.log"
    _write_capability_verifier(
        repo_root,
        {"P-ALPHA": "pass", "P-BETA": "pass"},
        check_log,
        gates_log,
    )

    report = provenance_tracker.check_readiness(repo_root, model="test-model")

    assert _get(report, "ready") is True
    assert list(_get(report, "not_ready_reasons")) == []

    gates_called = gates_log.read_text().splitlines() if gates_log.exists() else []
    assert sorted(gates_called) == ["P-ALPHA", "P-BETA"]


def test_one_failing_capability_gate_makes_not_ready_despite_passing_components(tmp_path):
    repo_root = _build_two_capability_repo(tmp_path)
    check_log = tmp_path / "check.log"
    gates_log = tmp_path / "gates.log"
    _write_capability_verifier(
        repo_root,
        {"P-ALPHA": "pass", "P-BETA": "fail"},
        check_log,
        gates_log,
    )

    report = provenance_tracker.check_readiness(repo_root, model="test-model")

    assert _get(report, "ready") is False
    reasons = list(_get(report, "not_ready_reasons"))
    assert any("P-BETA" in reason for reason in reasons)

    components = _get(report, "components")
    for comp_id in ("comp-alpha", "comp-beta"):
        comp_result = _get(components, comp_id)
        assert _get(comp_result, "hit") is True


def test_capability_miss_with_no_model_raises_without_running_gates(tmp_path):
    repo_root = _build_single_capability_repo(tmp_path)
    check_log = tmp_path / "check.log"
    gates_log = tmp_path / "gates.log"
    _write_capability_verifier(repo_root, {}, check_log, gates_log)

    with pytest.raises(ValueError):
        provenance_tracker.check_readiness(repo_root, model=None)

    assert check_log.exists()
    assert "P-ALPHA" in check_log.read_text().splitlines()
    assert not gates_log.exists() or gates_log.read_text() == ""