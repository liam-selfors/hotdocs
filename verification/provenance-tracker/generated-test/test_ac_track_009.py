import json

import provenance_tracker


def field(obj, name):
    return obj[name] if isinstance(obj, dict) else getattr(obj, name)


def write_component(repo_root, component_id, status="draft"):
    slug = component_id[len("comp-"):]
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        "---\n"
        f"id: {component_id}\n"
        f"title: {slug.replace('-', ' ').title()}\n"
        f"status: {status}\n"
        "owners: [lselfors]\n"
        "sealed: true\n"
        f"source_path: fake_src/{slug}.py\n"
        "---\n\n"
        f"# {component_id}\n\nSynthetic fixture component for testing.\n"
    )
    (comp_dir / "component.md").write_text(frontmatter)


def write_fake_module(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(source)


def write_json(path, data):
    path.write_text(json.dumps(data))


FAKE_IMPACT_ANALYZER_SOURCE = '''
import json
import os


def compute_blast_radius(changed_ids, repo_root):
    calls_path = os.path.join(str(repo_root), "_fake_impact_calls.json")
    calls = []
    if os.path.exists(calls_path):
        with open(calls_path) as f:
            calls = json.load(f)
    calls.append(list(changed_ids))
    with open(calls_path, "w") as f:
        json.dump(calls, f)

    config_path = os.path.join(str(repo_root), "_fake_impact_config.json")
    with open(config_path) as f:
        config = json.load(f)
    return {"impacted": config["impacted"], "precondition_error": None}
'''

FAKE_PROVENANCE_CHECKER_SOURCE = '''
import json
import os


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    calls_path = os.path.join(str(repo_root), "_fake_provenance_calls.json")
    calls = []
    if os.path.exists(calls_path):
        with open(calls_path) as f:
            calls = json.load(f)
    calls.append(component_id)
    with open(calls_path, "w") as f:
        json.dump(calls, f)

    config_path = os.path.join(str(repo_root), "_fake_provenance_config.json")
    with open(config_path) as f:
        config = json.load(f)
    if component_id in config:
        return config[component_id]
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

FAKE_CAPABILITY_SCENARIO_VERIFIER_SOURCE = '''
def run_capability_gates(capability_id, repo_root, judge=None, test_author=None):
    return {"hit": True, "capability_scenario_report": {}}


def check_capability_provenance(capability_id, repo_root):
    return {"hit": True, "capability_scenario_report": {}}
'''


def hit_result(component_id, overall="pass", requirement_results=None, blocked=False, flagged=False):
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [
                {
                    "id": "AC-" + component_id[len("comp-"):].upper() + "-001",
                    "covers": "R-" + component_id[len("comp-"):].upper() + "-001",
                    "kind": "compiled",
                    "result": overall,
                }
            ],
            "requirement_results": requirement_results
            if requirement_results is not None
            else {"R-" + component_id[len("comp-"):].upper() + "-001": overall},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": overall,
        },
        "license_scan": {
            "component_id": component_id,
            "gate_version": "license_scanner@3.1.0",
            "similarity_score": 0.9 if blocked else 0.1,
            "block_threshold": 0.7,
            "blocked": blocked,
            "matches": (
                [{"reference_id": "ref-1", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.9}]
                if blocked
                else []
            ),
            "notified": blocked,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@2.0.0",
            "flagged": flagged,
            "matches": [],
            "notified": flagged,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def miss_result():
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def test_blast_radius_scope_reports_hit_and_miss_without_gate_runner(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    write_component(repo_root, "comp-changed")
    write_component(repo_root, "comp-hit")
    write_component(repo_root, "comp-miss")

    write_fake_module(repo_root, "impact-analyzer", FAKE_IMPACT_ANALYZER_SOURCE)
    write_fake_module(repo_root, "provenance-checker", FAKE_PROVENANCE_CHECKER_SOURCE)
    write_fake_module(
        repo_root, "capability-scenario-verifier", FAKE_CAPABILITY_SCENARIO_VERIFIER_SOURCE
    )

    write_json(
        repo_root / "_fake_impact_config.json",
        {
            "impacted": [
                {"component_id": "comp-hit", "reason": "direct", "via": None},
                {
                    "component_id": "comp-miss",
                    "reason": "transitive-interface",
                    "via": "comp-changed",
                },
            ]
        },
    )
    write_json(
        repo_root / "_fake_provenance_config.json",
        {
            "comp-hit": hit_result("comp-hit", overall="pass"),
            "comp-miss": miss_result(),
        },
    )

    report = provenance_tracker.check_readiness(repo_root=repo_root, changed_ids=["comp-changed"])

    assert field(report, "scope") == "blast-radius"

    components = field(report, "components")
    assert set(components.keys()) == {"comp-hit", "comp-miss"}

    not_ready_reasons = field(report, "not_ready_reasons")
    assert any("comp-miss" in reason for reason in not_ready_reasons)

    impact_calls_path = repo_root / "_fake_impact_calls.json"
    assert impact_calls_path.exists()
    with open(impact_calls_path) as f:
        impact_calls = json.load(f)
    assert impact_calls == [["comp-changed"]]

    assert not (repo_root / "gen" / "component-gate-runner").exists()


def test_whole_corpus_scope_checks_every_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    write_component(repo_root, "comp-aaa")
    write_component(repo_root, "comp-bbb")

    write_fake_module(repo_root, "provenance-checker", FAKE_PROVENANCE_CHECKER_SOURCE)
    write_fake_module(
        repo_root, "capability-scenario-verifier", FAKE_CAPABILITY_SCENARIO_VERIFIER_SOURCE
    )

    write_json(
        repo_root / "_fake_provenance_config.json",
        {
            "comp-aaa": hit_result("comp-aaa", overall="pass"),
            "comp-bbb": hit_result("comp-bbb", overall="pass"),
        },
    )

    report = provenance_tracker.check_readiness(repo_root=repo_root, changed_ids=None)

    assert field(report, "scope") == "whole-corpus"

    components = field(report, "components")
    assert set(components.keys()) == {"comp-aaa", "comp-bbb"}

    provenance_calls_path = repo_root / "_fake_provenance_calls.json"
    assert provenance_calls_path.exists()
    with open(provenance_calls_path) as f:
        provenance_calls = json.load(f)
    assert set(provenance_calls) == {"comp-aaa", "comp-bbb"}

    assert not (repo_root / "gen" / "impact-analyzer").exists()
    assert not (repo_root / "gen" / "component-gate-runner").exists()


def test_failing_verification_report_marks_not_ready_without_gate_runner(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    write_component(repo_root, "comp-failcheck")

    write_fake_module(repo_root, "provenance-checker", FAKE_PROVENANCE_CHECKER_SOURCE)
    write_fake_module(
        repo_root, "capability-scenario-verifier", FAKE_CAPABILITY_SCENARIO_VERIFIER_SOURCE
    )

    write_json(
        repo_root / "_fake_provenance_config.json",
        {
            "comp-failcheck": hit_result(
                "comp-failcheck",
                overall="fail",
                requirement_results={"R-FAILCHECK-001": "fail"},
            )
        },
    )

    report = provenance_tracker.check_readiness(repo_root=repo_root, changed_ids=None)

    components = field(report, "components")
    result = components["comp-failcheck"]
    assert field(result, "hit") is True

    assert field(report, "ready") is False

    not_ready_reasons = field(report, "not_ready_reasons")
    matching = [r for r in not_ready_reasons if "comp-failcheck" in r]
    assert matching
    assert any("R-FAILCHECK-001" in r for r in matching)

    assert not (repo_root / "gen" / "impact-analyzer").exists()
    assert not (repo_root / "gen" / "component-gate-runner").exists()


def test_blocking_license_scan_marks_not_ready_without_gate_runner(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    write_component(repo_root, "comp-blockedscan")

    write_fake_module(repo_root, "provenance-checker", FAKE_PROVENANCE_CHECKER_SOURCE)
    write_fake_module(
        repo_root, "capability-scenario-verifier", FAKE_CAPABILITY_SCENARIO_VERIFIER_SOURCE
    )

    write_json(
        repo_root / "_fake_provenance_config.json",
        {
            "comp-blockedscan": hit_result(
                "comp-blockedscan", overall="pass", blocked=True
            )
        },
    )

    report = provenance_tracker.check_readiness(repo_root=repo_root, changed_ids=None)

    components = field(report, "components")
    result = components["comp-blockedscan"]
    assert field(result, "hit") is True
    license_scan = field(result, "license_scan")
    assert field(license_scan, "blocked") is True

    assert field(report, "ready") is False

    not_ready_reasons = field(report, "not_ready_reasons")
    matching = [r for r in not_ready_reasons if "comp-blockedscan" in r]
    assert matching
    assert any(
        "license" in r.lower() or "scan" in r.lower() or "blocked" in r.lower()
        for r in matching
    )

    assert not (repo_root / "gen" / "impact-analyzer").exists()
    assert not (repo_root / "gen" / "component-gate-runner").exists()