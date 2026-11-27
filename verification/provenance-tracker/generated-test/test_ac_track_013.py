# hotdocs-criterion: sha256:30d8d11f3fd73a8ebf112a3ef24a42479fa1cec52586f3c4aad4579d16cad9be
import copy
import json
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SEALED_HIT = {
    "hit": True,
    "sealed": True,
    "reason": None,
    "verification_report": {"overall": "pass"},
    "license_scan": None,
    "secret_scan": None,
    "owners": ["pipeline-team"],
    "source_hash": "sha256:" + "0" * 64,
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

PLAIN_HASH = "sha256:" + "ab" * 32
PLAIN_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}

PLAIN_RESULT = {
    "hit": True,
    "reason": None,
    "verification_report": {
        "component_id": "comp-plain",
        "criteria": [
            {"id": "AC-PLAIN-001", "covers": "R-PLAIN-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-PLAIN-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
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

CLEAN_SCAN = {"flagged": False, "matches": []}
FLAGGED_SCAN = {
    "flagged": True,
    "matches": [{"file": "a/b.py", "line": 3, "rule_id": "AWS Access Key", "risk_tier": "high"}],
}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "components" / "seal" / "component.md",
        "---\n"
        "id: comp-seal\n"
        "title: Sealed Fixture\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/seal/\n"
        "---\n\n# comp-seal\n\nA sealed fixture component.\n",
    )
    write(
        repo_root / "specs" / "components" / "plain" / "component.md",
        "---\n"
        "id: comp-plain\n"
        "title: Plain Fixture\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: false\n"
        "---\n\n# comp-plain\n\nA plain fixture component.\n",
    )


def write_fake_checker(repo_root, log_path, sealed_result):
    src = (
        "import copy\n"
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "SEALED_RESULT = " + repr(sealed_result) + "\n"
        "PLAIN_RESULT = " + repr(PLAIN_RESULT) + "\n"
        "PLAIN_HASH = " + repr(PLAIN_HASH) + "\n"
        "PLAIN_GATE_VERSIONS = " + repr(PLAIN_GATE_VERSIONS) + "\n"
        "SEALED_IDS = " + repr(["comp-seal"]) + "\n"
        "\n"
        "def _log(name, **kw):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'fn': name, 'args': kw}, default=str) + '\\n')\n"
        "\n"
        "class _SealedKey:\n"
        "    def __init__(self):\n"
        "        self.owners = ['pipeline-team']\n"
        "        self.source_path = 'legacy/seal/'\n"
        "        self.source_hash = " + repr("sha256:" + "0" * 64) + "\n"
        "        self.verifier_version = 'verifier-orchestrator@2.0.0'\n"
        "\n"
        "class _ProvenanceKey:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = PLAIN_HASH\n"
        "        self.spec_bundle_parts = {'spec': PLAIN_HASH, 'dependency_code': PLAIN_HASH}\n"
        "        self.gate_versions = dict(PLAIN_GATE_VERSIONS)\n"
        "        self.assets = []\n"
        "        self.drivers = []\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
        "    if component_id in SEALED_IDS:\n"
        "        return _SealedKey()\n"
        "    return None\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id, repo_root=str(repo_root))\n"
        "    return copy.deepcopy(SEALED_RESULT)\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id, repo_root=str(repo_root))\n"
        "    return _ProvenanceKey()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash,\n"
        "         gate_versions=gate_versions, repo_root=str(repo_root))\n"
        "    return copy.deepcopy(PLAIN_RESULT)\n"
    )
    write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", src)


def write_fake_secret_scanner(repo_root, log_path, result):
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "RESULT = " + repr(result) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(str(repo_root) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(RESULT)\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
    )
    write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", src)


def write_gate_runner_tripwire(repo_root, log_path):
    src = (
        "with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as _f:\n"
        "    _f.write('loaded\\n')\n"
    )
    write(repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py", src)


def setup(tmp_path, sealed_result, scan_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    build_corpus(repo_root)
    checker_log = logs / "checker.log"
    scan_log = logs / "scan.log"
    gate_log = logs / "gate_runner.log"
    write_fake_checker(repo_root, checker_log, sealed_result)
    write_fake_secret_scanner(repo_root, scan_log, scan_result)
    write_gate_runner_tripwire(repo_root, gate_log)
    return repo_root, checker_log, scan_log, gate_log


def read_calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ids_for(calls, fn):
    return {c["args"]["component_id"] for c in calls if c["fn"] == fn}


def test_sealed_hit_routes_only_through_sealed_check(tmp_path):
    repo_root, checker_log, scan_log, gate_log = setup(tmp_path, SEALED_HIT, CLEAN_SCAN)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True, field(report, "not_ready_reasons")

    calls = read_calls(checker_log)
    assert ids_for(calls, "check_sealed_provenance") == {"comp-seal"}
    assert ids_for(calls, "check_provenance") == {"comp-plain"}
    assert ids_for(calls, "current_provenance_key") == {"comp-plain"}

    for c in calls:
        if c["fn"] == "check_provenance":
            assert c["args"]["spec_bundle_hash"] == PLAIN_HASH
            assert c["args"]["gate_versions"] == PLAIN_GATE_VERSIONS

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT

    assert not gate_log.exists(), "component-gate-runner was loaded"


def test_sealed_miss_reason_names_source_changed(tmp_path):
    repo_root, checker_log, scan_log, gate_log = setup(tmp_path, SEALED_MISS, CLEAN_SCAN)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    seal_entries = [r for r in reasons if "comp-seal" in r]
    assert seal_entries == [
        "comp-seal: sealed provenance source_changed \u2014 run hotdocs generate comp-seal"
    ]

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_MISS
    assert not gate_log.exists(), "component-gate-runner was loaded"


def test_flagged_secret_scan_never_attributed_to_sealed_component(tmp_path):
    repo_root, checker_log, scan_log, gate_log = setup(tmp_path, SEALED_HIT, FLAGGED_SCAN)

    report = provenance_tracker.check_readiness(repo_root)

    reasons = list(field(report, "not_ready_reasons"))
    assert not any("comp-seal" in r for r in reasons), reasons

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT
    assert not gate_log.exists(), "component-gate-runner was loaded"