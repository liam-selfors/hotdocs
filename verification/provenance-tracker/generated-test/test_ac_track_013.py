# hotdocs-criterion: sha256:4cccae72267b1c08fe23cdab295eb47098a0866d4c6c7299b72e89ea27b9c61d
import json
import os
from pathlib import Path

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_ENV = "HOTDOCS_TEST_AC_TRACK_013_LOG"
SEALED_MODE_ENV = "HOTDOCS_TEST_AC_TRACK_013_SEALED_MODE"
SECRET_MODE_ENV = "HOTDOCS_TEST_AC_TRACK_013_SECRET_MODE"


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


PROVENANCE_CHECKER_SRC = (
    "import json\n"
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "LOG_ENV = " + repr(LOG_ENV) + "\n"
    "SEALED_MODE_ENV = " + repr(SEALED_MODE_ENV) + "\n"
    "SEALED_HIT = " + repr(SEALED_HIT) + "\n"
    "\n"
    "def _log(name, args):\n"
    "    with open(os.environ[LOG_ENV], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'fn': name, 'args': args}, default=str, sort_keys=True) + '\\n')\n"
    "\n"
    "def _slug(component_id):\n"
    "    return component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
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
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', [component_id, str(repo_root)])\n"
    "    md = Path(repo_root) / 'specs' / 'components' / _slug(component_id) / 'component.md'\n"
    "    try:\n"
    "        text = md.read_text(encoding='utf-8')\n"
    "    except OSError:\n"
    "        return None\n"
    "    lines = [l.strip() for l in text.splitlines()]\n"
    "    if 'sealed: true' not in lines:\n"
    "        return None\n"
    "    return SealedKey(['pipeline-team'], 'legacy/seal/', 'sha256:' + '0' * 64, 'verifier-orchestrator@2.0.0')\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', [component_id, str(repo_root)])\n"
    "    mode = os.environ.get(SEALED_MODE_ENV, 'hit')\n"
    "    if mode == 'hit':\n"
    "        return dict(SEALED_HIT)\n"
    "    return {'hit': False, 'sealed': True, 'reason': mode, 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None,\n"
    "            'source_hash': None, 'written_at': None}\n"
    "\n"
    "GATE_VERSIONS = {\n"
    "    'compiler': 'criterion-compiler@1.0.0',\n"
    "    'generated_test': 'generated_test@1.0.0',\n"
    "    'verifier': 'verifier-orchestrator@2.0.0',\n"
    "    'license_scanner': 'license_scanner@4.0.3+9f2c41ab07de',\n"
    "    'secret_scanner': 'secret_scanner@0.0.0',\n"
    "    'generator': 'generator@3.0.0+v11',\n"
    "}\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', [component_id, str(repo_root)])\n"
    "    return ProvenanceKey('sha256:' + 'a' * 64, dict(GATE_VERSIONS),\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "          'adapter_sha256': 'sha256:' + 'b' * 64, 'versions': {'python': '3.12.4'},\n"
    "          'lockfile_sha256': None}])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', [component_id, spec_bundle_hash, gate_versions, str(repo_root)])\n"
    "    report = {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-PLAIN-001', 'covers': 'R-PLAIN-001', 'kind': 'compiled', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-PLAIN-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'assets': [],\n"
    "        'overall': 'pass',\n"
    "    }\n"
    "    license_scan = {\n"
    "        'component_id': component_id, 'gate_version': 'license_scanner@4.0.3+9f2c41ab07de',\n"
    "        'evaluated': True, 'reason': None, 'similarity_score': 0.1, 'block_threshold': 0.7,\n"
    "        'blocked': False, 'matches': [], 'notified': False,\n"
    "        'notification_delivery_error': None, 'cache_hit': False,\n"
    "    }\n"
    "    secret_scan = {\n"
    "        'scope': 'full', 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
    "        'matches': [], 'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
    "        'notification_delivery_error': None, 'cache_hit': False,\n"
    "    }\n"
    "    return {'hit': True, 'reason': None, 'verification_report': report,\n"
    "            'license_scan': license_scan, 'secret_scan': secret_scan}\n"
)


