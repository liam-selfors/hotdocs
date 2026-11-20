# hotdocs-criterion: sha256:95cd6a758ebe323d47a772f328ee63fbfc0aa52d07b13193826fd02cc35db47e
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SEAL_HASH = "sha256:" + "0" * 64
PLAIN_HASH = "sha256:abc123"


def _component_md(comp_id, title, sealed):
    text = "---\n"
    text += "id: " + comp_id + "\n"
    text += "title: " + title + "\n"
    text += "status: draft\n"
    text += "owners: [pipeline-team]\n"
    text += "depends_on: []\n"
    if sealed:
        text += "sealed: true\n"
        text += "source_path: legacy/seal/\n"
    text += "---\n\n# " + title + "\n\nFixture component.\n"
    return text


def _write_component(repo_root, slug, comp_id, title, sealed, req_prefix):
    base = repo_root / "specs" / "components" / slug
    (base / "requirements").mkdir(parents=True, exist_ok=True)
    (base / "acceptance").mkdir(parents=True, exist_ok=True)
    (base / "interface").mkdir(parents=True, exist_ok=True)
    (base / "component.md").write_text(_component_md(comp_id, title, sealed))
    rid = "R-" + req_prefix + "-001"
    aid = "AC-" + req_prefix + "-001"
    (base / "requirements" / (rid + ".md")).write_text(
        "# " + rid + "\n\n**" + rid + "** — MUST do the thing.\n"
    )
    (base / "acceptance" / (aid + ".md")).write_text(
        "# " + aid + "\n\nCovers: " + rid + "\nKind: generated-test\n\nIt does the thing.\n"
    )
    (base / "interface" / "library.md").write_text("# Library\n\n```\nthing() -> None\n```\n")


def _checker_source(log_path, sealed_result_path):
    src = ""
    src += "import json\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += "SEALED_RESULT = " + repr(str(sealed_result_path)) + "\n"
    src += "SEAL_HASH = " + repr(SEAL_HASH) + "\n"
    src += "PLAIN_HASH = " + repr(PLAIN_HASH) + "\n"
    src += (
        "\n"
        "def _conv(a):\n"
        "    if isinstance(a, (str, int, float, bool, type(None), dict, list)):\n"
        "        return a\n"
        "    return str(a)\n"
        "\n"
        "def _log(name, *args):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'fn': name, 'args': [_conv(a) for a in args]}) + '\\n')\n"
        "\n"
        "class SealedKey:\n"
        "    def __init__(self, owners, source_path, source_hash, verifier_version):\n"
        "        self.owners = owners\n"
        "        self.source_path = source_path\n"
        "        self.source_hash = source_hash\n"
        "        self.verifier_version = verifier_version\n"
        "\n"
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "GATES = {\n"
        "    'compiler': 'criterion-compiler@1.0.0',\n"
        "    'generated_test': 'generated_test@1.0.0',\n"
        "    'verifier': 'verifier-orchestrator@2.0.0',\n"
        "    'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "    'secret_scanner': 'secret_scanner@0.0.0',\n"
        "    'generator': 'generator@3.0.0+v11',\n"
        "}\n"
        "\n"
        "ASSETS = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "           'adapter_sha256': 'sha256:aa', 'versions': {'python': '3.12.4'},\n"
        "           'lockfile_sha256': None}]\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id, repo_root)\n"
        "    if component_id == 'comp-seal':\n"
        "        return SealedKey(['pipeline-team'], 'legacy/seal/', SEAL_HASH,\n"
        "                         'verifier-orchestrator@2.0.0')\n"
        "    return None\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id, repo_root)\n"
        "    with open(SEALED_RESULT) as fh:\n"
        "        return json.load(fh)\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id, repo_root)\n"
        "    return ProvenanceKey(PLAIN_HASH, dict(GATES), [dict(a) for a in ASSETS])\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id, spec_bundle_hash, dict(gate_versions), repo_root)\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'reason': None,\n"
        "        'verification_report': {\n"
        "            'component_id': component_id,\n"
        "            'criteria': [{'id': 'AC-PLAIN-001', 'covers': 'R-PLAIN-001',\n"
        "                          'kind': 'generated-test', 'result': 'pass'}],\n"
        "            'requirement_results': {'R-PLAIN-001': 'pass'},\n"
        "            'interface_drift': False,\n"
        "            'mutation_score': 0.9,\n"
        "            'mutation_error': None,\n"
        "            'assets': [dict(a) for a in ASSETS],\n"
        "            'overall': 'pass',\n"
        "        },\n"
        "        'license_scan': {\n"
        "            'component_id': component_id,\n"
        "            'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',\n"
        "            'evaluated': True,\n"
        "            'reason': None,\n"
        "            'similarity_score': 0.1,\n"
        "            'block_threshold': 0.7,\n"
        "            'blocked': False,\n"
        "            'matches': [],\n"
        "            'notified': False,\n"
        "            'notification_delivery_error': None,\n"
        "            'cache_hit': False,\n"
        "        },\n"
        "        'secret_scan': {\n"
        "            'scope': 'full',\n"
        "            'gate_version': 'secret_scanner@0.0.0',\n"
        "            'flagged': False,\n"
        "            'matches': [],\n"
        "            'allowed': [],\n"
        "            'unused_allowlist_entries': [],\n"
        "            'notified': False,\n"
        "            'notification_delivery_error': None,\n"
        "            'cache_hit': False,\n"
        "        },\n"
        "    }\n"
    )
    return src


