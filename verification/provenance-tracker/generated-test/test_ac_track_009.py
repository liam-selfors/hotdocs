"""AC-TRACK-009: check_readiness checks components only via provenance-checker,
scoped by impact-analyzer's blast radius (or the whole corpus), reporting
not-ready reasons and never calling component-gate-runner."""

import json
from pathlib import Path

import provenance_tracker


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FULL_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
}


def passing_verification(cid):
    return {
        "component_id": cid,
        "criteria": [
            {"id": "AC-X-001", "covers": "R-X-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-X-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def clean_license(cid, blocked=False):
    return {
        "component_id": cid,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9 if blocked else 0.1,
        "block_threshold": 0.70,
        "blocked": blocked,
        "matches": (
            [{"reference_id": "ref-1", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.9}]
            if blocked else []
        ),
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def clean_secret():
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


def hit_result(cid, verification=None, license_scan=None, secret_scan=None):
    return {
        "hit": True,
        "verification_report": verification if verification is not None else passing_verification(cid),
        "license_scan": license_scan if license_scan is not None else clean_license(cid),
        "secret_scan": secret_scan if secret_scan is not None else clean_secret(),
    }


def miss_result():
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def write_component(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "component.md").write_text(
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: false\n"
        "realizes: []\n"
        "depends_on: []\n"
        "---\n\n"
        f"# comp-{slug}\n\nA fixture component.\n"
    )


PROVENANCE_CHECKER_SRC = '''
import json

_CONFIG_PATH = {config_path!r}
_LOG_PATH = {log_path!r}


def _cfg():
    with open(_CONFIG_PATH) as f:
        return json.load(f)


def _log(rec):
    with open(_LOG_PATH, "a") as f:
        try:
            f.write(json.dumps(rec) + "\\n")
        except TypeError:
            f.write(json.dumps({{k: repr(v) for k, v in rec.items()}}) + "\\n")


class _ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


def current_sealed_key(component_id, repo_root):
    _log({{"fn": "current_sealed_key", "component_id": component_id}})
    return None


def current_provenance_key(component_id, repo_root):
    _log({{"fn": "current_provenance_key", "component_id": component_id}})
    key = _cfg()["key"]
    return _ProvenanceKey(key["spec_bundle_hash"], dict(key["gate_versions"]))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    gv = dict(gate_versions) if hasattr(gate_versions, "keys") else gate_versions
    _log({{
        "fn": "check_provenance",
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gv,
    }})
    results = _cfg()["results"]
    if component_id in results:
        return results[component_id]
    return {{"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}}


def check_sealed_provenance(component_id, repo_root):
    _log({{"fn": "check_sealed_provenance", "component_id": component_id}})
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

IMPACT_ANALYZER_SRC = '''
import json

_LOG_PATH = {log_path!r}
_IMPACTED = json.loads({impacted_json!r})


def compute_blast_radius(changed_ids, repo_root):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({{"fn": "compute_blast_radius", "changed_ids": list(changed_ids)}}) + "\\n")
    return {{"impacted": _IMPACTED, "precondition_error": None}}
'''

GATE_RUNNER_SRC = '''
import json

_LOG_PATH = {log_path!r}


def _record(name, args, kwargs):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({{"fn": name, "args": repr(args), "kwargs": repr(kwargs)}}) + "\\n")


def run_component_gates(*args, **kwargs):
    _record("run_component_gates", args, kwargs)
    raise AssertionError("component-gate-runner must never be called by check_readiness")


def __getattr__(name):
    if name.startswith("_"):
        raise AttributeError(name)

    def _fn(*args, **kwargs):
        _record(name, args, kwargs)
        raise AssertionError("component-gate-runner must never be called by check_readiness")

    return _fn
'''

CAPABILITY_VERIFIER_SRC = '''
import json

_LOG_PATH = {log_path!r}

GATE_VERSION = "capability_scenario_verifier@2.0.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _log(rec):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def check_capability_provenance(capability_id, repo_root):
    _log({{"fn": "check_capability_provenance", "capability_id": capability_id}})
    return {{"hit": True,
            "capability_scenario_report": {{capability_id: {{"overall": "pass", "scenarios": []}}}}}}


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log({{"fn": "run_capability_gates", "capability_id": capability_id}})
    return {{"hit": True,
            "capability_scenario_report": {{capability_id: {{"overall": "pass", "scenarios": []}}}}}}


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    _log({{"fn": "run_capability_scenarios"}})
    return {{}}
'''


def build_repo(tmp_path, slugs, results, key=None, impacted=None):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    repo_root.mkdir(parents=True, exist_ok=True)

    for slug in slugs:
        write_component(repo_root, slug)

    config_path = logs / "provenance_config.json"
    config_path.write_text(json.dumps({
        "key": key or {"spec_bundle_hash": "sha256:abc123", "gate_versions": FULL_GATE_VERSIONS},
        "results": results,
    }))

    paths = {
        "provenance": logs / "provenance_checker.log",
        "impact": logs / "impact_analyzer.log",
        "gate_runner": logs / "component_gate_runner.log",
        "capability": logs / "capability_scenario_verifier.log",
    }

    def write_module(slug, src):
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(src)

    write_module("provenance-checker", PROVENANCE_CHECKER_SRC.format(
        config_path=str(config_path), log_path=str(paths["provenance"])))
    write_module("impact-analyzer", IMPACT_ANALYZER_SRC.format(
        log_path=str(paths["impact"]), impacted_json=json.dumps(impacted or [])))
    write_module("component-gate-runner", GATE_RUNNER_SRC.format(
        log_path=str(paths["gate_runner"])))
    write_module("capability-scenario-verifier", CAPABILITY_VERIFIER_SRC.format(
        log_path=str(paths["capability"])))

    return repo_root, paths


def read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_calls(paths):
    return [r for r in read_log(paths["provenance"]) if r["fn"] == "check_provenance"]


def assert_gate_runner_never_called(paths):
    assert read_log(paths["gate_runner"]) == [], "component-gate-runner was called"


def reasons_of(report):
    return list(field(report, "not_ready_reasons"))


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------

def test_blast_radius_hit_and_miss(tmp_path):
    impacted = [
        {"component_id": "comp-alpha", "reason": "direct", "via": None},
        {"component_id": "comp-beta", "reason": "transitive-interface", "via": "comp-alpha"},
    ]
    results = {
        "comp-alpha": hit_result("comp-alpha"),
        "comp-beta": miss_result(),
        "comp-gamma": hit_result("comp-gamma"),
    }
    repo_root, paths = build_repo(
        tmp_path, ["alpha", "beta", "gamma"], results, impacted=impacted)

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert set(components.keys()) == {"comp-alpha", "comp-beta"}

    reasons = reasons_of(report)
    assert any("comp-beta" in r for r in reasons), reasons
    assert field(report, "ready") is False

    impact_calls = read_log(paths["impact"])
    assert len(impact_calls) >= 1
    assert impact_calls[0]["changed_ids"] == ["comp-alpha"]

    assert {c["component_id"] for c in check_calls(paths)} == {"comp-alpha", "comp-beta"}
    assert_gate_runner_never_called(paths)


def test_whole_corpus_checks_every_component(tmp_path):
    slugs = ["alpha", "beta", "gamma"]
    results = {f"comp-{s}": hit_result(f"comp-{s}") for s in slugs}
    repo_root, paths = build_repo(tmp_path, slugs, results)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "scope") == "whole-corpus"
    checked = {c["component_id"] for c in check_calls(paths)}
    assert checked == {"comp-alpha", "comp-beta", "comp-gamma"}
    assert set(field(report, "components").keys()) == {"comp-alpha", "comp-beta", "comp-gamma"}
    assert_gate_runner_never_called(paths)


def test_failing_requirement_results_reported(tmp_path):
    verification = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "x equals 1 failed", "expected": 1, "actual": 2}},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "fail",
    }
    results = {"comp-foo": hit_result("comp-foo", verification=verification)}
    repo_root, paths = build_repo(tmp_path, ["foo"], results)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = reasons_of(report)
    assert any(
        "comp-foo" in r and "verification" in r and "R-FOO-002" in r for r in reasons
    ), reasons
    assert_gate_runner_never_called(paths)


def test_blocking_license_scan_reported(tmp_path):
    results = {
        "comp-foo": hit_result("comp-foo", license_scan=clean_license("comp-foo", blocked=True)),
    }
    repo_root, paths = build_repo(tmp_path, ["foo"], results)

    report = provenance_tracker.check_readiness(repo_root)

    reasons = reasons_of(report)
    assert any("comp-foo" in r and "license_scan" in r for r in reasons), reasons
    assert field(report, "ready") is False
    assert_gate_runner_never_called(paths)


def test_provenance_key_passed_through_unchanged(tmp_path):
    slugs = ["alpha", "beta"]
    results = {f"comp-{s}": hit_result(f"comp-{s}") for s in slugs}
    key = {"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}}
    repo_root, paths = build_repo(tmp_path, slugs, results, key=key)

    provenance_tracker.check_readiness(repo_root)

    calls = check_calls(paths)
    assert {c["component_id"] for c in calls} == {"comp-alpha", "comp-beta"}
    for c in calls:
        assert c["spec_bundle_hash"] == "sha256:k1"
        assert c["gate_versions"] == {"verifier": "v@1"}
    assert_gate_runner_never_called(paths)