import json
from pathlib import Path

from component_gate_runner import run_component_gates


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def get_field(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


LOG_HELPER = """\
import os


def _log(repo_root, line):
    path = os.path.join(str(repo_root), 'invocations.log')
    with open(path, 'a', encoding='utf-8') as f:
        f.write(line + chr(10))
"""


def _provenance_checker_src(overall: str) -> str:
    return LOG_HELPER + """
import json


class _Key(object):
    spec_bundle_hash = 'sha256:k'
    gate_versions = {'verifier': 'v@1'}


def current_provenance_key(component_id, repo_root):
    _log(repo_root, 'provenance-checker.current_provenance_key')
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        repo_root,
        'provenance-checker.check_provenance' + chr(9) + str(spec_bundle_hash)
        + chr(9) + json.dumps(gate_versions, sort_keys=True),
    )
    return {
        'hit': True,
        'verification_report': {
            'component_id': component_id,
            'criteria': [],
            'requirement_results': {},
            'interface_drift': False,
            'mutation_score': 1.0,
            'overall': '""" + overall + """',
        },
        'license_scan': {
            'component_id': component_id,
            'gate_version': 'license_scanner@3.1.0',
            'similarity_score': 0.0,
            'block_threshold': 0.70,
            'blocked': False,
            'matches': [],
            'notified': False,
            'notification_delivery_error': None,
            'cache_hit': False,
        },
        'secret_scan': {
            'scope': 'full',
            'gate_version': 'secret_scanner@2.0.0',
            'flagged': False,
            'matches': [],
            'notified': False,
            'notification_delivery_error': None,
            'cache_hit': False,
        },
    }
"""


SPEC_BUNDLE_ASSEMBLER_SRC = LOG_HELPER + """
def assemble(component_id, repo_root, mode='cold'):
    _log(repo_root, 'spec-bundle-assembler.assemble')
    return {
        'component_id': component_id,
        'spec_bundle_hash': 'sha256:k',
        'spec': 'spec text',
        'interface': 'interface text',
        'constraints': 'constraints text',
        'dependency_interfaces': {},
        'dependency_context': {},
        'dependency_usage': {},
        'vars': {},
        'glossary': 'glossary text',
        'hint_code': None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    _log(repo_root, 'spec-bundle-assembler.assemble_criterion')
    return {
        'component_id': component_id,
        'criterion_id': criterion_id,
        'covers': 'R-FOO-001',
        'criterion_text': '',
        'requirement_text': '',
        'interface': '',
        'glossary': '',
    }
"""

GENERATOR_SRC = LOG_HELPER + """
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log(repo_root, 'generator.generate')
    return {
        'component_id': 'comp-foo',
        'spec_bundle_hash': 'sha256:k',
        'model': model,
        'prompt_version': 'v1',
        'cache_hit': False,
        'files': {},
        'model_call_error': {'category': 'network', 'message': 'simulated failure'},
        'refused': None,
        'retry_feedback': retry_feedback,
    }
"""

VERIFIER_ORCHESTRATOR_SRC = LOG_HELPER + """
GATE_VERSION = 'verifier-orchestrator@2.0.0'


def verify(component_id, repo_root, judge=None, test_author=None):
    _log(repo_root, 'verifier-orchestrator.verify')
    return {
        'component_id': component_id,
        'criteria': [],
        'requirement_results': {},
        'interface_drift': False,
        'mutation_score': 1.0,
        'overall': 'pass',
    }
"""

LICENSE_SCANNER_SRC = LOG_HELPER + """
def scan(component_id, repo_root):
    _log(repo_root, 'license-scanner.scan')
    return {
        'component_id': component_id,
        'gate_version': 'license_scanner@3.1.0',
        'similarity_score': 0.0,
        'block_threshold': 0.70,
        'blocked': False,
        'matches': [],
        'notified': False,
        'notification_delivery_error': None,
        'cache_hit': False,
    }


def gate_version(repo_root):
    return 'license_scanner@3.1.0'
"""

SECRET_SCANNER_SRC = LOG_HELPER + """
def scan(repo_root):
    _log(repo_root, 'secret-scanner.scan')
    return {
        'scope': 'full',
        'gate_version': 'secret_scanner@2.0.0',
        'flagged': False,
        'matches': [],
        'notified': False,
        'notification_delivery_error': None,
        'cache_hit': False,
    }


def scan_files(paths):
    return {
        'scope': 'precommit',
        'flagged': False,
        'matches': [],
        'notified': False,
        'notification_delivery_error': None,
        'cache_hit': False,
    }


def gate_version(repo_root):
    return 'secret_scanner@2.0.0'
"""

PROVENANCE_TRACKER_SRC = LOG_HELPER + """
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log(repo_root, 'provenance-tracker.write_attempt_record')
    return {
        'attempt_id': '2026-01-01T00:00:00Z-aaaaaa',
        'component_id': component_id,
        'timestamp': '2026-01-01T00:00:00Z',
        'spec_bundle_hash': spec_bundle_hash,
        'generation': generation_result,
        'verification': verification_report,
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log(repo_root, 'provenance-tracker.check_readiness')
    return {
        'scope': 'whole-corpus',
        'ready': True,
        'components': {},
        'capabilities': {},
        'not_ready_reasons': [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
"""

PROVENANCE_WRITER_SRC = LOG_HELPER + """
def write_provenance(component_id, inputs, repo_root):
    _log(repo_root, 'provenance-writer.write_provenance')
    return None
"""

TEST_AUTHOR_SRC = LOG_HELPER + """
def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log(repo_root, 'test-author.author_test')
    return {
        'component_id': 'comp-foo',
        'criterion_id': 'AC-FOO-001',
        'model': model,
        'seed': seed,
        'prompt_version': 'v1',
        'cache_hit': False,
        'file': {'path': 'verification/foo/generated-test/test_ac_foo_001.py', 'content': ''},
        'model_call_error': None,
    }
"""

LLM_ENDPOINT_SRC = """
def complete(prompt, model, *, backend=None, **params):
    return {'text': 'ok', 'model': model, 'backend': backend, 'model_call_error': None}
"""


COMPONENT_MD = """\
---
id: comp-foo
title: Foo
status: draft
owners: [lselfors@gmail.com]
sealed: false
---

# Foo

Purpose: a fixture target component for component-gate-runner tests.
"""


def _build_repo(tmp_path: Path, overall: str) -> Path:
    repo_root = tmp_path

    _write(repo_root / "specs" / "components" / "foo" / "component.md", COMPONENT_MD)

    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        _provenance_checker_src(overall),
    )
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        SPEC_BUNDLE_ASSEMBLER_SRC,
    )
    _write(repo_root / "gen" / "generator" / "generator.py", GENERATOR_SRC)
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        VERIFIER_ORCHESTRATOR_SRC,
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        LICENSE_SCANNER_SRC,
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        SECRET_SCANNER_SRC,
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        PROVENANCE_TRACKER_SRC,
    )
    _write(
        repo_root / "gen" / "provenance-writer" / "provenance_writer.py",
        PROVENANCE_WRITER_SRC,
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", TEST_AUTHOR_SRC)
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", LLM_ENDPOINT_SRC)

    return repo_root


def _read_log_lines(repo_root: Path):
    log_path = repo_root / "invocations.log"
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8").splitlines()


def test_provenance_hit_pass_and_unblocked_short_circuits(tmp_path):
    repo_root = _build_repo(tmp_path, overall="pass")

    result = run_component_gates("comp-foo", repo_root, "m")

    lines = _read_log_lines(repo_root)
    assert len(lines) == 2
    assert lines[0] == "provenance-checker.current_provenance_key"

    parts = lines[1].split("\t")
    assert parts[0] == "provenance-checker.check_provenance"
    assert parts[1] == "sha256:k"
    assert json.loads(parts[2]) == {"verifier": "v@1"}

    assert get_field(result, "provenance_hit") is True
    assert get_field(result, "blocked") is False

    verification = get_field(result, "verification")
    assert get_field(verification, "component_id") == "comp-foo"
    assert get_field(verification, "criteria") == []
    assert get_field(verification, "requirement_results") == {}
    assert get_field(verification, "interface_drift") is False
    assert get_field(verification, "mutation_score") == 1.0
    assert get_field(verification, "overall") == "pass"


def test_provenance_hit_failing_verification_proceeds_as_miss(tmp_path):
    repo_root = _build_repo(tmp_path, overall="fail")

    result = run_component_gates("comp-foo", repo_root, "m")

    lines = _read_log_lines(repo_root)
    generator_calls = [line for line in lines if line == "generator.generate"]
    assert len(generator_calls) == 1

    assert get_field(result, "provenance_hit") is False