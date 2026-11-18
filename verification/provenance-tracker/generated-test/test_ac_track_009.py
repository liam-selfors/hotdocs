# hotdocs-criterion: sha256:3555d5a4a5442dff6cb3d57495929c533629ec3547e20ce0dfc7e88e478102e3
import json
from pathlib import Path

import provenance_tracker


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def keys_of(mapping):
    if isinstance(mapping, dict):
        return set(mapping.keys())
    return set(dict(mapping).keys())


def read_log(path):
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def write_component(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    d.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug.capitalize() + " component\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n\n"
        + "# " + slug.capitalize() + "\n\n"
        + "A fixture component.\n"
    )
    (d / "component.md").write_text(text)


def verification_report(component_id, requirement_results):
    criteria = []
    n = 0
    for rid, res in requirement_results.items():
        n += 1
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
    overall = "fail" if any(v == "fail" for v in requirement_results.values()) else "pass"
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(requirement_results),
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
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
        "matches": (
            [{"reference_id": "ref-1", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.9}]
            if blocked else []
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


def hit(component_id, requirement_results=None, license_blocked=False):
    if requirement_results is None:
        requirement_results = {"R-FOO-001": "pass"}
    return {
        "hit": True,
        "verification_report": verification_report(component_id, requirement_results),
        "license_scan": license_scan(component_id, blocked=license_blocked),
        "secret_scan": secret_scan(),
    }


def miss():
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


PROVENANCE_CHECKER_BODY = (
    "import json\n"
    "\n"
    "def _cfg():\n"
    "    with open(CONFIG) as f:\n"
    "        return json.load(f)\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "class ProvenanceKey(dict):\n"
    "    def __getattr__(self, name):\n"
    "        try:\n"
    "            return self[name]\n"
    "        except KeyError:\n"
    "            raise AttributeError(name)\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'fn': 'current_sealed_key', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'fn': 'current_provenance_key', 'component_id': component_id})\n"
    "    c = _cfg()\n"
    "    return ProvenanceKey(spec_bundle_hash=c['key']['spec_bundle_hash'],\n"
    "                         gate_versions=dict(c['key']['gate_versions']))\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    try:\n"
    "        gv = dict(gate_versions)\n"
    "    except Exception:\n"
    "        gv = repr(gate_versions)\n"
    "    _log({'fn': 'check_provenance', 'component_id': component_id,\n"
    "          'spec_bundle_hash': spec_bundle_hash, 'gate_versions': gv})\n"
    "    c = _cfg()\n"
    "    r = c['results'].get(component_id)\n"
    "    if r is None:\n"
    "        r = {'hit': False, 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    "    return json.loads(json.dumps(r))\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'fn': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

IMPACT_ANALYZER_BODY = (
    "import json\n"
    "\n"
    "def compute_blast_radius(changed_ids, repo_root):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps({'fn': 'compute_blast_radius', 'changed_ids': list(changed_ids)}) + '\\n')\n"
    "    with open(CONFIG) as f:\n"
    "        c = json.load(f)\n"
    "    return {'impacted': c['impacted'], 'precondition_error': None}\n"
)

GATE_RUNNER_BODY = (
    "import json\n"
    "\n"
    "def _log(name):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps({'fn': name}) + '\\n')\n"
    "\n"
    "def run_component_gates(*args, **kwargs):\n"
    "    _log('run_component_gates')\n"
    "    raise RuntimeError('component-gate-runner must never be called')\n"
)

CAPABILITY_BODY = (
    "import json\n"
    "\n"
    "GATE_VERSION = 'capability_scenario_verifier@2.0.0'\n"
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
    "def check_capability_provenance(capability_id, repo_root):\n"
    "    _log('check_capability_provenance', capability_id)\n"
    "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    "\n"
    "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
    "    _log('run_capability_gates', capability_id)\n"
    "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    "\n"
    "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
    "    _log('run_capability_scenarios', None)\n"
    "    return {}\n"
)


def write_fake(repo_root, slug, module_name, body, config_path, log_path):
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "CONFIG = " + repr(str(config_path)) + "\n"
        + "LOG = " + repr(str(log_path)) + "\n"
        + body
    )
    (d / (module_name + ".py")).write_text(src)


def setup_repo(tmp_path, slugs, results, impacted=None, key=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for s in slugs:
        write_component(repo_root, s)
    logs = tmp_path / "logs"
    logs.mkdir()
    if key is None:
        key = {"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}}
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "results": results,
        "key": key,
        "impacted": impacted or [],
    }))
    paths = {
        "prov": logs / "provenance_checker.log",
        "impact": logs / "impact_analyzer.log",
        "gate": logs / "component_gate_runner.log",
        "cap": logs / "capability.log",
    }
    write_fake(repo_root, "provenance-checker", "provenance_checker",
               PROVENANCE_CHECKER_BODY, cfg, paths["prov"])
    write_fake(repo_root, "impact-analyzer", "impact_analyzer",
               IMPACT_ANALYZER_BODY, cfg, paths["impact"])
    write_fake(repo_root, "component-gate-runner", "component_gate_runner",
               GATE_RUNNER_BODY, cfg, paths["gate"])
    write_fake(repo_root, "capability-scenario-verifier", "capability_scenario_verifier",
               CAPABILITY_BODY, cfg, paths["cap"])
    return repo_root, paths


