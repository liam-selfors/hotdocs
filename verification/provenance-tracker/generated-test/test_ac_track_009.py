# hotdocs-criterion: sha256:394e8e2997d929c846b867531ec92a1b019082abf7acbdf359e117ea25ed80e1
"""AC-TRACK-009: check_readiness scope resolution, provenance routing, and
not-ready reporting (R-TRACK-009)."""

import json
from pathlib import Path

import provenance_tracker


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def read_log(path):
    path = Path(path)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def write_component(repo_root, slug, component_id):
    d = Path(repo_root) / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "id: " + component_id + "\n"
        "title: Fixture " + slug + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# Fixture " + slug + "\n"
        "\n"
        "A fixture component.\n"
    )
    (d / "component.md").write_text(text)


def passing_verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "a" * 64,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "drivers": [],
        "overall": "pass",
    }


def failing_verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "result.foo equals 5 failed", "expected": 5, "actual": 3},
             "failure_origin": "implementation"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "a" * 64,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "drivers": [],
        "overall": "fail",
    }


def license_scan(component_id, blocked=False):
    if blocked:
        return {
            "component_id": component_id,
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.85,
            "block_threshold": 0.70,
            "blocked": True,
            "matches": [{"reference_id": "ref-123", "license_family": "gpl-3.0",
                         "risk_tier": "high", "score": 0.85}],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def stored_secret_scan():
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


def hit_result(component_id, verification_report=None, license=None):
    return {
        "hit": True,
        "reason": None,
        "verification_report": verification_report
        if verification_report is not None else passing_verification_report(component_id),
        "license_scan": license if license is not None else license_scan(component_id),
        "secret_scan": stored_secret_scan(),
    }


def miss_result():
    return {"hit": False, "reason": "no manifest", "verification_report": None,
            "license_scan": None, "secret_scan": None}


DEFAULT_GATES = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}


def write_provenance_checker(repo_root, log, results, key_hash="sha256:" + "1" * 64,
                             key_gates=None):
    if key_gates is None:
        key_gates = dict(DEFAULT_GATES)
    d = Path(repo_root) / "gen" / "provenance-checker"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import copy\n"
        "import json\n"
        "LOG = " + repr(str(log)) + "\n"
        "RESULTS = " + repr(results) + "\n"
        "KEY_HASH = " + repr(key_hash) + "\n"
        "KEY_GATES = " + repr(key_gates) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps(entry, default=repr) + '\\n')\n"
        "\n"
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, spec_bundle_parts, gate_versions, assets, drivers):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.spec_bundle_parts = spec_bundle_parts\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "        self.drivers = drivers\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
        "    return ProvenanceKey(\n"
        "        KEY_HASH,\n"
        "        {'spec': 'sha256:' + '2' * 64, 'dependency_code': 'sha256:' + '3' * 64},\n"
        "        dict(KEY_GATES),\n"
        "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "          'adapter_sha256': 'sha256:' + 'a' * 64,\n"
        "          'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],\n"
        "        [],\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log({'call': 'check_provenance', 'component_id': component_id,\n"
        "          'spec_bundle_hash': spec_bundle_hash, 'gate_versions': gate_versions})\n"
        "    if component_id in RESULTS:\n"
        "        return copy.deepcopy(RESULTS[component_id])\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log({'call': 'check_sealed_provenance', 'component_id': component_id})\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )
    (d / "provenance_checker.py").write_text(src)


