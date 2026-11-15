import provenance_tracker

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PROVENANCE_CHECKER_SRC = r'''
import json
from pathlib import Path


def _dir(repo_root):
    return Path(repo_root) / ".fakes"


def _log(repo_root, record):
    d = _dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "provenance_checker.log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=repr) + "\n")


def _config(repo_root):
    return json.loads((_dir(repo_root) / "config.json").read_text(encoding="utf-8"))


class ProvenanceKey(dict):
    def __init__(self, spec_bundle_hash, gate_versions):
        super().__init__(spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions)
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log(repo_root, {"fn": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log(repo_root, {"fn": "current_provenance_key", "component_id": component_id})
    key = _config(repo_root)["key"]
    return ProvenanceKey(key["spec_bundle_hash"], dict(key["gate_versions"]))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    try:
        gv = dict(gate_versions)
    except Exception:
        gv = repr(gate_versions)
    _log(repo_root, {
        "fn": "check_provenance",
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gv,
    })
    results = _config(repo_root)["results"]
    if component_id in results:
        return results[component_id]
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log(repo_root, {"fn": "check_sealed_provenance", "component_id": component_id})
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


IMPACT_ANALYZER_SRC = r'''
import json
from pathlib import Path


def _dir(repo_root):
    return Path(repo_root) / ".fakes"


def compute_blast_radius(changed_ids, repo_root):
    d = _dir(repo_root)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "impact_analyzer.log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"fn": "compute_blast_radius",
                             "changed_ids": list(changed_ids)}, default=repr) + "\n")
    cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
    return cfg["blast_radius"]
'''


GATE_RUNNER_SRC_TEMPLATE = r'''
import json

_LOG = __LOG_PATH__


def _log(name, args, kwargs):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"fn": name, "args": [repr(a) for a in args],
                             "kwargs": {k: repr(v) for k, v in kwargs.items()}}) + "\n")


def run_component_gates(*args, **kwargs):
    _log("run_component_gates", args, kwargs)
    raise AssertionError("component-gate-runner must never be called by check_readiness")
'''


CAPABILITY_VERIFIER_SRC = r'''
import json
from pathlib import Path

GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _log(repo_root, record):
    d = Path(repo_root) / ".fakes"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "capability_verifier.log.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=repr) + "\n")


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    _log(repo_root, {"fn": "run_capability_scenarios"})
    return {}


def check_capability_provenance(capability_id, repo_root):
    _log(repo_root, {"fn": "check_capability_provenance", "capability_id": capability_id})
    return {
        "hit": True,
        "capability_scenario_report": {capability_id: {"overall": "pass", "scenarios": []}},
    }


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log(repo_root, {"fn": "run_capability_gates", "capability_id": capability_id})
    return {
        "hit": True,
        "capability_scenario_report": {capability_id: {"overall": "pass", "scenarios": []}},
    }
