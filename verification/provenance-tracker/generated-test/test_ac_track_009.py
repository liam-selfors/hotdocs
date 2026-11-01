import json
from pathlib import Path

import provenance_tracker

OWNER_EMAIL = "lselfors@gmail.com"

FRONTMATTER = """---
id: {component_id}
title: {title}
status: draft
owners: [{owner}]
sealed: true
source_path: tools/legacy/{slug}.py
---

# {title}

Fixture component for AC-TRACK-009 testing.
"""

PROVENANCE_CHECKER_TEMPLATE = """
import json

_CONFIG_PATH = "CONFIG_PATH_PLACEHOLDER"
_CALLS_LOG = "CALLS_LOG_PLACEHOLDER"


def _load_config():
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _log_call(record):
    with open(_CALLS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\\n")


def current_provenance_key(component_id, repo_root):
    config = _load_config()
    entry = config["key"]
    _log_call({"fn": "current_provenance_key", "component_id": component_id})
    return {
        "spec_bundle_hash": entry["spec_bundle_hash"],
        "gate_versions": entry["gate_versions"],
    }


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    config = _load_config()
    entry = config["components"][component_id]
    _log_call({
        "fn": "check_provenance",
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gate_versions,
    })
    return {
        "hit": entry["hit"],
        "verification_report": entry.get("verification_report"),
        "license_scan": entry.get("license_scan"),
        "secret_scan": entry.get("secret_scan"),
    }
"""

IMPACT_ANALYZER_TEMPLATE = """
import json

_CALLS_LOG = "CALLS_LOG_PLACEHOLDER"
_IMPACTED = IMPACTED_PLACEHOLDER


def _log_call(record):
    with open(_CALLS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\\n")


def compute_blast_radius(changed_ids, repo_root):
    _log_call({"fn": "compute_blast_radius", "changed_ids": list(changed_ids)})
    return {"impacted": _IMPACTED, "precondition_error": None}
"""

GATE_RUNNER_TEMPLATE = """
import json

_CALLS_LOG = "CALLS_LOG_PLACEHOLDER"


def _log_call(record):
    with open(_CALLS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\\n")


def __getattr__(name):
    def _call(*args, **kwargs):
        _log_call({"fn": name})
        return {}
    return _call
"""