def write_impact_analyzer(repo_root, log, impacted, precondition_error=None):
    d = Path(repo_root) / "gen" / "impact-analyzer"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "import json\n"
        "LOG = " + repr(str(log)) + "\n"
        "IMPACTED = " + repr(impacted) + "\n"
        "PRECONDITION_ERROR = " + repr(precondition_error) + "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class ImpactedComponent:\n"
        "    component_id: str\n"
        "    reason: str\n"
        "    via: object = None\n"
        "    guarantee_ids: object = None\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def to_dict(self):\n"
        "        d = {'component_id': self.component_id, 'reason': self.reason, 'via': self.via}\n"
        "        if self.reason == 'transitive-guarantee':\n"
        "            d['guarantee_ids'] = list(self.guarantee_ids or [])\n"
        "        return d\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class BlastRadiusReport:\n"
        "    impacted: list\n"
        "    precondition_error: object = None\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'impacted': [i.to_dict() for i in self.impacted],\n"
        "                'precondition_error': self.precondition_error}\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'call': 'compute_blast_radius',\n"
        "                             'changed_ids': list(changed_ids)}) + '\\n')\n"
        "    return BlastRadiusReport(\n"
        "        [ImpactedComponent(e['component_id'], e['reason'], e['via'], e.get('guarantee_ids'))\n"
        "         for e in IMPACTED],\n"
        "        PRECONDITION_ERROR,\n"
        "    )\n"
    )
    (d / "impact_analyzer.py").write_text(src)


def write_secret_scanner(repo_root, log):
    d = Path(repo_root) / "gen" / "secret-scanner"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(str(repo_root) + '\\n')\n"
        "    return {'flagged': False, 'matches': []}\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
    )
    (d / "secret_scanner.py").write_text(src)


def write_gate_runner(repo_root, log):
    d = Path(repo_root) / "gen" / "component-gate-runner"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "def _log(name):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'call': name}) + '\\n')\n"
        "\n"
        "def run_gates(*args, **kwargs):\n"
        "    _log('run_gates')\n"
        "    raise RuntimeError('component-gate-runner must never be called')\n"
        "\n"
        "def __getattr__(name):\n"
        "    if name.startswith('__'):\n"
        "        raise AttributeError(name)\n"
        "    def _fn(*args, **kwargs):\n"
        "        _log(name)\n"
        "        raise RuntimeError('component-gate-runner must never be called')\n"
        "    return _fn\n"
    )
    (d / "component_gate_runner.py").write_text(src)


def write_capability_verifier(repo_root, log):
    d = Path(repo_root) / "gen" / "capability-scenario-verifier"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "LOG = " + repr(str(log)) + "\n"
        "GATE_VERSION = 'capability_scenario_verifier@3.0.0'\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _log(name, capability_id):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'call': name, 'capability_id': capability_id}) + '\\n')\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance', capability_id)\n"
        "    return {'hit': True, 'capability_scenario_report':\n"
        "            {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates', capability_id)\n"
        "    return {'hit': True, 'capability_scenario_report':\n"
        "            {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log('run_capability_scenarios', None)\n"
        "    return {}\n"
    )
    (d / "capability_scenario_verifier.py").write_text(src)


def setup_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "components").mkdir(parents=True)
    logs = tmp_path / "logs"
    logs.mkdir()
    paths = {
        "prov": logs / "provenance_checker.log",
        "impact": logs / "impact_analyzer.log",
        "secret": logs / "secret_scanner.log",
        "gate": logs / "gate_runner.log",
        "cap": logs / "capability.log",
    }
    write_secret_scanner(repo_root, paths["secret"])
    write_gate_runner(repo_root, paths["gate"])
    write_capability_verifier(repo_root, paths["cap"])
    return repo_root, paths


def calls(log, name):
    return [e for e in read_log(log) if e.get("call") == name]


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------

def test_blast_radius_hit_and_miss(tmp_path):
    repo_root, logs = setup_repo(tmp_path)
    write_component(repo_root, "alpha", "comp-alpha")
    write_component(repo_root, "beta", "comp-beta")
    write_impact_analyzer(repo_root, logs["impact"], [
        {"component_id": "comp-alpha", "reason": "direct", "via": None},
        {"component_id": "comp-beta", "reason": "transitive-interface", "via": "comp-alpha"},
    ])
    write_provenance_checker(repo_root, logs["prov"], {
        "comp-alpha": hit_result("comp-alpha"),
        "comp-beta": miss_result(),
    })

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert set(components.keys()) == {"comp-alpha", "comp-beta"}
    assert len(components) == 2
    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-beta" in r for r in reasons), reasons
    assert field(report, "ready") is False
    assert calls(logs["impact"], "compute_blast_radius"), "impact-analyzer was not called"
    assert read_log(logs["gate"]) == [], "component-gate-runner was called"


