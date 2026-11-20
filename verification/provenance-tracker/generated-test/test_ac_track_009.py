# hotdocs-criterion: sha256:28a422081d5f7e2233b22fc0150363096ff4a9f6a70e3479062c47261ae8f76d
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Result shapes (documented, complete)
# ---------------------------------------------------------------------------

PYTHON_ASSET = {
    "kind": "python",
    "path": ".",
    "definition_sha256": None,
    "adapter_sha256": "sha256:" + "a" * 64,
    "versions": {"python": "3.12.4"},
    "lockfile_sha256": None,
}


def verification_report(component_id, requirement_results):
    criteria = []
    n = 0
    for rid in sorted(requirement_results):
        n += 1
        res = requirement_results[rid]
        crit = {
            "id": "AC-FOO-" + str(n).zfill(3),
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            crit["failure_detail"] = {"message": "check failed", "expected": 1, "actual": 2}
            crit["failure_origin"] = "implementation"
        criteria.append(crit)
    overall = "fail" if "fail" in requirement_results.values() else "pass"
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(requirement_results),
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [dict(PYTHON_ASSET)],
        "overall": overall,
    }


def license_scan(component_id, blocked=False):
    if blocked:
        score = 0.9
        matches = [
            {"reference_id": "ref-1", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.9}
        ]
    else:
        score = 0.1
        matches = []
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": score,
        "block_threshold": 0.7,
        "blocked": blocked,
        "matches": matches,
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


def hit(component_id, requirement_results=None, blocked=False):
    if requirement_results is None:
        requirement_results = {"R-FOO-001": "pass"}
    return {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(component_id, requirement_results),
        "license_scan": license_scan(component_id, blocked=blocked),
        "secret_scan": secret_scan(),
    }


def miss():
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


# ---------------------------------------------------------------------------
# Fake dependency sources
# ---------------------------------------------------------------------------

COMMON_HEADER = (
    "import json\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "def _config():\n"
    "    with open(CONFIG) as f:\n"
    "        return json.load(f)\n"
    "\n"
)


def checker_source(log_path, config_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "CONFIG = " + repr(str(config_path)) + "\n"
        + COMMON_HEADER +
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "    def __getitem__(self, name):\n"
        "        return getattr(self, name)\n"
        "    def get(self, name, default=None):\n"
        "        return getattr(self, name, default)\n"
        "    def to_dict(self):\n"
        "        return {'spec_bundle_hash': self.spec_bundle_hash,\n"
        "                'gate_versions': dict(self.gate_versions),\n"
        "                'assets': list(self.assets)}\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log({'fn': 'current_sealed_key', 'component_id': component_id})\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log({'fn': 'current_provenance_key', 'component_id': component_id})\n"
        "    cfg = _config()\n"
        "    return ProvenanceKey(cfg['key']['spec_bundle_hash'],\n"
        "                         dict(cfg['key']['gate_versions']),\n"
        "                         [dict(a) for a in cfg['key']['assets']])\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log({'fn': 'check_provenance', 'component_id': component_id,\n"
        "          'spec_bundle_hash': spec_bundle_hash, 'gate_versions': gate_versions})\n"
        "    cfg = _config()\n"
        "    return cfg['results'][component_id]\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log({'fn': 'check_sealed_provenance', 'component_id': component_id})\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None,\n"
        "            'secret_scan': None, 'owners': None, 'source_hash': None,\n"
        "            'written_at': None}\n"
    )


def impact_source(log_path, config_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "CONFIG = " + repr(str(config_path)) + "\n"
        + COMMON_HEADER +
        "class ImpactedComponent:\n"
        "    def __init__(self, component_id, reason, via, guarantee_ids=None):\n"
        "        self.component_id = component_id\n"
        "        self.reason = reason\n"
        "        self.via = via\n"
        "        self.guarantee_ids = guarantee_ids\n"
        "    def __getitem__(self, name):\n"
        "        return getattr(self, name)\n"
        "    def get(self, name, default=None):\n"
        "        return getattr(self, name, default)\n"
        "    def to_dict(self):\n"
        "        d = {'component_id': self.component_id, 'reason': self.reason, 'via': self.via}\n"
        "        if self.reason == 'transitive-guarantee':\n"
        "            d['guarantee_ids'] = list(self.guarantee_ids or [])\n"
        "        return d\n"
        "\n"
        "class BlastRadiusReport:\n"
        "    def __init__(self, impacted, precondition_error):\n"
        "        self.impacted = impacted\n"
        "        self.precondition_error = precondition_error\n"
        "    def __getitem__(self, name):\n"
        "        return getattr(self, name)\n"
        "    def get(self, name, default=None):\n"
        "        return getattr(self, name, default)\n"
        "    def to_dict(self):\n"
        "        return {'impacted': [i.to_dict() for i in self.impacted],\n"
        "                'precondition_error': self.precondition_error}\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log({'fn': 'compute_blast_radius', 'changed_ids': list(changed_ids)})\n"
        "    cfg = _config()\n"
        "    return BlastRadiusReport([ImpactedComponent(**e) for e in cfg['impacted']], None)\n"
    )


def gate_runner_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(name):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'fn': name}) + '\\n')\n"
        "\n"
        "def run_component_gates(*args, **kwargs):\n"
        "    _log('run_component_gates')\n"
        "    raise RuntimeError('component-gate-runner must never be called')\n"
        "\n"
        "def __getattr__(name):\n"
        "    if name.startswith('__'):\n"
        "        raise AttributeError(name)\n"
        "    def _any(*args, **kwargs):\n"
        "        _log(name)\n"
        "        raise RuntimeError('component-gate-runner must never be called')\n"
        "    return _any\n"
    )


