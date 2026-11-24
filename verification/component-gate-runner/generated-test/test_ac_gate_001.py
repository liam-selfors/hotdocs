# hotdocs-criterion: sha256:527df7c45c20864dd4c270e62fc360b111b16e17a9c66b1619858ffd49d10fc3
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HEADER = (
    "import json\n"
    "import os\n"
    "import types\n"
    "\n"
    "def _log(fn, **kw):\n"
    "    rec = {'fn': fn}\n"
    "    rec.update(kw)\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as fh:\n"
    "        fh.write(json.dumps(rec, default=str) + '\\n')\n"
    "\n"
)


def verification_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass" if overall == "pass" else "fail"},
        ],
        "requirement_results": {"R-FOO-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:ab", "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": overall,
    }


def license_scan(blocked):
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": blocked,
        "matches": [],
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


def write_fake(repo_root, slug, body):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(HEADER + body)


def build_repo(repo_root, hit_overall):
    hit = {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(hit_overall),
        "license_scan": license_scan(False),
        "secret_scan": secret_scan(),
    }
    write_fake(repo_root, "provenance-checker", (
        "HIT = " + repr(hit) + "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    return types.SimpleNamespace(\n"
        "        spec_bundle_hash='sha256:k',\n"
        "        gate_versions={'verifier': 'v@1'},\n"
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                 'adapter_sha256': 'sha256:ab', 'versions': {'python': '3.12.4'},\n"
        "                 'lockfile_sha256': None}],\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id,\n"
        "         spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions)\n"
        "    return json.loads(json.dumps(HIT))\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))
    write_fake(repo_root, "spec-bundle-assembler", (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k',\n"
        "            'spec': '', 'interface': '', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    ))
    write_fake(repo_root, "generation-loop", (
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model)\n"
        "    gen = {'component_id': component_id, 'spec_bundle_hash': 'sha256:k',\n"
        "           'model': model, 'prompt_version': 'v1', 'cache_hit': False,\n"
        "           'files': {}, 'model_call_error': {'category': 'network', 'message': 'down'},\n"
        "           'refused': None, 'retry_feedback': retry_feedback, 'mode': 'single',\n"
        "           'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
        "    attempt = {'number': 1, 'outcome': 'generation_failed', 'retry_feedback': [],\n"
        "               'error_category': 'network', 'surface_ok': None, 'overall': None,\n"
        "               'failed_requirements': [], 'transcript_sha256': None,\n"
        "               'reauthored_tests': []}\n"
        "    return {'passed': False, 'stop_reason': 'not_retried', 'attempts': [attempt],\n"
        "            'generation_result': gen, 'verification_report': None,\n"
        "            'surface_report': None}\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))
    write_fake(repo_root, "license-scanner", (
        "RESULT = " + repr(license_scan(False)) + "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return dict(RESULT)\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    _log('license_gate_version')\n"
        "    return RESULT['gate_version']\n"
    ))
    write_fake(repo_root, "secret-scanner", (
        "RESULT = " + repr(secret_scan()) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return dict(RESULT)\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return dict(RESULT)\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    _log('secret_gate_version')\n"
        "    return RESULT['gate_version']\n"
        "\n"
        "def propose(repo_root):\n"
        "    _log('secret_propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    ))
    write_fake(repo_root, "provenance-writer", (
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id)\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id)\n"
        "    return None\n"
    ))
    write_fake(repo_root, "provenance-tracker", (
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id)\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    ))
    write_fake(repo_root, "verifier-orchestrator", (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "REPORT = " + repr(verification_report("pass")) + "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return dict(REPORT)\n"
    ))
    return hit


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_passing_hit_short_circuits(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    hit = build_repo(repo_root, "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = read_log(log_path)
    names = [c["fn"] for c in calls]
    assert names.count("check_provenance") == 1, names
    idx = names.index("check_provenance")
    cp = calls[idx]
    assert cp["spec_bundle_hash"] == "sha256:k"
    assert cp["gate_versions"] == {"verifier": "v@1"}
    assert "current_provenance_key" in names[:idx]
    assert names[idx + 1:] == [], names

    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False
    assert field(result, "verification") == hit["verification_report"]
    assert field(result, "license_scan") == hit["license_scan"]
    assert field(result, "secret_scan") == hit["secret_scan"]
    assert list(field(result, "attempts")) == []


def test_failed_hit_proceeds_as_miss(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    build_repo(repo_root, "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    names = [c["fn"] for c in read_log(log_path)]
    assert names.count("check_provenance") == 1, names
    assert names.count("run_attempts") == 1, names
    assert field(result, "provenance_hit") is False