def test_precondition_error_makes_scope_unknown(tmp_path):
    repo_root, logs = setup_repo(tmp_path)
    write_component(repo_root, "alpha", "comp-alpha")
    error = "corpus did not pass spec-linter cleanly: 6 fail-severity finding(s)"
    write_impact_analyzer(repo_root, logs["impact"], [], precondition_error=error)
    write_provenance_checker(repo_root, logs["prov"], {"comp-alpha": hit_result("comp-alpha")})

    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == ["blast radius unavailable: " + error]
    assert len(field(report, "components")) == 0
    assert calls(logs["prov"], "check_provenance") == []
    assert read_log(logs["gate"]) == []


def test_whole_corpus_checks_every_component_by_frontmatter_id(tmp_path):
    repo_root, logs = setup_repo(tmp_path)
    write_component(repo_root, "alpha", "comp-alpha")
    write_component(repo_root, "beta", "comp-beta")
    write_provenance_checker(repo_root, logs["prov"], {
        "comp-alpha": hit_result("comp-alpha"),
        "comp-beta": hit_result("comp-beta"),
    })

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "scope") == "whole-corpus"
    checked = {e["component_id"] for e in calls(logs["prov"], "check_provenance")}
    assert checked == {"comp-alpha", "comp-beta"}
    assert set(field(report, "components").keys()) == {"comp-alpha", "comp-beta"}
    assert read_log(logs["gate"]) == []


def test_empty_corpus_without_gen_uses_tool_checker_and_is_ready(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "components").mkdir(parents=True)
    assert not (repo_root / "gen").exists()

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "scope") == "whole-corpus"
    assert len(field(report, "components")) == 0
    assert field(report, "ready") is True


def test_failing_verification_report_names_failed_requirement(tmp_path):
    repo_root, logs = setup_repo(tmp_path)
    write_component(repo_root, "foo", "comp-foo")
    write_provenance_checker(repo_root, logs["prov"], {
        "comp-foo": hit_result("comp-foo",
                               verification_report=failing_verification_report("comp-foo")),
    })

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    entries = [r for r in reasons if "comp-foo" in r and "verification" in r]
    assert entries, reasons
    for entry in entries:
        assert "R-FOO-002" in entry
        assert "R-FOO-001" not in entry
    assert read_log(logs["gate"]) == [], "component-gate-runner was called"


def test_blocked_license_scan_is_named(tmp_path):
    repo_root, logs = setup_repo(tmp_path)
    write_component(repo_root, "foo", "comp-foo")
    write_provenance_checker(repo_root, logs["prov"], {
        "comp-foo": hit_result("comp-foo", license=license_scan("comp-foo", blocked=True)),
    })

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-foo" in r and "license_scan" in r for r in reasons), reasons
    assert read_log(logs["gate"]) == []


def test_provenance_key_passed_unchanged_to_check_provenance(tmp_path):
    repo_root, logs = setup_repo(tmp_path)
    write_component(repo_root, "alpha", "comp-alpha")
    write_component(repo_root, "beta", "comp-beta")
    write_provenance_checker(
        repo_root, logs["prov"],
        {"comp-alpha": hit_result("comp-alpha"), "comp-beta": hit_result("comp-beta")},
        key_hash="sha256:k1",
        key_gates={"verifier": "v@1"},
    )

    provenance_tracker.check_readiness(repo_root)

    checks = calls(logs["prov"], "check_provenance")
    assert {e["component_id"] for e in checks} == {"comp-alpha", "comp-beta"}
    for entry in checks:
        assert entry["spec_bundle_hash"] == "sha256:k1"
        assert entry["gate_versions"] == {"verifier": "v@1"}
    assert read_log(logs["gate"]) == []