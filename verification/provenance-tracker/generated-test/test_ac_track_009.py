# hotdocs-criterion: sha256:8c04eba19a361ba5557c05181adafb98b51f77aa5add5806d29f6a3c345bd915
import json
from pathlib import Path

import provenance_tracker


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


DEFAULT_HASH = "sha256:" + "a" * 64
DEFAULT_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}


def verification_report(component_id, requirement_results):
    criteria = []
    n = 0
    for rid, res in sorted(requirement_results.items()):
        n += 1
        entry = {
            "id": "AC-FOO-00" + str(n),
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            entry["failure_detail"] = {
                "message": "assertion failed",
                "expected": 1,
                "actual": 2,
            }
            entry["failure_origin"] = "implementation"
        criteria.append(entry)
    overall = "fail" if "fail" in requirement_results.values() else "pass"
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(requirement_results),
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "b" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": overall,
    }


def license_scan(component_id, blocked=False):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9 if blocked else 0.1,
        "block_threshold": 0.70,
        "blocked": blocked,
        "matches": (
            [
                {
                    "reference_id": "ref-123",
                    "license_family": "gpl-3.0",
                    "risk_tier": "high",
                    "score": 0.9,
                }
            ]
            if blocked
            else []
        ),
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def secret_scan():
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


def hit_result(component_id, requirement_results=None, blocked=False):
    if requirement_results is None:
        requirement_results = {"R-FOO-001": "pass"}
    return {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(component_id, requirement_results),
        "license_scan": license_scan(component_id, blocked=blocked),
        "secret_scan": secret_scan(),
    }


def miss_result():
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


PROVENANCE_CHECKER_BODY = '''

def _log(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=repr) + "\\n")


def _config():
    with open(_CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions, assets):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions
        self.assets = assets

    def __getitem__(self, name):
        return getattr(self, name)

    def get(self, name, default=None):
        return getattr(self, name, default)

    def to_dict(self):
        return {
            "spec_bundle_hash": self.spec_bundle_hash,
            "gate_versions": dict(self.gate_versions),
            "assets": list(self.assets),
        }


def current_sealed_key(component_id, repo_root):
    _log({"fn": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"fn": "current_provenance_key", "component_id": component_id})
    key = _config()["key"]
    assets = [{
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:" + "c" * 64,
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }]
    return ProvenanceKey(key["spec_bundle_hash"], dict(key["gate_versions"]), assets)


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({
        "fn": "check_provenance",
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gate_versions,
    })
    cfg = _config()
    return cfg["results"].get(component_id, cfg["default"])


def check_sealed_provenance(component_id, repo_root):
    _log({"fn": "check_sealed_provenance", "component_id": component_id})
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


IMPACT_ANALYZER_BODY = '''

def _log(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=repr) + "\\n")


def _config():
    with open(_CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


class ImpactedComponent:
    def __init__(self, component_id, reason, via, guarantee_ids=None):
        self.component_id = component_id
        self.reason = reason
        self.via = via
        self.guarantee_ids = guarantee_ids

    def __getitem__(self, name):
        return getattr(self, name)

    def get(self, name, default=None):
        return getattr(self, name, default)

    def to_dict(self):
        d = {"component_id": self.component_id, "reason": self.reason, "via": self.via}
        if self.reason == "transitive-guarantee":
            d["guarantee_ids"] = list(self.guarantee_ids or [])
        return d


class BlastRadiusReport:
    def __init__(self, impacted, precondition_error):
        self.impacted = impacted
        self.precondition_error = precondition_error

    def __getitem__(self, name):
        return getattr(self, name)

    def get(self, name, default=None):
        return getattr(self, name, default)

    def to_dict(self):
        return {
            "impacted": [i.to_dict() for i in self.impacted],
            "precondition_error": self.precondition_error,
        }


def compute_blast_radius(changed_ids, repo_root):
    _log({"fn": "compute_blast_radius", "changed_ids": list(changed_ids)})
    blast = _config()["blast"]
    impacted = [
        ImpactedComponent(e["component_id"], e["reason"], e["via"], e.get("guarantee_ids"))
        for e in blast["impacted"]
    ]
    return BlastRadiusReport(impacted, blast["precondition_error"])
'''


GATE_RUNNER_BODY = '''

def _log(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=repr) + "\\n")


def run_component_gates(*args, **kwargs):
    _log({"fn": "run_component_gates"})
    raise RuntimeError("component-gate-runner must never be called")
'''


CAPABILITY_BODY = '''

GATE_VERSION = "capability_scenario_verifier@2.2.0"


class UnknownCapabilityError(ValueError):
    pass


class ModelRequiredError(ValueError):
    pass


def _log(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=repr) + "\\n")


def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    _log({"fn": "run_capability_scenarios"})
    return {}


def check_capability_provenance(capability_id, repo_root):
    _log({"fn": "check_capability_provenance", "capability_id": capability_id})
    return {
        "hit": True,
        "capability_scenario_report": {capability_id: {"overall": "pass", "scenarios": []}},
    }


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log({"fn": "run_capability_gates", "capability_id": capability_id})
    return {
        "hit": False,
        "capability_scenario_report": {capability_id: {"overall": "pass", "scenarios": []}},
    }
