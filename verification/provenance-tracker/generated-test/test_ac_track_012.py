"""AC-TRACK-012 (covers R-TRACK-012).

Given a dict-shaped (never object-shaped) fake provenance-checker result
and a dict-shaped fake impact-analyzer impacted entry, when
check_readiness runs over that scope, then it reads hit/component_id/etc.
correctly from the dict shape and does not raise AttributeError.
"""

import provenance_tracker

import copy
import json
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FOO_HASH = "sha256:" + "a" * 64
BAR_HASH = "sha256:" + "b" * 64

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
}


def _hit_result(component_id):
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                }
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": component_id,
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


def _miss_result():
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


PROVENANCE_CHECKER_SRC = '''\
import copy
import json

LOG = {log!r}
RESULTS = {results!r}
HASHES = {hashes!r}
GATE_VERSIONS = {gate_versions!r}


def _log(rec):
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def _norm(component_id):
    component_id = str(component_id)
    return component_id if component_id.startswith("comp-") else "comp-" + component_id


class _Key(dict):
    """ProvenanceKey: documented as an object exposing both fields as
    attributes; also indexable, so it is readable either way."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def current_sealed_key(component_id, repo_root):
    _log({{"fn": "current_sealed_key", "component_id": _norm(component_id)}})
    return None


def current_provenance_key(component_id, repo_root):
    cid = _norm(component_id)
    _log({{"fn": "current_provenance_key", "component_id": cid}})
    return _Key(
        spec_bundle_hash=HASHES.get(cid, "sha256:" + "0" * 64),
        gate_versions=dict(GATE_VERSIONS),
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    cid = _norm(component_id)
    _log({{
        "fn": "check_provenance",
        "component_id": cid,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": dict(gate_versions),
    }})
    if cid in RESULTS:
        return copy.deepcopy(RESULTS[cid])
    return {{"hit": False, "verification_report": None,
             "license_scan": None, "secret_scan": None}}


def check_sealed_provenance(component_id, repo_root):
    _log({{"fn": "check_sealed_provenance", "component_id": _norm(component_id)}})
    return {{
        "hit": False,
        "sealed": False,
        "reason": "not_sealed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }}
'''


IMPACT_ANALYZER_SRC = '''\
import copy
import json

LOG = {log!r}
IMPACTED = {impacted!r}


def compute_blast_radius(changed_ids, repo_root):
    with open(LOG, "a") as f:
        f.write(json.dumps({{"fn": "compute_blast_radius",
                             "changed_ids": list(changed_ids)}}) + "\\n")
    return {{"impacted": copy.deepcopy(IMPACTED), "precondition_error": None}}
'''


CAPABILITY_VERIFIER_SRC = '''\
import json

LOG = {log!r}
GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _log(rec):
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def _report(capability_id):
    return {{capability_id: {{"overall": "pass", "scenarios": []}}}}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    _log({{"fn": "run_capability_scenarios"}})
    return {{}}


def check_capability_provenance(capability_id, repo_root):
    _log({{"fn": "check_capability_provenance", "capability_id": capability_id}})
    return {{"hit": True, "capability_scenario_report": _report(capability_id)}}


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log({{"fn": "run_capability_gates", "capability_id": capability_id}})
    return {{"hit": True, "capability_scenario_report": _report(capability_id)}}
'''


def _write_component_md(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "component.md").write_text(
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug} component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: false\n"
        "realizes: []\n"
        "---\n\n"
        f"# comp-{slug}\n\nA fixture component.\n"
    )


def _build_repo(tmp_path, results, impacted):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "invocations.jsonl"
    log.write_text("")

    for slug in ("foo", "bar"):
        _write_component_md(repo_root, slug)
        (repo_root / "gen" / slug).mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "product").mkdir(parents=True, exist_ok=True)

    pc_dir = repo_root / "gen" / "provenance-checker"
    pc_dir.mkdir(parents=True)
    (pc_dir / "provenance_checker.py").write_text(
        PROVENANCE_CHECKER_SRC.format(
            log=str(log),
            results=results,
            hashes={"comp-foo": FOO_HASH, "comp-bar": BAR_HASH},
            gate_versions=GATE_VERSIONS,
        )
    )

    ia_dir = repo_root / "gen" / "impact-analyzer"
    ia_dir.mkdir(parents=True)
    (ia_dir / "impact_analyzer.py").write_text(
        IMPACT_ANALYZER_SRC.format(log=str(log), impacted=impacted)
    )

    cv_dir = repo_root / "gen" / "capability-scenario-verifier"
    cv_dir.mkdir(parents=True)
    (cv_dir / "capability_scenario_verifier.py").write_text(
        CAPABILITY_VERIFIER_SRC.format(log=str(log))
    )

    return repo_root, log


def _read_log(log):
    return [json.loads(line) for line in Path(log).read_text().splitlines() if line.strip()]


IMPACTED = [
    {"component_id": "comp-foo", "reason": "direct", "via": None},
    {"component_id": "comp-bar", "reason": "transitive-interface", "via": "comp-foo"},
]


def _run(repo_root):
    try:
        return provenance_tracker.check_readiness(repo_root, changed_ids=["comp-foo"])
    except AttributeError as exc:  # the criterion's Then clause
        pytest.fail(
            f"check_readiness raised AttributeError reading a dict-shaped "
            f"dependency value: {exc!r}"
        )


def test_dict_shaped_results_read_correctly_mixed_hit_and_miss(tmp_path):
    results = {"comp-foo": _hit_result("comp-foo"), "comp-bar": _miss_result()}
    repo_root, log = _build_repo(tmp_path, copy.deepcopy(results), IMPACTED)

    report = _run(repo_root)

    # component_id was read from each dict-shaped impacted entry.
    components = field(report, "components")
    assert set(components.keys()) == {"comp-foo", "comp-bar"}

    # Each ProvenanceCheckResult copied verbatim from the dict shape.
    assert components["comp-foo"] == results["comp-foo"]
    assert components["comp-bar"] == results["comp-bar"]

    assert field(report, "scope") == "blast-radius"

    # `hit` was read correctly: the miss makes it not ready, and is named.
    assert field(report, "ready") is False
    reasons = field(report, "not_ready_reasons")
    assert any("comp-bar" in r for r in reasons), reasons
    assert not any("comp-foo" in r for r in reasons), reasons

    entries = _read_log(log)
    checks = {e["component_id"]: e for e in entries if e["fn"] == "check_provenance"}
    assert set(checks) == {"comp-foo", "comp-bar"}
    assert checks["comp-foo"]["spec_bundle_hash"] == FOO_HASH
    assert checks["comp-bar"]["spec_bundle_hash"] == BAR_HASH
    assert checks["comp-foo"]["gate_versions"] == GATE_VERSIONS
    assert not any(e["fn"] == "check_sealed_provenance" for e in entries)


def test_dict_shaped_results_all_hits_passing_are_ready(tmp_path):
    results = {"comp-foo": _hit_result("comp-foo"), "comp-bar": _hit_result("comp-bar")}
    repo_root, log = _build_repo(tmp_path, copy.deepcopy(results), IMPACTED)

    report = _run(repo_root)

    components = field(report, "components")
    assert set(components.keys()) == {"comp-foo", "comp-bar"}
    assert components["comp-foo"] == results["comp-foo"]
    assert components["comp-bar"] == results["comp-bar"]

    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []

    entries = _read_log(log)
    assert any(e["fn"] == "compute_blast_radius" for e in entries)
    assert {e["component_id"] for e in entries if e["fn"] == "check_provenance"} == {
        "comp-foo",
        "comp-bar",
    }