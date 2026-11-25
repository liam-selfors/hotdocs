# hotdocs-criterion: sha256:5f881e0e79da646088499afc7b5985b394cdb61514daaaa03647e928d08265a3
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PROVENANCE_CHECKER_SRC = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "class _Key:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "\n"
    "_GATE_VERSIONS = {\n"
    "    'compiler': 'criterion-compiler@1.0.0',\n"
    "    'generated_test': 'generated_test@1.0.0',\n"
    "    'verifier': 'verifier-orchestrator@2.0.0',\n"
    "    'license_scanner': 'license_scanner@4.0.3+abc',\n"
    "    'secret_scanner': 'secret_scanner@0.0.0',\n"
    "    'generator': 'generator@3.0.0+v11',\n"
    "}\n"
    "\n"
    "_HASH = 'sha256:' + 'a' * 64\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    return _Key(_HASH, dict(_GATE_VERSIONS), [{\n"
    "        'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "        'adapter_sha256': 'sha256:' + 'b' * 64,\n"
    "        'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}])\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    return {\n"
    "        'hit': True,\n"
    "        'reason': None,\n"
    "        'verification_report': {\n"
    "            'component_id': component_id,\n"
    "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001',\n"
    "                          'kind': 'compiled', 'result': 'pass'}],\n"
    "            'requirement_results': {'R-FOO-001': 'pass'},\n"
    "            'interface_drift': False,\n"
    "            'mutation_score': 0.9,\n"
    "            'mutation_error': None,\n"
    "            'assets': [],\n"
    "            'overall': 'pass',\n"
    "        },\n"
    "        'license_scan': {\n"
    "            'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.3+abc',\n"
    "            'evaluated': True, 'reason': None,\n"
    "            'similarity_score': 0.1, 'block_threshold': 0.7,\n"
    "            'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False,\n"
    "        },\n"
    "        'secret_scan': {\n"
    "            'scope': 'full', 'gate_version': 'secret_scanner@0.0.0',\n"
    "            'flagged': False, 'matches': [], 'allowed': [],\n"
    "            'unused_allowlist_entries': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False,\n"
    "        },\n"
    "    }\n"
    "\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    return {\n"
    "        'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "        'verification_report': None, 'license_scan': None,\n"
    "        'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "        'written_at': None,\n"
    "    }\n"
)


CAPABILITY_VERIFIER_SRC = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "GATE_VERSION = 'capability_scenario_verifier@2.2.0'\n"
    "_HERE = Path(__file__).resolve().parent\n"
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
    "def _cfg():\n"
    "    return json.loads((_HERE / 'config.json').read_text())\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(_HERE / 'calls.log', 'a') as f:\n"
    "        f.write(line + '\\n')\n"
    "\n"
    "\n"
    "def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):\n"
    "    _log('scenarios')\n"
    "    return {}\n"
    "\n"
    "\n"
    "def check_capability_provenance(capability_id, repo_root):\n"
    "    _log('check ' + capability_id)\n"
    "    return _cfg()['check']\n"
    "\n"
    "\n"
    "def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):\n"
    "    _log('gates ' + json.dumps([capability_id, model, seed]))\n"
    "    return _cfg()['gates']\n"
)


SECRET_SCANNER_SRC = (
    "from pathlib import Path\n"
    "\n"
    "_HERE = Path(__file__).resolve().parent\n"
    "\n"
    "\n"
    "def scan(repo_root):\n"
    "    with open(_HERE / 'scan.log', 'a') as f:\n"
    "        f.write(str(repo_root) + '\\n')\n"
    "    return {'flagged': False, 'matches': []}\n"
)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "realizes: [P-FOO]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A fixture component realizing P-FOO.\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo capability\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "---\n"
    "\n"
    "# P-FOO\n"
    "\n"
    "A fixture product capability.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _build_repo(repo_root, check_result, gates_result):
    _write(repo_root / "specs" / "components" / "foo" / "component.md", COMPONENT_MD)
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do foo.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )
    _write(repo_root / "specs" / "product" / "foo.md", PRODUCT_MD)
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        PROVENANCE_CHECKER_SRC,
    )
    cap_dir = repo_root / "gen" / "capability-scenario-verifier"
    _write(cap_dir / "capability_scenario_verifier.py", CAPABILITY_VERIFIER_SRC)
    _write(
        cap_dir / "config.json",
        json.dumps({"check": check_result, "gates": gates_result}),
    )
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SRC)
    return cap_dir / "calls.log"


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [l for l in log_path.read_text().splitlines() if l.strip()]