CAPABILITY_VERIFIER_TEMPLATE = """
def __getattr__(name):
    def _call(*args, **kwargs):
        return {}
    return _call
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _keys(mapping):
    if isinstance(mapping, dict):
        return set(mapping.keys())
    return set(vars(mapping).keys())


def _write_module(gen_dir: Path, dependency_slug: str, module_name: str, source: str) -> None:
    _write(gen_dir / dependency_slug / f"{module_name}.py", source)


def _write_component(repo_root: Path, slug: str, requirement_ids: list) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    component_id = f"comp-{slug}"
    _write(
        comp_dir / "component.md",
        FRONTMATTER.format(component_id=component_id, title=slug.title(), owner=OWNER_EMAIL, slug=slug),
    )
    for requirement_id in requirement_ids:
        _write(
            comp_dir / "requirements" / f"{requirement_id}.md",
            f"**{requirement_id}** -- MUST do the fixture thing for {component_id}.\n",
        )
        ac_id = "AC-" + requirement_id.split("-", 1)[1]
        _write(
            comp_dir / "acceptance" / f"{ac_id}.md",
            f"# {ac_id}\n\nCovers: {requirement_id}\n\n"
            f"Given the fixture precondition\n"
            f"When the fixture action runs\n"
            f"Then the fixture outcome holds\n",
        )


def _setup_provenance_checker(gen_dir: Path, config_path: Path, calls_log: Path, config: dict) -> None:
    _write(config_path, json.dumps(config))
    source = PROVENANCE_CHECKER_TEMPLATE.replace("CONFIG_PATH_PLACEHOLDER", str(config_path)).replace(
        "CALLS_LOG_PLACEHOLDER", str(calls_log)
    )
    _write_module(gen_dir, "provenance-checker", "provenance_checker", source)


def _setup_repo(tmp_path: Path, components: list, provenance_config: dict, impacted=None):
    repo_root = tmp_path / "repo"
    gen_dir = repo_root / "gen"

    for slug, requirement_ids in components:
        _write_component(repo_root, slug, requirement_ids)

    provenance_calls_log = tmp_path / "provenance_calls.log"
    provenance_config_path = tmp_path / "provenance_config.json"
    _setup_provenance_checker(gen_dir, provenance_config_path, provenance_calls_log, provenance_config)

    gate_runner_calls_log = tmp_path / "gate_runner_calls.log"
    _write_module(
        gen_dir,
        "component-gate-runner",
        "component_gate_runner",
        GATE_RUNNER_TEMPLATE.replace("CALLS_LOG_PLACEHOLDER", str(gate_runner_calls_log)),
    )

    _write_module(
        gen_dir,
        "capability-scenario-verifier",
        "capability_scenario_verifier",
        CAPABILITY_VERIFIER_TEMPLATE,
    )

    if impacted is not None:
        impact_calls_log = tmp_path / "impact_calls.log"
        source = IMPACT_ANALYZER_TEMPLATE.replace("CALLS_LOG_PLACEHOLDER", str(impact_calls_log)).replace(
            "IMPACTED_PLACEHOLDER", repr(impacted)
        )
        _write_module(gen_dir, "impact-analyzer", "impact_analyzer", source)

    return repo_root, provenance_calls_log, gate_runner_calls_log


def _read_calls(log_path: Path):
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _assert_no_calls(log_path: Path) -> None:
    if log_path.exists():
        assert log_path.read_text(encoding="utf-8") == ""


def _passing_verification_report(component_id: str, requirement_id: str) -> dict:
    ac_id = "AC-" + requirement_id.split("-", 1)[1]
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac_id, "covers": requirement_id, "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {requirement_id: "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }


def _clean_license_scan(component_id: str) -> dict:
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _blocked_license_scan(component_id: str) -> dict:
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.95,
        "block_threshold": 0.70,
        "blocked": True,
        "matches": [
            {"reference_id": "ref-123", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.95}
        ],
        "notified": True,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _clean_secret_scan() -> dict:
    return {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def test_blast_radius_scope_reports_two_components_and_skips_gate_runner(tmp_path):
    provenance_config = {
        "key": {"spec_bundle_hash": "sha256:" + "a" * 8, "gate_versions": {"verifier": "v@1"}},
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _passing_verification_report("comp-foo", "R-FOO-001"),
                "license_scan": _clean_license_scan("comp-foo"),
                "secret_scan": _clean_secret_scan(),
            },
            "comp-bar": {"hit": False},
        },
    }
    impacted = [
        {"component_id": "comp-foo", "reason": "direct", "via": None},
        {"component_id": "comp-bar", "reason": "transitive-interface", "via": "comp-foo"},
    ]
    repo_root, _, gate_log = _setup_repo(
        tmp_path,
        components=[("foo", ["R-FOO-001"]), ("bar", ["R-BAR-001"])],
        provenance_config=provenance_config,
        impacted=impacted,
    )

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-foo"])

    assert _get(report, "scope") == "blast-radius"
    components_map = _get(report, "components")
    assert _keys(components_map) == {"comp-foo", "comp-bar"}

    reasons = _get(report, "not_ready_reasons")
    assert any("comp-bar" in reason for reason in reasons)

    _assert_no_calls(gate_log)


def test_no_changed_ids_checks_whole_corpus(tmp_path):
    provenance_config = {
        "key": {"spec_bundle_hash": "sha256:" + "b" * 8, "gate_versions": {"verifier": "v@1"}},
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _passing_verification_report("comp-foo", "R-FOO-001"),
                "license_scan": _clean_license_scan("comp-foo"),
                "secret_scan": _clean_secret_scan(),
            },
            "comp-bar": {
                "hit": True,
                "verification_report": _passing_verification_report("comp-bar", "R-BAR-001"),
                "license_scan": _clean_license_scan("comp-bar"),
                "secret_scan": _clean_secret_scan(),
            },
        },
    }
    repo_root, calls_log, gate_log = _setup_repo(
        tmp_path,
        components=[("foo", ["R-FOO-001"]), ("bar", ["R-BAR-001"])],
        provenance_config=provenance_config,
    )

    report = provenance_tracker.check_readiness(repo_root)

    assert _get(report, "scope") == "whole-corpus"

    calls = _read_calls(calls_log)
    checked_ids = {call["component_id"] for call in calls if call["fn"] == "check_provenance"}
    assert checked_ids == {"comp-foo", "comp-bar"}

    _assert_no_calls(gate_log)


def test_failing_verification_report_marks_component_not_ready(tmp_path):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "boom", "expected": 1, "actual": 2},
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.5,
        "overall": "fail",
    }
    provenance_config = {
        "key": {"spec_bundle_hash": "sha256:" + "c" * 8, "gate_versions": {"verifier": "v@1"}},
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report,
                "license_scan": _clean_license_scan("comp-foo"),
                "secret_scan": _clean_secret_scan(),
            },
        },
    }
    repo_root, _, gate_log = _setup_repo(
        tmp_path,
        components=[("foo", ["R-FOO-001", "R-FOO-002"])],
        provenance_config=provenance_config,
    )

    report = provenance_tracker.check_readiness(repo_root)

    reasons = _get(report, "not_ready_reasons")
    matching = [r for r in reasons if "comp-foo" in r and "verification" in r and "R-FOO-002" in r]
    assert matching

    _assert_no_calls(gate_log)


def test_blocked_license_scan_marks_component_not_ready(tmp_path):
    provenance_config = {
        "key": {"spec_bundle_hash": "sha256:" + "d" * 8, "gate_versions": {"verifier": "v@1"}},
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _passing_verification_report("comp-foo", "R-FOO-001"),
                "license_scan": _blocked_license_scan("comp-foo"),
                "secret_scan": _clean_secret_scan(),
            },
        },
    }
    repo_root, _, gate_log = _setup_repo(
        tmp_path,
        components=[("foo", ["R-FOO-001"])],
        provenance_config=provenance_config,
    )

    report = provenance_tracker.check_readiness(repo_root)

    reasons = _get(report, "not_ready_reasons")
    matching = [r for r in reasons if "comp-foo" in r and "license_scan" in r]
    assert matching

    _assert_no_calls(gate_log)


def test_check_provenance_receives_key_unchanged_for_every_component(tmp_path):
    provenance_config = {
        "key": {"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}},
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _passing_verification_report("comp-foo", "R-FOO-001"),
                "license_scan": _clean_license_scan("comp-foo"),
                "secret_scan": _clean_secret_scan(),
            },
            "comp-bar": {
                "hit": True,
                "verification_report": _passing_verification_report("comp-bar", "R-BAR-001"),
                "license_scan": _clean_license_scan("comp-bar"),
                "secret_scan": _clean_secret_scan(),
            },
        },
    }
    repo_root, calls_log, _ = _setup_repo(
        tmp_path,
        components=[("foo", ["R-FOO-001"]), ("bar", ["R-BAR-001"])],
        provenance_config=provenance_config,
    )

    provenance_tracker.check_readiness(repo_root)

    calls = _read_calls(calls_log)
    check_calls = [c for c in calls if c["fn"] == "check_provenance"]
    assert len(check_calls) >= 2
    for call in check_calls:
        assert call["spec_bundle_hash"] == "sha256:k1"
        assert call["gate_versions"] == {"verifier": "v@1"}