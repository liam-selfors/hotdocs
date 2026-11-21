# hotdocs-criterion: sha256:fe6616deb8abba09150101436c0467086d6b285bf09c3d6b8147c5286484e805
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PASSING_REPORT = {
    "component_id": "comp-x",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
                "lockfile_sha256": None}],
    "overall": "pass",
}


def make_report(component_id, requirement_results):
    overall = "fail" if "fail" in requirement_results.values() else "pass"
    criteria = []
    n = 0
    for rid, res in requirement_results.items():
        n += 1
        entry = {"id": "AC-X-" + str(n).zfill(3), "covers": rid,
                 "kind": "compiled", "result": res}
        if res == "fail":
            entry["failure_detail"] = {"message": "failed", "expected": 1, "actual": 2}
            entry["failure_origin"] = "implementation"
        criteria.append(entry)
    report = dict(PASSING_REPORT)
    report["component_id"] = component_id
    report["criteria"] = criteria
    report["requirement_results"] = dict(requirement_results)
    report["overall"] = overall
    return report


def make_license(component_id, blocked=False):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9 if blocked else 0.1,
        "block_threshold": 0.7,
        "blocked": blocked,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def make_secret():
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


def make_hit(component_id, requirement_results=None, license_blocked=False):
    if requirement_results is None:
        requirement_results = {"R-X-001": "pass"}
    return {
        "hit": True,
        "reason": None,
        "verification_report": make_report(component_id, requirement_results),
        "license_scan": make_license(component_id, license_blocked),
        "secret_scan": make_secret(),
    }


def make_miss(reason="no manifest"):
    return {
        "hit": False,
        "reason": reason,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def write_file(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo_root, slug):
    text = (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: Component " + slug + "\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n\n"
        "# Component " + slug + "\n"
    )
    write_file(repo_root / "specs" / "components" / slug / "component.md", text)


def write_provenance_checker(repo_root, log_path, results,
                             key_hash="sha256:abc123",
                             key_gv=None):
    if key_gv is None:
        key_gv = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.0.0+v11",
        }
    lines = [
        "import copy",
        "import json",
        "LOG = " + repr(str(log_path)),
        "RESULTS = " + repr(results),
        "MISS = " + repr(make_miss()),
        "KEY_HASH = " + repr(key_hash),
        "KEY_GV = " + repr(key_gv),
        "",
        "def _log(entry):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps(entry) + '\\n')",
        "",
        "class ProvenanceKey:",
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):",
        "        self.spec_bundle_hash = spec_bundle_hash",
        "        self.gate_versions = gate_versions",
        "        self.assets = assets",
        "    def __getitem__(self, name):",
        "        return getattr(self, name)",
        "",
        "def current_sealed_key(component_id, repo_root):",
        "    _log({'fn': 'current_sealed_key', 'component_id': component_id})",
        "    return None",
        "",
        "def current_provenance_key(component_id, repo_root):",
        "    _log({'fn': 'current_provenance_key', 'component_id': component_id})",
        "    assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,",
        "               'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},",
        "               'lockfile_sha256': None}]",
        "    return ProvenanceKey(KEY_HASH, dict(KEY_GV), assets)",
        "",
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):",
        "    _log({'fn': 'check_provenance', 'component_id': component_id,",
        "          'spec_bundle_hash': spec_bundle_hash,",
        "          'gate_versions': dict(gate_versions)})",
        "    return copy.deepcopy(RESULTS.get(component_id, MISS))",
        "",
        "def check_sealed_provenance(component_id, repo_root):",
        "    _log({'fn': 'check_sealed_provenance', 'component_id': component_id})",
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',",
        "            'verification_report': None, 'license_scan': None,",
        "            'secret_scan': None, 'owners': None, 'source_hash': None,",
        "            'written_at': None}",
        "",
    ]
    write_file(repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
               "\n".join(lines))