'''


def module_header(config_path, log_path):
    return (
        "import json\n\n"
        + "_CONFIG = " + repr(str(config_path)) + "\n"
        + "_LOG = " + repr(str(log_path)) + "\n"
    )


def write_component(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        + "id: " + "comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " Component\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n\n"
        + "# " + slug.capitalize() + " Component\n\n"
        + "A fixture component.\n"
    )
    (d / "component.md").write_text(text, encoding="utf-8")


def setup_repo(tmp_path, slugs, results=None, default=None, key=None, blast=None):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "components").mkdir(parents=True)
    for slug in slugs:
        write_component(repo_root, slug)

    config_path = tmp_path / "fake_config.json"
    log_path = tmp_path / "calls.log"
    config = {
        "results": results or {},
        "default": default if default is not None else hit_result("comp-unknown"),
        "key": key or {"spec_bundle_hash": DEFAULT_HASH, "gate_versions": DEFAULT_GATE_VERSIONS},
        "blast": blast or {"impacted": [], "precondition_error": None},
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    header = module_header(config_path, log_path)
    fakes = [
        ("provenance-checker", "provenance_checker", PROVENANCE_CHECKER_BODY),
        ("impact-analyzer", "impact_analyzer", IMPACT_ANALYZER_BODY),
        ("component-gate-runner", "component_gate_runner", GATE_RUNNER_BODY),
        ("capability-scenario-verifier", "capability_scenario_verifier", CAPABILITY_BODY),
    ]
    for slug, module_name, body in fakes:
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(header + body, encoding="utf-8")
    return repo_root, log_path


def read_log(log_path):
    if not Path(log_path).is_file():
        return []
    return [
        json.loads(line)
        for line in Path(log_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def calls(log_path, fn):
    return [e for e in read_log(log_path) if e.get("fn") == fn]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_blast_radius_hit_and_miss_never_runs_gates(tmp_path):
    repo_root, log_path = setup_repo(
        tmp_path,
        ["alpha", "beta"],
        results={"comp-alpha": hit_result("comp-alpha"), "comp-beta": miss_result()},
        blast={
            "impacted": [
                {"component_id": "comp-alpha", "reason": "direct", "via": None},
                {"component_id": "comp-beta", "reason": "transitive-interface", "via": "comp-alpha"},
            ],
            "precondition_error": None,
        },
    )

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert set(components.keys()) == {"comp-alpha", "comp-beta"}
    assert len(components) == 2
    assert field(report, "ready") is False
    reasons = field(report, "not_ready_reasons")
    assert any("comp-beta" in r for r in reasons), reasons
    assert not any("comp-alpha" in r and "comp-beta" not in r for r in reasons), reasons
    assert calls(log_path, "run_component_gates") == []


def test_precondition_error_reports_blast_radius_unavailable(tmp_path):
    error = "corpus did not pass spec-linter cleanly: 6 fail-severity finding(s)"
    repo_root, log_path = setup_repo(
        tmp_path,
        ["alpha"],
        results={"comp-alpha": hit_result("comp-alpha")},
        blast={"impacted": [], "precondition_error": error},
    )

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == ["blast radius unavailable: " + error]
    assert len(field(report, "components")) == 0
    assert calls(log_path, "check_provenance") == []
    assert calls(log_path, "run_component_gates") == []


def test_no_changed_ids_checks_whole_corpus(tmp_path):
    repo_root, log_path = setup_repo(
        tmp_path,
        ["alpha", "beta"],
        results={"comp-alpha": hit_result("comp-alpha"), "comp-beta": hit_result("comp-beta")},
    )
    # A directory without a component.md is not a component.
    (repo_root / "specs" / "components" / "notes").mkdir()

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "scope") == "whole-corpus"
    checked = {e["component_id"] for e in calls(log_path, "check_provenance")}
    assert checked == {"comp-alpha", "comp-beta"}
    assert set(field(report, "components").keys()) == {"comp-alpha", "comp-beta"}
    assert calls(log_path, "run_component_gates") == []


def test_empty_corpus_without_gen_uses_tool_checker_and_is_ready(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "components").mkdir(parents=True)
    assert not (repo_root / "gen").exists()

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True
    assert field(report, "scope") == "whole-corpus"
    assert len(field(report, "components")) == 0


def test_failing_verification_report_names_failed_requirements(tmp_path):
    repo_root, log_path = setup_repo(
        tmp_path,
        ["alpha"],
        results={
            "comp-alpha": hit_result(
                "comp-alpha", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
            )
        },
    )

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = field(report, "not_ready_reasons")
    entries = [r for r in reasons if "comp-alpha" in r and "verification" in r]
    assert entries, reasons
    entry = entries[0]
    assert "R-FOO-002" in entry
    assert "R-FOO-001" not in entry
    assert calls(log_path, "run_component_gates") == []


def test_blocking_license_scan_is_named(tmp_path):
    repo_root, log_path = setup_repo(
        tmp_path,
        ["alpha"],
        results={"comp-alpha": hit_result("comp-alpha", {"R-FOO-001": "pass"}, blocked=True)},
    )

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = field(report, "not_ready_reasons")
    entries = [r for r in reasons if "comp-alpha" in r]
    assert entries, reasons
    assert any("license_scan" in r for r in entries), entries
    assert calls(log_path, "run_component_gates") == []


def test_provenance_key_passed_unchanged_to_check_provenance(tmp_path):
    repo_root, log_path = setup_repo(
        tmp_path,
        ["alpha", "beta"],
        results={"comp-alpha": hit_result("comp-alpha"), "comp-beta": hit_result("comp-beta")},
        key={"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}},
    )

    provenance_tracker.check_readiness(repo_root)

    checks = calls(log_path, "check_provenance")
    assert {e["component_id"] for e in checks} == {"comp-alpha", "comp-beta"}
    for entry in checks:
        assert entry["spec_bundle_hash"] == "sha256:k1"
        assert entry["gate_versions"] == {"verifier": "v@1"}
    assert calls(log_path, "run_component_gates") == []