SECRET_SCANNER_SRC = (
    "import json\n"
    "import os\n"
    "\n"
    "LOG_ENV = " + repr(LOG_ENV) + "\n"
    "SECRET_MODE_ENV = " + repr(SECRET_MODE_ENV) + "\n"
    "\n"
    "def scan(repo_root):\n"
    "    with open(os.environ[LOG_ENV], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'fn': 'secret_scan', 'args': [str(repo_root)]}) + '\\n')\n"
    "    if os.environ.get(SECRET_MODE_ENV) == 'flagged':\n"
    "        return {'flagged': True, 'matches': [{'file': 'a/b.py', 'line': 3,\n"
    "                'rule_id': 'AWS Access Key', 'risk_tier': 'high'}]}\n"
    "    return {'flagged': False, 'matches': []}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
)


GATE_RUNNER_SRC = (
    "import json\n"
    "import os\n"
    "\n"
    "with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "    fh.write(json.dumps({'fn': 'component_gate_runner_loaded', 'args': []}) + '\\n')\n"
    "\n"
    "def run_component_gates(*args, **kwargs):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'fn': 'run_component_gates', 'args': []}) + '\\n')\n"
    "    raise RuntimeError('component-gate-runner must never be called')\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write(
        repo_root / "specs" / "components" / "seal" / "component.md",
        "---\n"
        "id: comp-seal\n"
        "title: Sealed Fixture\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/seal/\n"
        "---\n"
        "\n"
        "# Sealed fixture\n",
    )
    _write(
        repo_root / "specs" / "components" / "plain" / "component.md",
        "---\n"
        "id: comp-plain\n"
        "title: Plain Fixture\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Plain fixture\n",
    )
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_SRC)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SRC)
    _write(repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py", GATE_RUNNER_SRC)
    return repo_root


def _setup(tmp_path, monkeypatch, sealed_mode="hit", secret_mode="clean"):
    repo_root = _build_repo(tmp_path)
    log = tmp_path / "invocations.log"
    log.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log))
    monkeypatch.setenv(SEALED_MODE_ENV, sealed_mode)
    monkeypatch.setenv(SECRET_MODE_ENV, secret_mode)
    return repo_root, log


def _read_log(log):
    entries = []
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _ids_for(entries, fn):
    return [e["args"][0] for e in entries if e["fn"] == fn]


def test_sealed_hit_routes_only_through_sealed_check(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch)

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True, field(report, "not_ready_reasons")

    entries = _read_log(log)
    assert sorted(set(_ids_for(entries, "check_sealed_provenance"))) == ["comp-seal"]
    assert sorted(set(_ids_for(entries, "check_provenance"))) == ["comp-plain"]
    assert sorted(set(_ids_for(entries, "current_provenance_key"))) == ["comp-plain"]

    components = field(report, "components")
    assert "comp-seal" in components
    assert components["comp-seal"] == SEALED_HIT

    fns = [e["fn"] for e in entries]
    assert "component_gate_runner_loaded" not in fns
    assert "run_component_gates" not in fns


def test_sealed_miss_reason_exact(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch, sealed_mode="source_changed")

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False
    reasons = list(field(report, "not_ready_reasons"))
    seal_reasons = [r for r in reasons if "comp-seal" in r]
    assert seal_reasons == [
        "comp-seal: sealed provenance source_changed — run hotdocs generate comp-seal"
    ]

    fns = [e["fn"] for e in _read_log(log)]
    assert "component_gate_runner_loaded" not in fns
    assert "run_component_gates" not in fns


def test_sealed_readiness_ignores_secret_scan(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch, secret_mode="flagged")

    report = provenance_tracker.check_readiness(repo_root)

    reasons = list(field(report, "not_ready_reasons"))
    assert not any("comp-seal" in r for r in reasons), reasons

    fns = [e["fn"] for e in _read_log(log)]
    assert "component_gate_runner_loaded" not in fns