def _gate_runner_source(log_path):
    src = "import json\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += (
        "with open(LOG, 'a') as fh:\n"
        "    fh.write(json.dumps({'fn': 'LOADED component_gate_runner', 'args': []}) + '\\n')\n"
        "\n"
        "def run_component_gates(*args, **kwargs):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'fn': 'run_component_gates', 'args': []}) + '\\n')\n"
        "    raise RuntimeError('component-gate-runner must never be called')\n"
    )
    return src


def _capability_source(log_path):
    src = "import json\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += (
        "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "def _log(name, *args):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'fn': name, 'args': [str(a) for a in args]}) + '\\n')\n"
        "def _report(capability_id):\n"
        "    return {capability_id: {'overall': 'pass', 'scenarios': []}}\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance', capability_id)\n"
        "    return {'hit': True, 'capability_scenario_report': _report(capability_id)}\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates', capability_id)\n"
        "    return {'hit': True, 'capability_scenario_report': _report(capability_id)}\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log('run_capability_scenarios')\n"
        "    return {}\n"
    )
    return src


def _secret_scanner_source(log_path):
    src = "import json\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += (
        "with open(LOG, 'a') as fh:\n"
        "    fh.write(json.dumps({'fn': 'LOADED secret_scanner', 'args': []}) + '\\n')\n"
        "GATE_VERSION = 'secret_scanner@0.0.0'\n"
        "FLAGGED = {\n"
        "    'scope': 'full',\n"
        "    'gate_version': 'secret_scanner@0.0.0',\n"
        "    'flagged': True,\n"
        "    'matches': [{'rule_id': 'AWS Access Key', 'risk_tier': 'high',\n"
        "                 'file': 'legacy/seal/config.py', 'line': 1}],\n"
        "    'allowed': [],\n"
        "    'unused_allowlist_entries': [],\n"
        "    'notified': False,\n"
        "    'notification_delivery_error': None,\n"
        "    'cache_hit': True,\n"
        "}\n"
        "def gate_version(repo_root):\n"
        "    return GATE_VERSION\n"
        "def stored_result(repo_root):\n"
        "    return dict(FLAGGED)\n"
        "def read_stored_result(repo_root):\n"
        "    return dict(FLAGGED)\n"
        "def scan_repository(repo_root, *args, **kwargs):\n"
        "    return dict(FLAGGED)\n"
        "def scan(repo_root, *args, **kwargs):\n"
        "    return dict(FLAGGED)\n"
    )
    return src