def capability_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _log(name, cid):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'fn': name, 'capability_id': cid}) + '\\n')\n"
        "\n"
        "def _hit(cid):\n"
        "    return {'hit': True, 'capability_scenario_report':\n"
        "            {cid: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance', capability_id)\n"
        "    return _hit(capability_id)\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates', capability_id)\n"
        "    return _hit(capability_id)\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log('run_capability_scenarios', None)\n"
        "    return {}\n"
    )


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------

def write_component(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "component.md").write_text(
        "---\n"
        "id: comp-" + slug + "\n"
        "title: Component " + slug + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# Component " + slug + "\n"
        "\n"
        "A fixture component.\n"
    )


def setup_repo(tmp_path, slugs, results, impacted=None,
               key_hash="sha256:k1", key_gates=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    for slug in slugs:
        write_component(repo_root, slug)

    if key_gates is None:
        key_gates = {"verifier": "v@1"}
    config = {
        "key": {
            "spec_bundle_hash": key_hash,
            "gate_versions": key_gates,
            "assets": [PYTHON_ASSET],
        },
        "results": results,
        "impacted": impacted or [],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    paths = {
        "checker": logs / "checker.log",
        "impact": logs / "impact.log",
        "gate": logs / "gate.log",
        "cap": logs / "cap.log",
    }

    def put(slug, module, source):
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(source)

    put("provenance-checker", "provenance_checker", checker_source(paths["checker"], config_path))
    put("impact-analyzer", "impact_analyzer", impact_source(paths["impact"], config_path))
    put("component-gate-runner", "component_gate_runner", gate_runner_source(paths["gate"]))
    put("capability-scenario-verifier", "capability_scenario_verifier", capability_source(paths["cap"]))
    return repo_root, paths


def read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_calls(paths):
    return [e for e in read_log(paths["checker"]) if e["fn"] == "check_provenance"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_blast_radius_scope_hit_and_miss(tmp_path):
    results = {"comp-alpha": hit("comp-alpha"), "comp-beta": miss(), "comp-gamma": hit("comp-gamma")}
    impacted = [
        {"component_id": "comp-alpha", "reason": "direct", "via": None},
        {"component_id": "comp-beta", "reason": "transitive-interface", "via": "comp-alpha"},
    ]
    repo_root, paths = setup_repo(tmp_path, ["alpha", "beta", "gamma"], results, impacted)

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    impact_calls = [e for e in read_log(paths["impact"]) if e["fn"] == "compute_blast_radius"]
    assert impact_calls, "impact-analyzer's compute_blast_radius was never called"
    assert impact_calls[0]["changed_ids"] == ["comp-alpha"]

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert set(components.keys()) == {"comp-alpha", "comp-beta"}

    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-beta" in r for r in reasons), reasons
    assert field(report, "ready") is False

    assert read_log(paths["gate"]) == []


def test_no_changed_ids_checks_whole_corpus(tmp_path):
    results = {
        "comp-alpha": hit("comp-alpha"),
        "comp-beta": hit("comp-beta"),
        "comp-gamma": hit("comp-gamma"),
    }
    repo_root, paths = setup_repo(tmp_path, ["alpha", "beta", "gamma"], results)

    report = provenance_tracker.check_readiness(repo_root)

    checked = {e["component_id"] for e in check_calls(paths)}
    assert checked == {"comp-alpha", "comp-beta", "comp-gamma"}
    assert field(report, "scope") == "whole-corpus"
    assert set(field(report, "components").keys()) == {"comp-alpha", "comp-beta", "comp-gamma"}
    assert read_log(paths["gate"]) == []


def test_failing_verification_report_is_not_ready(tmp_path):
    results = {
        "comp-alpha": hit("comp-alpha", {"R-FOO-001": "pass", "R-FOO-002": "fail"}),
    }
    repo_root, paths = setup_repo(tmp_path, ["alpha"], results)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    matching = [
        r for r in reasons
        if "comp-alpha" in r and "verification" in r and "R-FOO-002" in r
    ]
    assert matching, reasons
    assert read_log(paths["gate"]) == []


def test_blocked_license_scan_is_named(tmp_path):
    results = {"comp-alpha": hit("comp-alpha", {"R-FOO-001": "pass"}, blocked=True)}
    repo_root, paths = setup_repo(tmp_path, ["alpha"], results)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-alpha" in r and "license_scan" in r for r in reasons), reasons
    assert read_log(paths["gate"]) == []


def test_provenance_key_passed_unchanged(tmp_path):
    results = {"comp-alpha": hit("comp-alpha"), "comp-beta": hit("comp-beta")}
    repo_root, paths = setup_repo(
        tmp_path, ["alpha", "beta"], results,
        key_hash="sha256:k1", key_gates={"verifier": "v@1"},
    )

    provenance_tracker.check_readiness(repo_root)

    calls = check_calls(paths)
    assert {e["component_id"] for e in calls} == {"comp-alpha", "comp-beta"}
    for e in calls:
        assert e["spec_bundle_hash"] == "sha256:k1"
        assert e["gate_versions"] == {"verifier": "v@1"}
    assert read_log(paths["gate"]) == []