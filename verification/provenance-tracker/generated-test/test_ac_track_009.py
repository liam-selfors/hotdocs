# hotdocs-criterion: sha256:e5cd0ee38f623d91ccc6ef2047d354c974cfb3de3b980b8bfb4ea1ffa544d57c
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_COMMON = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "_ROOT = Path(__file__).resolve().parents[2]\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(_ROOT / 'fake_log.jsonl', 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry, default=repr) + '\\n')\n"
    "\n"
    "\n"
    "def _config():\n"
    "    return json.loads((_ROOT / 'fake_config.json').read_text(encoding='utf-8'))\n"
    "\n"
)

FAKE_PROVENANCE_CHECKER = FAKE_COMMON + (
    "\n"
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'fn': 'current_sealed_key', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'fn': 'current_provenance_key', 'component_id': component_id})\n"
    "    key = _config()['key']\n"
    "    assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "               'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "               'lockfile_sha256': None}]\n"
    "    return ProvenanceKey(key['spec_bundle_hash'], dict(key['gate_versions']), assets)\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'fn': 'check_provenance', 'component_id': component_id,\n"
    "          'spec_bundle_hash': spec_bundle_hash, 'gate_versions': gate_versions})\n"
    "    results = _config()['results']\n"
    "    if component_id in results:\n"
    "        return dict(results[component_id])\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'fn': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

FAKE_IMPACT_ANALYZER = FAKE_COMMON + (
    "\n"
    "class ImpactedComponent:\n"
    "    def __init__(self, component_id, reason, via, guarantee_ids=None):\n"
    "        self.component_id = component_id\n"
    "        self.reason = reason\n"
    "        self.via = via\n"
    "        self.guarantee_ids = guarantee_ids\n"
    "\n"
    "    def __getitem__(self, name):\n"
    "        return getattr(self, name)\n"
    "\n"
    "    def to_dict(self):\n"
    "        d = {'component_id': self.component_id, 'reason': self.reason, 'via': self.via}\n"
    "        if self.reason == 'transitive-guarantee':\n"
    "            d['guarantee_ids'] = list(self.guarantee_ids or [])\n"
    "        return d\n"
    "\n"
    "\n"
    "class BlastRadiusReport:\n"
    "    def __init__(self, impacted, precondition_error):\n"
    "        self.impacted = impacted\n"
    "        self.precondition_error = precondition_error\n"
    "\n"
    "    def __getitem__(self, name):\n"
    "        return getattr(self, name)\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'impacted': [i.to_dict() for i in self.impacted],\n"
    "                'precondition_error': self.precondition_error}\n"
    "\n"
    "\n"
    "def compute_blast_radius(changed_ids, repo_root):\n"
    "    _log({'fn': 'compute_blast_radius', 'changed_ids': list(changed_ids)})\n"
    "    impact = _config()['impact']\n"
    "    impacted = [ImpactedComponent(e['component_id'], e['reason'], e['via'],\n"
    "                                  e.get('guarantee_ids'))\n"
    "                for e in impact['impacted']]\n"
    "    return BlastRadiusReport(impacted, impact['precondition_error'])\n"
)

FAKE_GATE_RUNNER = FAKE_COMMON + (
    "\n"
    "_log({'fn': 'component_gate_runner_loaded'})\n"
    "\n"
    "\n"
    "def __getattr__(name):\n"
    "    if name.startswith('__'):\n"
    "        raise AttributeError(name)\n"
    "\n"
    "    def _called(*args, **kwargs):\n"
    "        _log({'fn': 'component_gate_runner_called', 'name': name})\n"
    "        raise RuntimeError('component-gate-runner must never be called')\n"
    "\n"
    "    return _called\n"
)

FAKE_SECRET_SCANNER = FAKE_COMMON + (
    "\n"
    "def scan(repo_root):\n"
    "    _log({'fn': 'secret_scan', 'repo_root': str(repo_root)})\n"
    "    return {'flagged': False, 'matches': []}\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
)

FAKE_CAPABILITY_VERIFIER = FAKE_COMMON + (
    "\n"
    "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
    "\n"
    "\n"
    "class UnknownCapabilityError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "class ModelRequiredError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "def check_capability_provenance(capability_id, repo_root):\n"
    "    _log({'fn': 'check_capability_provenance', 'capability_id': capability_id})\n"
    "    return {'hit': True, 'capability_scenario_report':\n"
    "            {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    "\n"
    "\n"
    "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
    "    _log({'fn': 'run_capability_gates', 'capability_id': capability_id})\n"
    "    return {'hit': True, 'capability_scenario_report':\n"
    "            {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    "\n"
    "\n"
    "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
    "    return {}\n"
)


DEFAULT_KEY = {
    "spec_bundle_hash": "sha256:abc123",
    "gate_versions": {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
        "secret_scanner": "secret_scanner@0.0.0",
        "generator": "generator@3.0.0+v11",
    },
}