def _setup(tmp_path, sealed_result, flagged_secret_scan=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    sealed_path = tmp_path / "sealed_result.json"
    sealed_path.write_text(json.dumps(sealed_result))

    _write_component(repo_root, "seal", "comp-seal", "Sealed Fixture", True, "SEAL")
    _write_component(repo_root, "plain", "comp-plain", "Plain Fixture", False, "PLAIN")

    def put(slug, module_name, source):
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(source)

    put("provenance-checker", "provenance_checker", _checker_source(log_path, sealed_path))
    put("component-gate-runner", "component_gate_runner", _gate_runner_source(log_path))
    put("capability-scenario-verifier", "capability_scenario_verifier", _capability_source(log_path))
    if flagged_secret_scan:
        put("secret-scanner", "secret_scanner", _secret_scanner_source(log_path))
        stored = repo_root / ".hotdocs"
        stored.mkdir(parents=True, exist_ok=True)
        (stored / "secret-scan.json").write_text(json.dumps({
            "scope": "full",
            "gate_version": "secret_scanner@0.0.0",
            "flagged": True,
            "matches": [{"rule_id": "AWS Access Key", "risk_tier": "high",
                         "file": "legacy/seal/config.py", "line": 1}],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": True,
        }))
    return repo_root, log_path


def _read_log(log_path):
    entries = []
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _ids_for(entries, fn):
    return [e["args"][0] for e in entries if e["fn"] == fn]


def _hit_sealed():
    return {
        "hit": True,
        "sealed": True,
        "reason": None,
        "verification_report": {"overall": "pass"},
        "license_scan": None,
        "secret_scan": None,
        "owners": ["pipeline-team"],
        "source_hash": SEAL_HASH,
        "written_at": "2026-11-02T00:00:00Z",
    }


def _assert_gate_runner_never_loaded(entries):
    names = [e["fn"] for e in entries]
    assert "LOADED component_gate_runner" not in names
    assert "run_component_gates" not in names


def test_sealed_hit_and_plain_hit_routed_correctly(tmp_path):
    faked = _hit_sealed()
    repo_root, log_path = _setup(tmp_path, faked)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True
    entries = _read_log(log_path)

    assert set(_ids_for(entries, "current_sealed_key")) == {"comp-seal", "comp-plain"}
    sealed_calls = _ids_for(entries, "check_sealed_provenance")
    assert sealed_calls and set(sealed_calls) == {"comp-seal"}
    prov_calls = _ids_for(entries, "check_provenance")
    assert prov_calls and set(prov_calls) == {"comp-plain"}
    key_calls = _ids_for(entries, "current_provenance_key")
    assert key_calls and set(key_calls) == {"comp-plain"}

    for e in entries:
        if e["fn"] == "check_provenance":
            assert e["args"][1] == PLAIN_HASH
            assert e["args"][2]["generator"] == "generator@3.0.0+v11"

    components = field(report, "components")
    assert components["comp-seal"] == faked

    _assert_gate_runner_never_loaded(entries)


def test_sealed_miss_reports_source_changed(tmp_path):
    miss = {
        "hit": False,
        "sealed": True,
        "reason": "source_changed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }
    repo_root, log_path = _setup(tmp_path, miss)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    seal_reasons = [r for r in reasons if "comp-seal" in r]
    assert seal_reasons == [
        "comp-seal: sealed provenance source_changed — run hotdocs generate comp-seal"
    ]
    assert len(reasons) == 1

    entries = _read_log(log_path)
    _assert_gate_runner_never_loaded(entries)


def test_sealed_readiness_ignores_flagged_secret_scan(tmp_path):
    faked = _hit_sealed()
    repo_root, log_path = _setup(tmp_path, faked, flagged_secret_scan=True)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True
    reasons = list(field(report, "not_ready_reasons"))
    assert [r for r in reasons if "comp-seal" in r] == []
    components = field(report, "components")
    assert components["comp-seal"] == faked

    entries = _read_log(log_path)
    _assert_gate_runner_never_loaded(entries)