def write_impact_analyzer(repo_root, log_path, impacted, precondition_error):
    lines = [
        "import json",
        "LOG = " + repr(str(log_path)),
        "IMPACTED = " + repr(impacted),
        "PRECONDITION_ERROR = " + repr(precondition_error),
        "",
        "def _log(entry):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps(entry) + '\\n')",
        "",
        "class ImpactedComponent:",
        "    def __init__(self, component_id, reason, via, guarantee_ids=None):",
        "        self.component_id = component_id",
        "        self.reason = reason",
        "        self.via = via",
        "        self.guarantee_ids = guarantee_ids",
        "    def __getitem__(self, name):",
        "        return getattr(self, name)",
        "    def to_dict(self):",
        "        d = {'component_id': self.component_id, 'reason': self.reason, 'via': self.via}",
        "        if self.reason == 'transitive-guarantee':",
        "            d['guarantee_ids'] = list(self.guarantee_ids or [])",
        "        return d",
        "",
        "class BlastRadiusReport:",
        "    def __init__(self, impacted, precondition_error):",
        "        self.impacted = impacted",
        "        self.precondition_error = precondition_error",
        "    def __getitem__(self, name):",
        "        return getattr(self, name)",
        "    def to_dict(self):",
        "        return {'impacted': [i.to_dict() for i in self.impacted],",
        "                'precondition_error': self.precondition_error}",
        "",
        "def compute_blast_radius(changed_ids, repo_root):",
        "    _log({'fn': 'compute_blast_radius', 'changed_ids': list(changed_ids)})",
        "    items = [ImpactedComponent(e['component_id'], e['reason'], e['via'],",
        "                               e.get('guarantee_ids')) for e in IMPACTED]",
        "    return BlastRadiusReport(items, PRECONDITION_ERROR)",
        "",
    ]
    write_file(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
               "\n".join(lines))


def write_gate_runner(repo_root, log_path):
    lines = [
        "import json",
        "LOG = " + repr(str(log_path)),
        "",
        "def _log(entry):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps(entry) + '\\n')",
        "",
        "_log({'fn': 'module-loaded'})",
        "",
        "def run_component_gates(*args, **kwargs):",
        "    _log({'fn': 'run_component_gates'})",
        "    raise RuntimeError('component-gate-runner must never be called')",
        "",
    ]
    write_file(repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py",
               "\n".join(lines))


def write_capability_verifier(repo_root, log_path):
    lines = [
        "import json",
        "LOG = " + repr(str(log_path)),
        "GATE_VERSION = 'capability_scenario_verifier@2.2.0'",
        "",
        "class UnknownCapabilityError(ValueError):",
        "    pass",
        "",
        "class ModelRequiredError(ValueError):",
        "    pass",
        "",
        "def _log(entry):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps(entry) + '\\n')",
        "",
        "def _report(capability_id):",
        "    return {capability_id: {'overall': 'pass', 'scenarios': []}}",
        "",
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):",
        "    _log({'fn': 'run_capability_scenarios'})",
        "    return {}",
        "",
        "def check_capability_provenance(capability_id, repo_root):",
        "    _log({'fn': 'check_capability_provenance', 'capability_id': capability_id})",
        "    return {'hit': True, 'capability_scenario_report': _report(capability_id)}",
        "",
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):",
        "    _log({'fn': 'run_capability_gates', 'capability_id': capability_id})",
        "    return {'hit': False, 'capability_scenario_report': _report(capability_id)}",
        "",
    ]
    write_file(repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
               "\n".join(lines))


