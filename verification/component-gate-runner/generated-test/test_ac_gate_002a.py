# hotdocs-criterion: sha256:0d6109f1d8a405873ed371fa91451a3d52ed9b19f934ab2be999b1deb9df6467
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _SentinelBackend:
    def __repr__(self):
        return "<SENTINEL-BACKEND-AC-GATE-002a>"


def _prelude(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(name, **kw):\n"
        "    kw['call'] = name\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps(kw, default=repr) + '\\n')\n"
        "\n"
    )


_VR_SRC = """
def _vr():
    return {
        'component_id': 'comp-foo',
        'criteria': [
            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'},
        ],
        'requirement_results': {'R-FOO-001': 'pass'},
        'interface_drift': False,
        'mutation_score': 0.9,
        'mutation_error': None,
        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,
                    'adapter_sha256': 'sha256:' + 'd' * 64, 'versions': {'python': '3.12.4'},
                    'lockfile_sha256': None}],
        'drivers': [],
        'overall': 'pass',
    }

"""

_LICENSE_SRC = """
def _license(component_id):
    return {
        'component_id': component_id,
        'gate_version': 'license_scanner@4.0.0-no-reference-corpus',
        'evaluated': False,
        'reason': 'no-reference-corpus',
        'similarity_score': None,
        'block_threshold': None,
        'blocked': False,
        'matches': [],
        'notified': False,
        'notification_delivery_error': None,
        'cache_hit': False,
    }

"""

_SECRET_SRC = """
def _secret(scope='full'):
    return {
        'scope': scope,
        'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',
        'flagged': False,
        'matches': [],
        'allowed': [],
        'unused_allowlist_entries': [],
        'notified': False,
        'notification_delivery_error': None,
        'cache_hit': False,
    }

"""

_PROVENANCE_CHECKER_SRC = """
class _Key:
    def __init__(self):
        self.spec_bundle_hash = 'sha256:' + 'a' * 64
        self.spec_bundle_parts = {'spec': 'sha256:' + 'b' * 64, 'dependency_code': 'sha256:' + 'c' * 64}
        self.gate_versions = {
            'compiler': 'criterion-compiler@1.0.0',
            'generated_test': 'generated_test@1.0.0',
            'verifier': 'verifier-orchestrator@4.0.0',
            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',
            'secret_scanner': 'secret_scanner@3.1.0+detect-secrets.1.5.0',
            'generator': 'generator@3.0.0+v11',
        }
        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,
                        'adapter_sha256': 'sha256:' + 'd' * 64,
                        'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}]
        self.drivers = []

def current_sealed_key(component_id, repo_root):
    _log('current_sealed_key', component_id=component_id)
    return None

def current_provenance_key(component_id, repo_root):
    _log('current_provenance_key', component_id=component_id)
    return _Key()

def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):
    _log('check_provenance', component_id=component_id)
    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,
            'license_scan': None, 'secret_scan': None}

def check_sealed_provenance(component_id, repo_root):
    _log('check_sealed_provenance', component_id=component_id)
    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,
            'license_scan': None, 'secret_scan': None, 'owners': None,
            'source_hash': None, 'written_at': None}
"""

_ASSEMBLER_SRC = """
def assemble(component_id, repo_root, mode='cold'):
    bundle = {
        'component_id': component_id,
        'spec_bundle_hash': 'sha256:' + 'a' * 64,
        'spec': 'BUNDLE-MARKER-AC-GATE-002a',
        'interface': 'iface',
        'constraints': '',
        'dependency_interfaces': {},
        'dependency_context': {},
        'dependency_usage': {},
        'vars': {},
        'glossary': '',
        'hint_code': None,
        'spec_bundle_parts': {'spec': 'sha256:' + 'b' * 64, 'dependency_code': 'sha256:' + 'c' * 64},
    }
    _log('assemble', component_id=component_id, repo_root=str(repo_root),
         repo_root_type=type(repo_root).__name__, mode=mode,
         bundle_id=id(bundle), bundle=bundle)
    return bundle

def assemble_criterion(component_id, criterion_id, repo_root):
    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)
    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',
            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',
            'dependency_interfaces': {}, 'testing': ''}
"""

_LOOP_SRC = """
RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',
                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',
                      'missing_asset', 'malformed_layout')

def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,
                 on_attempt=None):
    _log('run_attempts', component_id=component_id,
         bundle_id=id(bundle),
         bundle=(bundle if isinstance(bundle, dict) else repr(bundle)),
         repo_root=str(repo_root), repo_root_type=type(repo_root).__name__,
         model=model, mode=mode, max_attempts=max_attempts,
         retry_feedback=retry_feedback, seed=seed,
         backend_id=id(llm_backend), backend_repr=repr(llm_backend),
         allow_unisolated_exec=allow_unisolated_exec,
         on_attempt_callable=callable(on_attempt))
    generation_result = {
        'component_id': component_id,
        'spec_bundle_hash': 'sha256:' + 'a' * 64,
        'model': model,
        'prompt_version': 'v12',
        'cache_hit': False,
        'files': {'foo.py': 'X = 1\\n'},
        'model_call_error': None,
        'refused': None,
        'retry_feedback': retry_feedback,
        'mode': mode,
        'transcript_sha256': None,
        'turns': 1,
        'tool_calls': 0,
        'isolation': None,
    }
    return {
        'passed': True,
        'stop_reason': 'passed',
        'attempts': [{'number': 1, 'outcome': 'passed', 'retry_feedback': list(retry_feedback or []),
                      'error_category': None, 'surface_ok': True, 'overall': 'pass',
                      'failed_requirements': [], 'transcript_sha256': None,
                      'reauthored_tests': []}],
        'generation_result': generation_result,
        'verification_report': _vr(),
        'surface_report': {'ok': True, 'findings': []},
    }

def make_closures(model, seed, repo_root, llm_backend=None):
    _log('make_closures', model=model, seed=seed)
    def test_author(bundle):
        return {'model_call_error': None, 'file': None}
    def judge(bundle):
        return {'result': 'pass', 'rationale': None}
    return (test_author, judge)
"""