def check_calls(paths):
    return [e for e in read_log(paths["prov"]) if e.get("fn") == "check_provenance"]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_blast_radius_hit_and_miss(tmp_path):
    results = {"comp-alpha": hit("comp-alpha"), "comp-beta": miss()}
    impacted = [
        {"component_id": "comp-alpha", "reason": "direct", "via": None},
        {"component_id": "comp-beta", "reason": "transitive-interface", "via": "comp-alpha"},
    ]
    repo_root, paths = setup_repo(
        tmp_path, ["alpha", "beta", "gamma"], results, impacted=impacted)

    report = provenance_tracker.check_readiness(repo_root, ["comp-alpha"])

    assert field(report, "scope") == "blast-radius"
    comps = field(report, "components")
    assert keys_of(comps) == {"comp-alpha", "comp-beta"}
    reasons = list(field(report, "not_ready_reasons"))
    assert any("comp-beta" in str(r) for r in reasons), reasons
    assert field(report, "ready") is False
    assert read_log(paths["gate"]) == []


def test_whole_corpus_checks_every_component(tmp_path):
    results = {
        "comp-alpha": hit("comp-alpha"),
        "comp-beta": hit("comp-beta"),
        "comp-gamma": hit("comp-gamma"),
    }
    repo_root, paths = setup_repo(tmp_path, ["alpha", "beta", "gamma"], results)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "scope") == "whole-corpus"
    checked = {e["component_id"] for e in check_calls(paths)}
    assert checked == {"comp-alpha", "comp-beta", "comp-gamma"}
    assert keys_of(field(report, "components")) == {"comp-alpha", "comp-beta", "comp-gamma"}
    assert read_log(paths["gate"]) == []


def test_failing_verification_report_not_ready(tmp_path):
    results = {
        "comp-alpha": hit("comp-alpha", {"R-FOO-001": "pass", "R-FOO-002": "fail"}),
    }
    repo_root, paths = setup_repo(tmp_path, ["alpha"], results)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = [str(r) for r in field(report, "not_ready_reasons")]
    matching = [
        r for r in reasons
        if "comp-alpha" in r and "verification" in r and "R-FOO-002" in r
    ]
    assert matching, reasons
    assert read_log(paths["gate"]) == []


def test_blocked_license_scan_reason(tmp_path):
    results = {"comp-alpha": hit("comp-alpha", license_blocked=True)}
    repo_root, paths = setup_repo(tmp_path, ["alpha"], results)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = [str(r) for r in field(report, "not_ready_reasons")]
    matching = [r for r in reasons if "comp-alpha" in r and "license_scan" in r]
    assert matching, reasons
    assert read_log(paths["gate"]) == []


def test_provenance_key_passed_unchanged(tmp_path):
    results = {"comp-alpha": hit("comp-alpha"), "comp-beta": hit("comp-beta")}
    key = {"spec_bundle_hash": "sha256:k1", "gate_versions": {"verifier": "v@1"}}
    repo_root, paths = setup_repo(tmp_path, ["alpha", "beta"], results, key=key)

    provenance_tracker.check_readiness(repo_root)

    calls = check_calls(paths)
    assert {c["component_id"] for c in calls} == {"comp-alpha", "comp-beta"}
    for c in calls:
        assert c["spec_bundle_hash"] == "sha256:k1"
        assert c["gate_versions"] == {"verifier": "v@1"}
    assert read_log(paths["gate"]) == []