'''


DEFAULT_KEY = {"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}}


def passing_verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def failing_verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "result.foo equals 5 failed",
                                "expected": 5, "actual": 3}},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "fail",
    }


def passing_license_scan(component_id):
    return {
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
    }


def blocked_license_scan(component_id):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9,
        "block_threshold": 0.7,
        "blocked": True,
        "matches": [
            {"reference_id": "ref-123", "license_family": "gpl-3.0",
             "risk_tier": "high", "score": 0.9},
        ],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def passing_secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@0.0.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def hit(component_id, verification=None, license_scan=None, secret_scan=None):
    return {
        "hit": True,
        "verification_report": verification or passing_verification_report(component_id),
        "license_scan": license_scan or passing_license_scan(component_id),
        "secret_scan": secret_scan or passing_secret_scan(),
    }


def miss():
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def write_fake(repo, slug, module_name, source):
    d = repo / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def build_repo(tmp_path, component_ids, results, blast_radius=None, key=None):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    for cid in component_ids:
        slug = cid[len("comp-"):]
        d = repo / "specs" / "components" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "component.md").write_text(
            "---\n"
            f"id: {cid}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [test-team]\n"
            "sealed: false\n"
            "realizes: []\n"
            "depends_on: []\n"
            "---\n"
            "\n"
            f"# {slug.capitalize()}\n"
            "\n"
            "A synthetic fixture component.\n",
            encoding="utf-8",
        )
    (repo / "specs" / "product").mkdir(parents=True, exist_ok=True)

    fakes = repo / ".fakes"
    fakes.mkdir(parents=True, exist_ok=True)
    config = {
        "key": key or DEFAULT_KEY,
        "results": results,
        "blast_radius": blast_radius or {"impacted": [], "precondition_error": None},
    }
    (fakes / "config.json").write_text(json.dumps(config), encoding="utf-8")

    gate_log = fakes / "gate_runner.log.jsonl"
    write_fake(repo, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    write_fake(repo, "impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_SRC)
    write_fake(
        repo,
        "component-gate-runner",
        "component_gate_runner",
        GATE_RUNNER_SRC_TEMPLATE.replace("__LOG_PATH__", repr(str(gate_log))),
    )
    write_fake(
        repo,
        "capability-scenario-verifier",
        "capability_scenario_verifier",
        CAPABILITY_VERIFIER_SRC,
    )
    return repo


def read_log(repo, name):
    path = repo / ".fakes" / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def check_provenance_calls(repo):
    return [r for r in read_log(repo, "provenance_checker.log.jsonl")
            if r["fn"] == "check_provenance"]


def assert_gate_runner_never_called(repo):
    assert read_log(repo, "gate_runner.log.jsonl") == []


def reasons_of(report):
    reasons = field(report, "not_ready_reasons")
    return [str(r) for r in reasons]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def test_blast_radius_scope_hit_and_miss_never_runs_gates(tmp_path):
    repo = build_repo(
        tmp_path,
        ["comp-alpha", "comp-beta", "comp-gamma"],
        results={
            "comp-alpha": hit("comp-alpha"),
            "comp-beta": miss(),
            "comp-gamma": hit("comp-gamma"),
        },
        blast_radius={
            "impacted": [
                {"component_id": "comp-alpha", "reason": "direct", "via": None},
                {"component_id": "comp-beta", "reason": "transitive-interface",
                 "via": "comp-alpha"},
            ],
            "precondition_error": None,
        },
    )

    report = provenance_tracker.check_readiness(repo, changed_ids=["comp-alpha"])

    assert field(report, "scope") == "blast-radius"

    components = field(report, "components")
    assert set(components) == {"comp-alpha", "comp-beta"}
    assert len(components) == 2

    reasons = reasons_of(report)
    assert any("comp-beta" in r for r in reasons), reasons

    impact_calls = read_log(repo, "impact_analyzer.log.jsonl")
    assert impact_calls, "impact-analyzer must be called given changed_ids"
    assert "comp-alpha" in impact_calls[0]["changed_ids"]

    assert_gate_runner_never_called(repo)


def test_whole_corpus_checks_every_component(tmp_path):
    ids = ["comp-alpha", "comp-beta", "comp-gamma"]
    repo = build_repo(
        tmp_path,
        ids,
        results={cid: hit(cid) for cid in ids},
    )

    report = provenance_tracker.check_readiness(repo)

    assert field(report, "scope") == "whole-corpus"

    checked = {r["component_id"] for r in check_provenance_calls(repo)}
    assert checked == set(ids)

    assert_gate_runner_never_called(repo)


def test_failing_verification_report_names_failing_requirement(tmp_path):
    cid = "comp-foo"
    repo = build_repo(
        tmp_path,
        [cid],
        results={cid: hit(cid, verification=failing_verification_report(cid))},
    )

    report = provenance_tracker.check_readiness(repo)

    assert field(report, "ready") is False

    reasons = reasons_of(report)
    matching = [r for r in reasons
                if cid in r and "verification" in r and "R-FOO-002" in r]
    assert matching, reasons

    assert_gate_runner_never_called(repo)


def test_blocked_license_scan_named_in_reason(tmp_path):
    cid = "comp-foo"
    repo = build_repo(
        tmp_path,
        [cid],
        results={cid: hit(cid, license_scan=blocked_license_scan(cid))},
    )

    report = provenance_tracker.check_readiness(repo)

    reasons = reasons_of(report)
    matching = [r for r in reasons if cid in r and "license_scan" in r]
    assert matching, reasons

    assert_gate_runner_never_called(repo)


def test_provenance_key_passed_through_unchanged(tmp_path):
    ids = ["comp-alpha", "comp-beta"]
    repo = build_repo(
        tmp_path,
        ids,
        results={cid: hit(cid) for cid in ids},
        key={"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}},
    )

    provenance_tracker.check_readiness(repo)

    calls = check_provenance_calls(repo)
    assert {c["component_id"] for c in calls} == set(ids)
    for call in calls:
        assert call["spec_bundle_hash"] == "sha256:k1"
        assert call["gate_versions"] == {"verifier": "v@1"}

    assert_gate_runner_never_called(repo)