import json
from pathlib import Path

import provenance_tracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


KEY_HASH = "sha256:k1"
KEY_GATES = {"verifier": "v@1"}

ALL_COMPONENTS = ["comp-alpha", "comp-beta", "comp-gamma"]


def _passing_report(component_id):
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


def _clean_license(component_id, blocked=False):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9 if blocked else 0.1,
        "block_threshold": 0.70,
        "blocked": blocked,
        "matches": (
            [{"reference_id": "ref-1", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.9}]
            if blocked
            else []
        ),
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _clean_secret():
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


def _hit(component_id, report=None, license_scan=None):
    return {
        "hit": True,
        "verification_report": report if report is not None else _passing_report(component_id),
        "license_scan": license_scan if license_scan is not None else _clean_license(component_id),
        "secret_scan": _clean_secret(),
    }


def _miss():
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


PROVENANCE_CHECKER_SRC = '''\
import json

LOG = {log!r}
CONFIG = {config!r}


def _log(rec):
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\\n")


def _config():
    with open(CONFIG) as f:
        return json.load(f)


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions

    def __getitem__(self, name):
        return getattr(self, name)

    def get(self, name, default=None):
        return getattr(self, name, default)


def _default_hit(component_id):
    return {{
        "hit": True,
        "verification_report": {{
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {{"R-FOO-001": "pass"}},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "pass",
        }},
        "license_scan": {{
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
        }},
        "secret_scan": {{
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }},
    }}


def current_sealed_key(component_id, repo_root):
    _log({{"fn": "current_sealed_key", "component_id": component_id}})
    return None


def current_provenance_key(component_id, repo_root):
    _log({{"fn": "current_provenance_key", "component_id": component_id}})
    cfg = _config()
    return ProvenanceKey(cfg["key"]["spec_bundle_hash"], dict(cfg["key"]["gate_versions"]))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({{
        "fn": "check_provenance",
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": dict(gate_versions) if gate_versions is not None else None,
    }})
    cfg = _config()
    result = cfg["results"].get(component_id)
    if result is None:
        result = _default_hit(component_id)
    return result


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


IMPACT_ANALYZER_SRC = '''\
import json

LOG = {log!r}
CONFIG = {config!r}


def compute_blast_radius(changed_ids, repo_root):
    with open(LOG, "a") as f:
        f.write(json.dumps({{"fn": "compute_blast_radius", "changed_ids": list(changed_ids)}}) + "\\n")
    with open(CONFIG) as f:
        cfg = json.load(f)
    return {{"impacted": cfg.get("impacted", []), "precondition_error": None}}
'''


GATE_RUNNER_SRC = '''\
import json

LOG = {log!r}


def _record(name):
    def _fn(*args, **kwargs):
        with open(LOG, "a") as f:
            f.write(json.dumps({{"fn": "component_gate_runner." + name}}) + "\\n")
        raise AssertionError("component-gate-runner must never be called by check_readiness")
    return _fn


run_component_gates = _record("run_component_gates")


def __getattr__(name):
    if name.startswith("_"):
        raise AttributeError(name)
    return _record(name)
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


def _hit(capability_id):
    return {{
        "hit": True,
        "capability_scenario_report": {{capability_id: {{"overall": "pass", "scenarios": []}}}},
    }}


def check_capability_provenance(capability_id, repo_root):
    _log({{"fn": "check_capability_provenance", "capability_id": capability_id}})
    return _hit(capability_id)


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log({{"fn": "run_capability_gates", "capability_id": capability_id}})
    return _hit(capability_id)


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    _log({{"fn": "run_capability_scenarios"}})
    return {{}}