def setup_repo(tmp_path, results, impacted=None, precondition_error=None,
               slugs=(), key_hash="sha256:abc123", key_gv=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = {
        "prov": tmp_path / "prov.log",
        "impact": tmp_path / "impact.log",
        "gate": tmp_path / "gate.log",
        "cap": tmp_path / "cap.log",
    }
    for slug in slugs:
        write_component(repo_root, slug)
    write_provenance_checker(repo_root, logs["prov"], results, key_hash, key_gv)
    write_impact_analyzer(repo_root, logs["impact"], impacted or [], precondition_error)
    write_gate_runner(repo_root, logs["gate"])
    write_capability_verifier(repo_root, logs["cap"])
    return repo_root, logs


def read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def calls(path, fn):
    return [e for e in read_log(path) if e.get("fn") == fn]


def assert_gate_runner_never_called(logs):
    assert calls(logs["gate"], "run_component_gates") == []


def test_blast_radius_hit_and_miss(tmp_path):
    results = {"comp-alpha": make_hit("comp-alpha"), "comp-beta": make_miss("no manifest")}
    impacted = [
        {"component_id": "comp-alpha", "reason": "direct", "via": None},
        {"component_id": "comp-beta", "reason": "transitive-interface", "via": "comp-alpha"},
    ]
    repo_root, logs = setup_repo(tmp_path, results, impacted=impacted,
                                 slugs=("alpha", "beta"))
    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "scope") == "blast-radius"
    components = field(report, "components")
    assert set(components.keys()) == {"comp-alpha", "comp-beta"}
    assert len(components) == 2
    reasons = field(report, "not_ready_reasons")
    assert any("comp-beta" in r for r in reasons)
    assert field(report, "ready") is False
    assert_gate_runner_never_called(logs)


def test_precondition_error_makes_scope_unknown(tmp_path):
    err = "corpus did not pass spec-linter cleanly: 6 fail-severity finding(s)"
    results = {"comp-alpha": make_hit("comp-alpha")}
    repo_root, logs = setup_repo(tmp_path, results, impacted=[],
                                 precondition_error=err, slugs=("alpha",))
    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == ["blast radius unavailable: " + err]
    assert len(field(report, "components")) == 0
    assert calls(logs["prov"], "check_provenance") == []
    assert_gate_runner_never_called(logs)


def test_no_changed_ids_checks_whole_corpus(tmp_path):
    results = {"comp-alpha": make_hit("comp-alpha"), "comp-beta": make_hit("comp-beta")}
    repo_root, logs = setup_repo(tmp_path, results, slugs=("alpha", "beta"))
    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "scope") == "whole-corpus"
    checked = {e["component_id"] for e in calls(logs["prov"], "check_provenance")}
    assert checked == {"comp-alpha", "comp-beta"}
    assert set(field(report, "components").keys()) == {"comp-alpha", "comp-beta"}
    assert_gate_runner_never_called(logs)


def test_failing_verification_report_is_not_ready(tmp_path):
    results = {"comp-foo": make_hit("comp-foo", {"R-FOO-001": "pass", "R-FOO-002": "fail"})}
    repo_root, logs = setup_repo(tmp_path, results, slugs=("foo",))
    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = field(report, "not_ready_reasons")
    matching = [r for r in reasons
                if "comp-foo" in r and "verification" in r and "R-FOO-002" in r]
    assert matching, reasons
    assert_gate_runner_never_called(logs)


def test_blocking_license_scan_is_named(tmp_path):
    results = {"comp-foo": make_hit("comp-foo", {"R-FOO-001": "pass"}, license_blocked=True)}
    repo_root, logs = setup_repo(tmp_path, results, slugs=("foo",))
    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = field(report, "not_ready_reasons")
    assert any("license_scan" in r for r in reasons), reasons
    assert_gate_runner_never_called(logs)


def test_provenance_key_passed_through_unchanged(tmp_path):
    results = {"comp-alpha": make_hit("comp-alpha"), "comp-beta": make_hit("comp-beta")}
    repo_root, logs = setup_repo(tmp_path, results, slugs=("alpha", "beta"),
                                 key_hash="sha256:k1", key_gv={"verifier": "v@1"})
    provenance_tracker.check_readiness(repo_root)

    checks = calls(logs["prov"], "check_provenance")
    assert {e["component_id"] for e in checks} == {"comp-alpha", "comp-beta"}
    for entry in checks:
        assert entry["spec_bundle_hash"] == "sha256:k1"
        assert entry["gate_versions"] == {"verifier": "v@1"}
    assert_gate_runner_never_called(logs)