# hotdocs-criterion: sha256:2aaa867dab99e441ae931c128301706261de8a6562fc48a21b882bb50f9e1b2c
import copy
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SEAL_HASH = "sha256:" + "0" * 64

SEALED_HIT = {
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

SEALED_MISS = {
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

PLAIN_HASH = "sha256:" + "a" * 64

PLAIN_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
}

PLAIN_HIT = {
    "hit": True,
    "verification_report": {
        "component_id": "comp-plain",
        "criteria": [
            {"id": "AC-PLAIN-001", "covers": "R-PLAIN-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-PLAIN-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "overall": "pass",
    },
    "license_scan": {
        "component_id": "comp-plain",
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
    },
    "secret_scan": {
        "scope": "full",
        "gate_version": "secret_scanner@0.0.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    },
}

FLAGGED_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@0.0.0",
    "flagged": True,
    "matches": [
        {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "legacy/seal/config.py", "line": 3},
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


LOG_HELPERS = (
    "import json\n"
    "import copy\n"
    "\n"
    "class _Obj:\n"
    "    def __init__(self, **kw):\n"
    "        self.__dict__.update(kw)\n"
    "\n"
    "def _log(name, *args):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps([name] + [a if isinstance(a, (str, int, dict, list, type(None))) else str(a) for a in args]) + '\\n')\n"
    "\n"
)

CHECKER_BODY = (
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id, str(repo_root))\n"
    "    if component_id == 'comp-seal':\n"
    "        return _Obj(owners=['pipeline-team'], source_path='legacy/seal/', source_hash=SEAL_HASH, verifier_version='verifier-orchestrator@2.0.0')\n"
    "    return None\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id, str(repo_root))\n"
    "    return copy.deepcopy(SEALED_RESULT)\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id, str(repo_root))\n"
    "    return _Obj(spec_bundle_hash=PLAIN_HASH, gate_versions=dict(PLAIN_GATE_VERSIONS))\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id, spec_bundle_hash, dict(gate_versions), str(repo_root))\n"
    "    if component_id == 'comp-plain':\n"
    "        return copy.deepcopy(PLAIN_HIT)\n"
    "    return {'hit': False, 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
)

GATE_RUNNER_BODY = (
    "_log('component_gate_runner_loaded')\n"
    "\n"
    "def run_component_gates(*args, **kwargs):\n"
    "    _log('run_component_gates')\n"
    "    raise RuntimeError('component-gate-runner must never be called')\n"
)

CAPABILITY_BODY = (
    "GATE_VERSION = 'capability_scenario_verifier@2.0.0'\n"
    "\n"
    "class UnknownCapabilityError(ValueError):\n"
    "    pass\n"
    "\n"
    "class ModelRequiredError(ValueError):\n"
    "    pass\n"
    "\n"
    "def check_capability_provenance(capability_id, repo_root):\n"
    "    _log('check_capability_provenance', capability_id, str(repo_root))\n"
    "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    "\n"
    "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
    "    _log('run_capability_gates', capability_id, str(repo_root))\n"
    "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
    "\n"
    "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
    "    _log('run_capability_scenarios', str(repo_root))\n"
    "    return {}\n"
)

SECRET_BODY = (
    "def gate_version(repo_root):\n"
    "    _log('secret_gate_version', str(repo_root))\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def scan_repo(repo_root, *args, **kwargs):\n"
    "    _log('secret_scan_repo', str(repo_root))\n"
    "    return copy.deepcopy(FLAGGED)\n"
    "\n"
    "def scan_files(*args, **kwargs):\n"
    "    _log('secret_scan_files')\n"
    "    return copy.deepcopy(FLAGGED)\n"
    "\n"
    "def scan(*args, **kwargs):\n"
    "    _log('secret_scan')\n"
    "    return copy.deepcopy(FLAGGED)\n"
    "\n"
    "def stored_result(*args, **kwargs):\n"
    "    _log('secret_stored_result')\n"
    "    return copy.deepcopy(FLAGGED)\n"
    "\n"
    "def load_stored_result(*args, **kwargs):\n"
    "    _log('secret_load_stored_result')\n"
    "    return copy.deepcopy(FLAGGED)\n"
    "\n"
    "def read_stored_result(*args, **kwargs):\n"
    "    _log('secret_read_stored_result')\n"
    "    return copy.deepcopy(FLAGGED)\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(tmp_path, sealed_result, flagged_secret=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "invocations.log"
    log.write_text("", encoding="utf-8")

    _write(
        repo_root / "specs" / "components" / "seal" / "component.md",
        "---\n"
        "id: comp-seal\n"
        "title: Seal\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/seal/\n"
        "---\n"
        "\n"
        "# Seal\n",
    )
    _write(
        repo_root / "specs" / "components" / "plain" / "component.md",
        "---\n"
        "id: comp-plain\n"
        "title: Plain\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Plain\n",
    )
    _write(repo_root / "legacy" / "seal" / "seal.py", "VALUE = 1\n")

    header = "LOG = " + repr(str(log)) + "\n"

    checker_src = (
        header
        + LOG_HELPERS
        + "SEAL_HASH = " + repr(SEAL_HASH) + "\n"
        + "SEALED_RESULT = " + repr(sealed_result) + "\n"
        + "PLAIN_HASH = " + repr(PLAIN_HASH) + "\n"
        + "PLAIN_GATE_VERSIONS = " + repr(PLAIN_GATE_VERSIONS) + "\n"
        + "PLAIN_HIT = " + repr(PLAIN_HIT) + "\n"
        + "\n"
        + CHECKER_BODY
    )
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", checker_src)

    _write(
        repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py",
        header + LOG_HELPERS + GATE_RUNNER_BODY,
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        header + LOG_HELPERS + CAPABILITY_BODY,
    )

    if flagged_secret:
        _write(
            repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
            header + LOG_HELPERS + "FLAGGED = " + repr(FLAGGED_SECRET_SCAN) + "\n\n" + SECRET_BODY,
        )
        stored = json.dumps(FLAGGED_SECRET_SCAN)
        _write(repo_root / ".hotdocs" / "secret-scan.json", stored)
        _write(repo_root / ".hotdocs" / "secret-scanner" / "result.json", stored)

    return repo_root, log


def _read_log(log):
    entries = []
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _calls(entries, name):
    return [e for e in entries if e[0] == name]


def _assert_gate_runner_never_loaded(entries):
    assert _calls(entries, "component_gate_runner_loaded") == []
    assert _calls(entries, "run_component_gates") == []


def test_sealed_component_hit_routes_through_sealed_path(tmp_path):
    repo_root, log = _build_repo(tmp_path, copy.deepcopy(SEALED_HIT))

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True

    entries = _read_log(log)

    sealed_calls = _calls(entries, "check_sealed_provenance")
    assert [c[1] for c in sealed_calls] == ["comp-seal"]

    prov_calls = _calls(entries, "check_provenance")
    assert [c[1] for c in prov_calls] == ["comp-plain"]
    assert prov_calls[0][2] == PLAIN_HASH
    assert prov_calls[0][3] == PLAIN_GATE_VERSIONS

    key_calls = _calls(entries, "current_provenance_key")
    assert [c[1] for c in key_calls] == ["comp-plain"]

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT

    _assert_gate_runner_never_loaded(entries)


def test_sealed_component_miss_reports_reason(tmp_path):
    repo_root, log = _build_repo(tmp_path, copy.deepcopy(SEALED_MISS))

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False

    reasons = list(field(report, "not_ready_reasons"))
    seal_reasons = [r for r in reasons if "comp-seal" in r]
    assert seal_reasons == [
        "comp-seal: sealed provenance source_changed — run hotdocs generate comp-seal"
    ]

    entries = _read_log(log)
    assert [c[1] for c in _calls(entries, "check_sealed_provenance")] == ["comp-seal"]
    assert all(c[1] != "comp-seal" for c in _calls(entries, "check_provenance"))
    assert all(c[1] != "comp-seal" for c in _calls(entries, "current_provenance_key"))

    _assert_gate_runner_never_loaded(entries)


def test_sealed_component_ignores_flagged_secret_scan(tmp_path):
    repo_root, log = _build_repo(tmp_path, copy.deepcopy(SEALED_HIT), flagged_secret=True)

    report = provenance_tracker.check_readiness(repo_root)

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT

    reasons = list(field(report, "not_ready_reasons"))
    assert [r for r in reasons if "comp-seal" in r] == []

    entries = _read_log(log)
    assert [c[1] for c in _calls(entries, "check_sealed_provenance")] == ["comp-seal"]

    _assert_gate_runner_never_loaded(entries)