def _gates_calls(log_path):
    return [l for l in _log_lines(log_path) if l.startswith("gates ")]


MISS = {"hit": False, "capability_scenario_report": None}


def _report(overall, scenarios):
    return {"P-FOO": {"overall": overall, "scenarios": scenarios}}


def test_all_passing_is_ready(tmp_path):
    passing = {
        "hit": False,
        "capability_scenario_report": _report(
            "pass", [{"id": "CS-FOO-001", "kind": "compiled", "result": "pass"}]
        ),
    }
    log = _build_repo(tmp_path, MISS, passing)
    report = provenance_tracker.check_readiness(tmp_path, model="m-1", seed=7)
    assert field(report, "ready") is True
    assert list(field(report, "not_ready_reasons")) == []
    calls = _gates_calls(log)
    assert len(calls) == 1
    assert json.loads(calls[0][len("gates "):]) == ["P-FOO", "m-1", 7]


def test_failed_scenarios_reason(tmp_path):
    failing = {
        "hit": False,
        "capability_scenario_report": _report(
            "fail",
            [
                {"id": "CS-FOO-001", "kind": "compiled", "result": "pass"},
                {"id": "CS-FOO-002", "kind": "llm-judge", "result": "fail"},
                {"id": "CS-FOO-003", "kind": "llm-judge", "result": "skipped"},
                {"id": "CS-FOO-004", "kind": "generated-test", "result": "fail"},
            ],
        ),
    }
    log = _build_repo(tmp_path, MISS, failing)
    report = provenance_tracker.check_readiness(tmp_path, model="m-1")
    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: capability scenarios failed: CS-FOO-002, CS-FOO-004"
    ]
    assert len(_gates_calls(log)) == 1


def test_empty_scenarios_reason(tmp_path):
    empty = {"hit": False, "capability_scenario_report": _report("fail", [])}
    log = _build_repo(tmp_path, MISS, empty)
    report = provenance_tracker.check_readiness(tmp_path, model="m-1")
    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: has no capability scenarios; add a CS- scenario to its file under specs/product/"
    ]
    assert len(_gates_calls(log)) == 1


def test_hit_short_circuits_gates(tmp_path):
    hit = {"hit": True, "capability_scenario_report": _report("fail", [])}
    unused = {
        "hit": False,
        "capability_scenario_report": _report(
            "pass", [{"id": "CS-FOO-001", "kind": "compiled", "result": "pass"}]
        ),
    }
    log = _build_repo(tmp_path, hit, unused)
    report = provenance_tracker.check_readiness(tmp_path, model="m-1")
    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: has no capability scenarios; add a CS- scenario to its file under specs/product/"
    ]
    assert _gates_calls(log) == []
    assert any(l == "check P-FOO" for l in _log_lines(log))


def test_miss_without_model_needs_fresh_run(tmp_path):
    unused = {
        "hit": False,
        "capability_scenario_report": _report(
            "pass", [{"id": "CS-FOO-001", "kind": "compiled", "result": "pass"}]
        ),
    }
    log = _build_repo(tmp_path, MISS, unused)
    report = provenance_tracker.check_readiness(tmp_path, model=None)
    assert field(report, "ready") is False
    assert list(field(report, "not_ready_reasons")) == [
        "P-FOO: needs a fresh run; pass --model"
    ]
    components = field(report, "components")
    assert "comp-foo" in components
    assert _gates_calls(log) == []