def verification_report(component_id, requirement_results):
    overall = "fail" if "fail" in requirement_results.values() else "pass"
    criteria = []
    for i, (rid, res) in enumerate(sorted(requirement_results.items()), start=1):
        crit = {
            "id": "AC-FOO-" + str(i).zfill(3),
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            crit["failure_detail"] = {"message": "failed", "expected": 1, "actual": 2}
            crit["failure_origin"] = "implementation"
        criteria.append(crit)
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(requirement_results),
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [{
            "kind": "python", "path": ".", "definition_sha256": None,
            "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }],
        "overall": overall,
    }


def license_scan(component_id, blocked=False):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.9 if blocked else 0.1,
        "block_threshold": 0.7,
        "blocked": blocked,
        "matches": [{"reference_id": "ref-1", "license_family": "gpl-3.0",
                     "risk_tier": "high", "score": 0.9}] if blocked else [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def stored_secret_scan():
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


def hit(component_id, requirement_results=None, blocked=False):
    if requirement_results is None:
        requirement_results = {"R-FOO-001": "pass"}
    return {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(component_id, requirement_results),
        "license_scan": license_scan(component_id, blocked=blocked),
        "secret_scan": stored_secret_scan(),
    }


def write_component(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "A fixture component.\n"
    )
    (d / "component.md").write_text(text, encoding="utf-8")


def build_repo(repo_root, slugs, results, key=None, impact=None):
    (repo_root / "specs" / "components").mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        write_component(repo_root, slug)
    config = {
        "results": results,
        "key": key if key is not None else DEFAULT_KEY,
        "impact": impact if impact is not None else {"impacted": [], "precondition_error": None},
    }
    (repo_root / "fake_config.json").write_text(json.dumps(config), encoding="utf-8")
    fakes = {
        "provenance-checker": FAKE_PROVENANCE_CHECKER,
        "impact-analyzer": FAKE_IMPACT_ANALYZER,
        "component-gate-runner": FAKE_GATE_RUNNER,
        "secret-scanner": FAKE_SECRET_SCANNER,
        "capability-scenario-verifier": FAKE_CAPABILITY_VERIFIER,
    }
    for slug, source in fakes.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")
    return repo_root


def read_log(repo_root):
    path = repo_root / "fake_log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def gate_runner_entries(repo_root):
    return [e for e in read_log(repo_root) if e["fn"].startswith("component_gate_runner")]


def check_calls(repo_root):
    return [e for e in read_log(repo_root) if e["fn"] == "check_provenance"]


def test_blast_radius_hit_and_miss(tmp_path):
    repo_root = build_repo(
        tmp_path,
        ["alpha", "beta"],
        {"comp-alpha": hit("comp-alpha")},
        impact={
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
    assert set(dict(components).keys()) == {"comp-alpha", "comp-beta"}
    assert len(dict(components)) == 2
    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-beta" in r for r in reasons), reasons
    assert gate_runner_entries(repo_root) == []


def test_precondition_error_means_scope_unknown(tmp_path):
    err = "corpus did not pass spec-linter cleanly: 6 fail-severity finding(s)"
    repo_root = build_repo(
        tmp_path,
        ["alpha", "beta"],
        {"comp-alpha": hit("comp-alpha"), "comp-beta": hit("comp-beta")},
        impact={"impacted": [], "precondition_error": err},
    )
    report = provenance_tracker.check_readiness(repo_root, changed_ids=["comp-alpha"])

    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == ["blast radius unavailable: " + err]
    assert len(dict(field(report, "components"))) == 0
    assert check_calls(repo_root) == []
    assert gate_runner_entries(repo_root) == []


def test_no_changed_ids_checks_whole_corpus(tmp_path):
    repo_root = build_repo(
        tmp_path,
        ["alpha", "beta"],
        {"comp-alpha": hit("comp-alpha"), "comp-beta": hit("comp-beta")},
    )
    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "scope") == "whole-corpus"
    checked = {e["component_id"] for e in check_calls(repo_root)}
    assert checked == {"comp-alpha", "comp-beta"}
    assert set(dict(field(report, "components")).keys()) == {"comp-alpha", "comp-beta"}
    assert not any(e["fn"] == "compute_blast_radius" for e in read_log(repo_root))
    assert gate_runner_entries(repo_root) == []


def test_empty_corpus_without_gen_uses_tool_provenance_checker(tmp_path):
    repo_root = tmp_path
    (repo_root / "specs" / "components").mkdir(parents=True)
    assert not (repo_root / "gen").exists()

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True
    assert field(report, "scope") == "whole-corpus"
    assert len(dict(field(report, "components"))) == 0


def test_failing_verification_report_names_failed_requirements(tmp_path):
    repo_root = build_repo(
        tmp_path,
        ["foo"],
        {"comp-foo": hit("comp-foo", {"R-FOO-001": "pass", "R-FOO-002": "fail"})},
    )
    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    mine = [r for r in reasons if "comp-foo" in r]
    assert mine, reasons
    assert any("verification" in r and "R-FOO-002" in r for r in mine), mine
    assert not any("R-FOO-001" in r for r in mine), mine
    assert gate_runner_entries(repo_root) == []


def test_blocked_license_scan_is_named(tmp_path):
    repo_root = build_repo(
        tmp_path,
        ["foo"],
        {"comp-foo": hit("comp-foo", {"R-FOO-001": "pass"}, blocked=True)},
    )
    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    mine = [r for r in reasons if "comp-foo" in r]
    assert any("license_scan" in r for r in mine), reasons
    assert gate_runner_entries(repo_root) == []


def test_provenance_key_passed_unchanged(tmp_path):
    repo_root = build_repo(
        tmp_path,
        ["alpha", "beta"],
        {"comp-alpha": hit("comp-alpha"), "comp-beta": hit("comp-beta")},
        key={"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}},
    )
    provenance_tracker.check_readiness(repo_root)

    calls = check_calls(repo_root)
    assert {e["component_id"] for e in calls} == {"comp-alpha", "comp-beta"}
    for e in calls:
        assert e["spec_bundle_hash"] == "sha256:k1"
        assert e["gate_versions"] == {"verifier": "v@1"}