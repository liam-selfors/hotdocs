# hotdocs-criterion: sha256:8743e86f6d1f7f24d9e3f9e8213126aaab5afbc1b6ef6436753caba38b6808a1
import json
from pathlib import Path

import provenance_tracker


PLAIN_HASH = "sha256:" + "a" * 64
SEAL_HASH = "sha256:" + "0123456789abcdef" * 4

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}

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

PLAIN_VERIFICATION_REPORT = {
    "component_id": "comp-plain",
    "criteria": [
        {"id": "AC-PLAIN-001", "covers": "R-PLAIN-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-PLAIN-001": "pass"},
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
    "overall": "pass",
}

PLAIN_LICENSE_SCAN = {
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
}

PLAIN_SECRET_SCAN = {
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

PLAIN_HIT = {
    "hit": True,
    "reason": None,
    "verification_report": PLAIN_VERIFICATION_REPORT,
    "license_scan": PLAIN_LICENSE_SCAN,
    "secret_scan": PLAIN_SECRET_SCAN,
}

FLAGGED_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": True,
    "matches": [
        {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "legacy/seal/config.py", "line": 12}
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo_root, slug, comp_id):
    text = (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + slug + " component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + comp_id + "\n"
        "\n"
        "A fixture component.\n"
    )
    write(repo_root / "specs" / "components" / slug / "component.md", text)


LOG_HELPER = (
    "import json\n"
    "import types\n"
    "\n"
    "def _plain(a):\n"
    "    if isinstance(a, (dict, list, str, int, float, bool)) or a is None:\n"
    "        return a\n"
    "    return str(a)\n"
    "\n"
    "def _log(name, *args):\n"
    "    with open(LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps({'name': name, 'args': [_plain(a) for a in args]}) + '\\n')\n"
    "\n"
)


def write_fakes(repo_root, log_path, sealed_result, with_flagged_secret_scan=False):
    checker = (
        "LOG = " + repr(str(log_path)) + "\n"
        + LOG_HELPER
        + "SEALED_IDS = " + repr(["comp-seal"]) + "\n"
        + "SEALED_RESULT = " + repr(sealed_result) + "\n"
        + "PLAIN_RESULT = " + repr(PLAIN_HIT) + "\n"
        + "PLAIN_HASH = " + repr(PLAIN_HASH) + "\n"
        + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        + "SEAL_HASH = " + repr(SEAL_HASH) + "\n"
        + "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id, repo_root)\n"
        "    if component_id in SEALED_IDS:\n"
        "        return types.SimpleNamespace(\n"
        "            owners=['pipeline-team'],\n"
        "            source_path='legacy/' + component_id[len('comp-'):] + '/',\n"
        "            source_hash=SEAL_HASH,\n"
        "            verifier_version='verifier-orchestrator@2.0.0',\n"
        "        )\n"
        "    return None\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id, repo_root)\n"
        "    return dict(SEALED_RESULT)\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id, repo_root)\n"
        "    return types.SimpleNamespace(\n"
        "        spec_bundle_hash=PLAIN_HASH,\n"
        "        gate_versions=dict(GATE_VERSIONS),\n"
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                 'adapter_sha256': 'sha256:' + 'b' * 64,\n"
        "                 'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id, spec_bundle_hash, gate_versions, repo_root)\n"
        "    if component_id in SEALED_IDS:\n"
        "        return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "                'license_scan': None, 'secret_scan': None}\n"
        "    return json.loads(json.dumps(PLAIN_RESULT))\n"
    )
    write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", checker)

    gate_runner = (
        "LOG = " + repr(str(log_path)) + "\n"
        + LOG_HELPER
        + "_log('LOADED component-gate-runner')\n"
        "\n"
        "def run_component_gates(*args, **kwargs):\n"
        "    _log('run_component_gates', *args)\n"
        "    raise RuntimeError('component-gate-runner must never be called')\n"
    )
    write(repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py", gate_runner)

    capability = (
        "LOG = " + repr(str(log_path)) + "\n"
        + LOG_HELPER
        + "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
        "\n"
        "class UnknownCapabilityError(ValueError):\n"
        "    pass\n"
        "\n"
        "class ModelRequiredError(ValueError):\n"
        "    pass\n"
        "\n"
        "def check_capability_provenance(capability_id, repo_root):\n"
        "    _log('check_capability_provenance', capability_id, repo_root)\n"
        "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
        "    _log('run_capability_gates', capability_id, repo_root)\n"
        "    return {'hit': True, 'capability_scenario_report': {capability_id: {'overall': 'pass', 'scenarios': []}}}\n"
        "\n"
        "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
        "    _log('run_capability_scenarios', blast_radius, repo_root)\n"
        "    return {}\n"
    )
    write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        capability,
    )

    if with_flagged_secret_scan:
        scanner = (
            "LOG = " + repr(str(log_path)) + "\n"
            + LOG_HELPER
            + "FLAGGED = " + repr(FLAGGED_SECRET_SCAN) + "\n"
            "\n"
            "def gate_version(repo_root):\n"
            "    _log('secret_scanner.gate_version', repo_root)\n"
            "    return FLAGGED['gate_version']\n"
            "\n"
            "def stored_result(repo_root):\n"
            "    _log('secret_scanner.stored_result', repo_root)\n"
            "    return dict(FLAGGED)\n"
            "\n"
            "def scan_repository(repo_root):\n"
            "    _log('secret_scanner.scan_repository', repo_root)\n"
            "    return dict(FLAGGED)\n"
        )
        write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", scanner)
        write(
            repo_root / ".hotdocs" / "secret-scan" / "result.json",
            json.dumps(FLAGGED_SECRET_SCAN),
        )


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ids_for(entries, name):
    return [e["args"][0] for e in entries if e["name"] == name]


def build(tmp_path, sealed_result, with_flagged_secret_scan=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.log"
    write_component(repo_root, "seal", "comp-seal")
    write_component(repo_root, "plain", "comp-plain")
    write_fakes(repo_root, log_path, sealed_result, with_flagged_secret_scan)
    return repo_root, log_path


def test_sealed_component_routed_to_sealed_check_and_hit_is_ready(tmp_path):
    repo_root, log_path = build(tmp_path, SEALED_HIT)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True
    entries = read_log(log_path)
    assert ids_for(entries, "check_sealed_provenance") == ["comp-seal"]
    assert ids_for(entries, "check_provenance") == ["comp-plain"]
    assert ids_for(entries, "current_provenance_key") == ["comp-plain"]

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT

    names = [e["name"] for e in entries]
    assert "LOADED component-gate-runner" not in names
    assert "run_component_gates" not in names


def test_sealed_miss_reports_sealed_provenance_reason(tmp_path):
    repo_root, log_path = build(tmp_path, SEALED_MISS)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    seal_reasons = [r for r in reasons if "comp-seal" in r]
    assert seal_reasons == [
        "comp-seal: sealed provenance source_changed — run hotdocs generate comp-seal"
    ]

    names = [e["name"] for e in read_log(log_path)]
    assert "LOADED component-gate-runner" not in names
    assert "run_component_gates" not in names


def test_sealed_readiness_ignores_flagged_repository_secret_scan(tmp_path):
    repo_root, log_path = build(tmp_path, SEALED_HIT, with_flagged_secret_scan=True)

    report = provenance_tracker.check_readiness(repo_root)

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT
    reasons = list(field(report, "not_ready_reasons"))
    assert [r for r in reasons if "comp-seal" in r] == []

    entries = read_log(log_path)
    assert ids_for(entries, "check_sealed_provenance") == ["comp-seal"]
    names = [e["name"] for e in entries]
    assert "LOADED component-gate-runner" not in names
    assert "run_component_gates" not in names