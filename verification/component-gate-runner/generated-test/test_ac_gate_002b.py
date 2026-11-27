# hotdocs-criterion: sha256:fd00fa049d182fc0d3f3b84b40b47a5a8a22dd8861be3453dd0ec11601892080
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "\n"
    "def _log(rec):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(rec) + '\\n')\n"
    "\n"
)


def _write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def _header(log_path):
    return "LOG = " + repr(str(log_path)) + "\n" + LOG_HELPER


def _verification_report_source():
    report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }
    return repr(report)


def _build_fakes(repo_root, log_path):
    head = _header(log_path)

    provenance_checker = (
        head
        + "class _SealedKey:\n"
        + "    def __init__(self):\n"
        + "        self.owners = " + repr(["pipeline-team"]) + "\n"
        + "        self.source_path = " + repr("legacy/foo/") + "\n"
        + "        self.source_hash = " + repr("sha256:" + "0" * 64) + "\n"
        + "        self.verifier_version = " + repr("verifier-orchestrator@2.0.0") + "\n"
        + "\n"
        + "class _ProvenanceKey:\n"
        + "    def __init__(self):\n"
        + "        self.spec_bundle_hash = " + repr("sha256:" + "1" * 64) + "\n"
        + "        self.spec_bundle_parts = " + repr({"spec": "sha256:aa", "dependency_code": "sha256:bb"}) + "\n"
        + "        self.gate_versions = " + repr({
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.0.0+v11",
        }) + "\n"
        + "        self.assets = []\n"
        + "        self.drivers = []\n"
        + "\n"
        + "def current_sealed_key(component_id, repo_root):\n"
        + "    _log({'call': 'current_sealed_key', 'component_id': component_id, 'repo_root': str(repo_root)})\n"
        + "    return _SealedKey()\n"
        + "\n"
        + "def current_provenance_key(component_id, repo_root):\n"
        + "    _log({'call': 'current_provenance_key'})\n"
        + "    return _ProvenanceKey()\n"
        + "\n"
        + "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        + "    _log({'call': 'check_provenance'})\n"
        + "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        + "            'license_scan': None, 'secret_scan': None}\n"
        + "\n"
        + "def check_sealed_provenance(component_id, repo_root):\n"
        + "    _log({'call': 'check_sealed_provenance'})\n"
        + "    return {'hit': False, 'sealed': True, 'reason': 'no manifest', 'verification_report': None,\n"
        + "            'license_scan': None, 'secret_scan': None, 'owners': None,\n"
        + "            'source_hash': None, 'written_at': None}\n"
    )
    _write_fake(repo_root, "provenance-checker", provenance_checker)

    generation_loop = (
        head
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        + "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        + "                      'missing_asset', 'malformed_layout')\n"
        + "\n"
        + "def _sentinel_test_author(bundle):\n"
        + "    return {'model_call_error': None, 'file': None}\n"
        + "_sentinel_test_author.sentinel_tag = 'TEST-AUTHOR-SENTINEL'\n"
        + "\n"
        + "def _sentinel_judge(bundle):\n"
        + "    return {'result': 'pass', 'rationale': None}\n"
        + "_sentinel_judge.sentinel_tag = 'JUDGE-SENTINEL'\n"
        + "\n"
        + "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        + "    _log({'call': 'make_closures', 'model': model, 'seed': seed,\n"
        + "          'seed_type': type(seed).__name__,\n"
        + "          'repo_root': str(repo_root), 'repo_root_type': type(repo_root).__name__,\n"
        + "          'llm_backend_is_none': llm_backend is None,\n"
        + "          'test_author_id': id(_sentinel_test_author), 'judge_id': id(_sentinel_judge)})\n"
        + "    return (_sentinel_test_author, _sentinel_judge)\n"
        + "\n"
        + "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        + "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
        + "                 on_attempt=None):\n"
        + "    _log({'call': 'run_attempts'})\n"
        + "    return {'passed': False, 'stop_reason': 'max_attempts', 'attempts': [],\n"
        + "            'generation_result': {'component_id': component_id, 'spec_bundle_hash': 'sha256:00',\n"
        + "                'model': model, 'prompt_version': 'v1', 'cache_hit': False, 'files': {},\n"
        + "                'model_call_error': None, 'refused': 'fake', 'retry_feedback': None,\n"
        + "                'mode': 'single', 'transcript_sha256': None, 'turns': 1, 'tool_calls': 0,\n"
        + "                'isolation': None},\n"
        + "            'verification_report': None, 'surface_report': None}\n"
    )
    _write_fake(repo_root, "generation-loop", generation_loop)

    verifier = (
        head
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        + "DEFAULT_TEST_TIMEOUT = 300.0\n"
        + "\n"
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        + "    _log({'call': 'verify', 'component_id': component_id, 'repo_root': str(repo_root),\n"
        + "          'judge_tag': getattr(judge, 'sentinel_tag', None),\n"
        + "          'test_author_tag': getattr(test_author, 'sentinel_tag', None),\n"
        + "          'judge_id': id(judge), 'test_author_id': id(test_author)})\n"
        + "    return " + _verification_report_source() + "\n"
    )
    _write_fake(repo_root, "verifier-orchestrator", verifier)

    license_scanner = (
        head
        + "def gate_version(repo_root):\n"
        + "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
        + "\n"
        + "def scan(component_id, repo_root):\n"
        + "    _log({'call': 'license_scan', 'component_id': component_id})\n"
        + "    return {'component_id': component_id,\n"
        + "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
        + "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
        + "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
        + "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
        + "            'cache_hit': False}\n"
    )
    _write_fake(repo_root, "license-scanner", license_scanner)

    secret_scanner = (
        head
        + "def gate_version(repo_root):\n"
        + "    return 'secret_scanner@0.0.0'\n"
        + "\n"
        + "def scan(repo_root):\n"
        + "    _log({'call': 'secret_scan'})\n"
        + "    return {'scope': 'full', 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
        + "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
        + "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
        + "\n"
        + "def scan_files(paths, repo_root=None):\n"
        + "    _log({'call': 'secret_scan_files'})\n"
        + "    return {'scope': 'precommit', 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
        + "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
        + "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
    )
    _write_fake(repo_root, "secret-scanner", secret_scanner)

    provenance_writer = (
        head
        + "class InvalidSealedInputError(Exception):\n"
        + "    pass\n"
        + "\n"
        + "class MissingInputError(Exception):\n"
        + "    pass\n"
        + "\n"
        + "def write_provenance(component_id, inputs, repo_root):\n"
        + "    _log({'call': 'write_provenance'})\n"
        + "    return None\n"
        + "\n"
        + "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        + "    _log({'call': 'write_sealed_provenance', 'component_id': component_id})\n"
        + "    return None\n"
    )
    _write_fake(repo_root, "provenance-writer", provenance_writer)

    assembler = (
        head
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        + "    _log({'call': 'assemble'})\n"
        + "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:00', 'spec': '',\n"
        + "            'interface': '', 'constraints': '', 'dependency_interfaces': {},\n"
        + "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {},\n"
        + "            'glossary': '', 'hint_code': None, 'spec_bundle_parts': {}}\n"
        + "\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    _log({'call': 'assemble_criterion'})\n"
        + "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
        + "            'criterion_text': '', 'requirement_text': '', 'interface': '',\n"
        + "            'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    )
    _write_fake(repo_root, "spec-bundle-assembler", assembler)

    tracker = (
        head
        + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        + "    _log({'call': 'write_attempt_record'})\n"
        + "    return {'attempt_id': '2026-01-01T00:00:00Z-000000', 'component_id': component_id,\n"
        + "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        + "            'generation': {}, 'verification': None}\n"
        + "\n"
        + "def last_requirement_failures(component_id, repo_root):\n"
        + "    return []\n"
        + "\n"
        + "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        + "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
        + "            'secret_scan': None, 'not_ready_reasons': []}\n"
    )
    _write_fake(repo_root, "provenance-tracker", tracker)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_gate_002b_sealed_closures_come_from_make_closures(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fakes(repo_root, log_path)

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m", seed=5)

    calls = _read_log(log_path)
    names = [c["call"] for c in calls]

    mc = [c for c in calls if c["call"] == "make_closures"]
    assert len(mc) == 1, names
    mc = mc[0]
    assert mc["model"] == "m"
    assert mc["seed"] == 5
    assert mc["seed_type"] == "int"
    assert mc["repo_root"] == str(repo_root)
    assert mc["repo_root_type"] == type(repo_root).__name__
    assert mc["llm_backend_is_none"] is True

    vf = [c for c in calls if c["call"] == "verify"]
    assert len(vf) == 1, names
    vf = vf[0]
    assert vf["component_id"] == "comp-foo"
    assert vf["test_author_tag"] == "TEST-AUTHOR-SENTINEL"
    assert vf["judge_tag"] == "JUDGE-SENTINEL"
    assert vf["test_author_id"] == mc["test_author_id"]
    assert vf["judge_id"] == mc["judge_id"]

    assert names.index("make_closures") < names.index("verify")
    assert "run_attempts" not in names