'''


def _write_component(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "component.md").write_text(
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "depends_on: []\n"
        "---\n\n"
        f"# comp-{slug}\n\nA synthetic fixture component.\n"
    )


def _setup(tmp_path, results=None, impacted=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.jsonl"
    log.write_text("")
    config = tmp_path / "fake_config.json"
    config.write_text(
        json.dumps(
            {
                "key": {"spec_bundle_hash": KEY_HASH, "gate_versions": KEY_GATES},
                "results": results or {},
                "impacted": impacted or [],
            }
        )
    )

    for cid in ALL_COMPONENTS:
        _write_component(repo_root, cid[len("comp-"):])

    fakes = {
        "provenance-checker": ("provenance_checker", PROVENANCE_CHECKER_SRC),
        "impact-analyzer": ("impact_analyzer", IMPACT_ANALYZER_SRC),
        "component-gate-runner": ("component_gate_runner", GATE_RUNNER_SRC),
        "capability-scenario-verifier": ("capability_scenario_verifier", CAPABILITY_VERIFIER_SRC),
    }
    for slug, (module_name, src) in fakes.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{module_name}.py").write_text(src.format(log=str(log), config=str(config)))

    return repo_root, log


def _calls(log):
    return [json.loads(line) for line in Path(log).read_text().splitlines() if line.strip()]


def _gate_runner_calls(log):
    return [c for c in _calls(log) if c["fn"].startswith("component_gate_runner.")]


def _reasons(report):
    return [str(r) for r in field(report, "not_ready_reasons")]


# ---------------------------------------------------------------------------
# Scenario 1: blast radius with one hit and one miss
# ---------------------------------------------------------------------------

def test_blast_radius_hit_and_miss_never_calls_gate_runner(tmp_path):
    repo_root, log = _setup(
        tmp_path,
        results={"comp-alpha": _hit("comp-alpha"), "comp-beta": _miss()},
        impacted=[
            {"component_id": "comp-alpha", "reason": "direct", "via": None},
            {"component_id": "comp-beta", "reason": "transitive-interface", "via": "comp-alpha"},
        ],
    )

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert set(components.keys()) == {"comp-alpha", "comp-beta"}
    assert len(components) == 2

    reasons = _reasons(report)
    assert any("comp-beta" in r for r in reasons), reasons

    assert any(c["fn"] == "compute_blast_radius" for c in _calls(log))
    assert _gate_runner_calls(log) == []


# ---------------------------------------------------------------------------
# Scenario 2: no changed_ids → whole corpus
# ---------------------------------------------------------------------------

def test_no_changed_ids_checks_every_component_whole_corpus(tmp_path):
    repo_root, log = _setup(tmp_path)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "scope") == "whole-corpus"
    checked = {c["component_id"] for c in _calls(log) if c["fn"] == "check_provenance"}
    assert checked == set(ALL_COMPONENTS)
    assert _gate_runner_calls(log) == []


# ---------------------------------------------------------------------------
# Scenario 3: hit with a failing verification report
# ---------------------------------------------------------------------------

def test_hit_with_failing_verification_report_is_not_ready(tmp_path):
    failing_report = {
        "component_id": "comp-alpha",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "x", "expected": 1, "actual": 2}},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "fail",
    }
    repo_root, log = _setup(
        tmp_path,
        results={"comp-alpha": _hit("comp-alpha", report=failing_report)},
    )

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = _reasons(report)
    matching = [
        r for r in reasons
        if "comp-alpha" in r and "verification" in r and "R-FOO-002" in r
    ]
    assert matching, reasons
    assert _gate_runner_calls(log) == []


# ---------------------------------------------------------------------------
# Scenario 4: hit with passing report but blocking license scan
# ---------------------------------------------------------------------------

def test_hit_with_blocked_license_scan_names_license_scan(tmp_path):
    repo_root, log = _setup(
        tmp_path,
        results={
            "comp-alpha": _hit(
                "comp-alpha", license_scan=_clean_license("comp-alpha", blocked=True)
            )
        },
    )

    report = provenance_tracker.check_readiness(repo_root)

    reasons = _reasons(report)
    matching = [r for r in reasons if "comp-alpha" in r and "license_scan" in r]
    assert matching, reasons
    assert _gate_runner_calls(log) == []


# ---------------------------------------------------------------------------
# Scenario 5: key values passed through unchanged
# ---------------------------------------------------------------------------

def test_check_provenance_receives_current_provenance_key_unchanged(tmp_path):
    repo_root, log = _setup(tmp_path)

    provenance_tracker.check_readiness(repo_root)

    checks = [c for c in _calls(log) if c["fn"] == "check_provenance"]
    assert checks, "check_provenance was never called"
    for c in checks:
        assert c["spec_bundle_hash"] == "sha256:k1"
        assert c["gate_versions"] == {"verifier": "v@1"}
    assert _gate_runner_calls(log) == []