_TRACKER_SRC = """
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log('write_attempt_record', component_id=component_id)
    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,
            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,
            'generation': {}, 'verification': None}

def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log('check_readiness')
    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},
            'secret_scan': None, 'not_ready_reasons': []}

def last_requirement_failures(component_id, repo_root):
    _log('last_requirement_failures', component_id=component_id)
    return []
"""

_VERIFIER_SRC = """
GATE_VERSION = 'verifier-orchestrator@4.0.0'
DEFAULT_TEST_TIMEOUT = 300.0

def verify(component_id, repo_root, judge=None, test_author=None):
    _log('verify', component_id=component_id)
    return _vr()
"""

_LICENSE_SCANNER_SRC = """
def scan(component_id, repo_root):
    _log('license_scan', component_id=component_id)
    return _license(component_id)

def gate_version(repo_root):
    return 'license_scanner@4.0.0-no-reference-corpus'
"""

_SECRET_SCANNER_SRC = """
def scan(repo_root):
    _log('secret_scan')
    return _secret('full')

def scan_files(paths, repo_root=None):
    _log('secret_scan_files')
    return _secret('precommit')

def gate_version(repo_root):
    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'

class AllowlistInvalidError(Exception):
    pass

def propose(repo_root):
    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}
"""

_WRITER_SRC = """
class InvalidSealedInputError(Exception):
    pass

class MissingInputError(Exception):
    pass

def write_provenance(component_id, inputs, repo_root):
    _log('write_provenance', component_id=component_id)
    return None

def write_sealed_provenance(component_id, inputs, repo_root):
    _log('write_sealed_provenance', component_id=component_id)
    return None
"""


def _write_fake(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_gate_002a_miss_calls_assemble_then_run_attempts_with_own_params(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    pre = _prelude(log_path)

    _write_fake(repo_root, "provenance-checker", pre + _PROVENANCE_CHECKER_SRC)
    _write_fake(repo_root, "spec-bundle-assembler", pre + _ASSEMBLER_SRC)
    _write_fake(repo_root, "generation-loop", pre + _VR_SRC + _LOOP_SRC)
    _write_fake(repo_root, "provenance-tracker", pre + _TRACKER_SRC)
    _write_fake(repo_root, "verifier-orchestrator", pre + _VR_SRC + _VERIFIER_SRC)
    _write_fake(repo_root, "license-scanner", pre + _LICENSE_SRC + _LICENSE_SCANNER_SRC)
    _write_fake(repo_root, "secret-scanner", pre + _SECRET_SRC + _SECRET_SCANNER_SRC)
    _write_fake(repo_root, "provenance-writer", pre + _WRITER_SRC)

    sentinel = _SentinelBackend()

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", seed=3,
        llm_backend=sentinel, retry_feedback=["R-FOO-002"],
        max_attempts=2, mode="agentic", allow_unisolated_exec=True,
    )
    assert result is not None

    calls = _read_log(log_path)
    names = [c["call"] for c in calls]

    # Order: assemble then run_attempts, each exactly once.
    relevant = [n for n in names if n in ("assemble", "run_attempts")]
    assert relevant == ["assemble", "run_attempts"], names
    assert "make_closures" not in names

    assemble_call = next(c for c in calls if c["call"] == "assemble")
    run_call = next(c for c in calls if c["call"] == "run_attempts")

    # assemble received cold mode.
    assert assemble_call["mode"] == "cold"
    assert assemble_call["component_id"] == "comp-foo"
    assert assemble_call["repo_root"] == str(repo_root)

    # run_attempts received the expected arguments.
    assert run_call["component_id"] == "comp-foo"
    assert run_call["bundle_id"] == assemble_call["bundle_id"]
    assert run_call["bundle"] == assemble_call["bundle"]
    assert run_call["repo_root"] == str(repo_root)
    assert run_call["repo_root_type"] == type(repo_root).__name__
    assert run_call["model"] == "m"
    assert run_call["mode"] == "agentic"
    assert run_call["max_attempts"] == 2
    assert run_call["retry_feedback"] == ["R-FOO-002"]
    assert run_call["seed"] == 3
    assert run_call["backend_id"] == id(sentinel)
    assert run_call["backend_repr"] == repr(sentinel)
    assert run_call["allow_unisolated_exec"] is True
    assert run_call["on_attempt_callable"] is True