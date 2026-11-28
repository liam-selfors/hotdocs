# hotdocs-criterion: sha256:742e4919d1ec96ab6ef9f27a3453299f4be57f864ff41a0eb25f50416ed517ba
import importlib.util
import json
import sys
from pathlib import Path

import generation_loop


TEST_REL = Path("verification") / "widget" / "generated-test" / "test_ac_w_1.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _logger_source(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "def _log(name, args):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': name, 'args': args}) + '\\n')\n"
    )


def _generator_source(log_path):
    return (
        _logger_source(log_path)
        + "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generate', {'model': model, 'retry_feedback': retry_feedback})\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': {'widget.py': 'VALUE = 1\\n'},\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "        'mode': 'single',\n"
        "        'transcript_sha256': None,\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "    }\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log('commit_cache', {})\n"
        "    return None\n"
    )


def _agentic_source(log_path):
    return (
        _logger_source(log_path)
        + "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        "                     wall_seconds=1800.0, claude_command='claude'):\n"
        "    _log('generate_agentic', {})\n"
        "    raise AssertionError('agentic generation must not run in single mode')\n"
    )


def _surface_source(log_path):
    return (
        _logger_source(log_path)
        + "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log('check_surface', {'component_id': component_id})\n"
        "    return {'ok': True, 'findings': []}\n"
    )


def _verifier_source(log_path, test_file, rewrite):
    return (
        _logger_source(log_path)
        + "import uuid\n"
        "from pathlib import Path\n"
        "TEST_FILE = Path(" + repr(str(test_file)) + ")\n"
        "REWRITE = " + repr(bool(rewrite)) + "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', {'component_id': component_id})\n"
        "    if REWRITE:\n"
        "        TEST_FILE.parent.mkdir(parents=True, exist_ok=True)\n"
        "        TEST_FILE.write_text('x = ' + repr(uuid.uuid4().hex) + '\\n', encoding='utf-8')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [\n"
        "            {'id': 'AC-W-1', 'kind': 'generated-test', 'result': 'fail',\n"
        "             'failure_origin': 'implementation', 'covers': 'R-W-1',\n"
        "             'failure_detail': {'message': 'assert failed', 'expected': 1, 'actual': 2}},\n"
        "        ],\n"
        "        'requirement_results': {'R-W-1': 'fail'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': 'fail',\n"
        "    }\n"
    )


def _test_author_source(log_path):
    return (
        _logger_source(log_path)
        + "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log('author_test', {})\n"
        "    return {\n"
        "        'component_id': 'comp-widget', 'criterion_id': 'AC-W-1', 'model': model,\n"
        "        'seed': seed, 'prompt_version': 'v1', 'cache_hit': False,\n"
        "        'file': {'path': 'verification/widget/generated-test/test_ac_w_1.py', 'content': 'x = 1\\n'},\n"
        "        'model_call_error': None, 'repair_attempts': 0, 'probe_findings': [],\n"
        "    }\n"
    )


def _llm_endpoint_source(log_path):
    return (
        _logger_source(log_path)
        + "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('complete', {})\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )


def _build_repo(tmp_path, rewrite):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    test_file = repo_root / TEST_REL
    _write(test_file, "x = 1")
    gen = repo_root / "gen"
    _write(gen / "generator" / "generator.py", _generator_source(log_path))
    _write(gen / "agentic-generator" / "agentic_generator.py", _agentic_source(log_path))
    _write(gen / "surface-checker" / "surface_checker.py", _surface_source(log_path))
    _write(gen / "verifier-orchestrator" / "verifier_orchestrator.py",
           _verifier_source(log_path, test_file, rewrite))
    _write(gen / "test-author" / "test_author.py", _test_author_source(log_path))
    _write(gen / "llm-endpoint" / "llm_endpoint.py", _llm_endpoint_source(log_path))
    return repo_root, log_path, test_file


def _calls(log_path, name):
    if not log_path.is_file():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry["call"] == name:
                out.append(entry)
    return out


def _run(repo_root, max_attempts):
    return generation_loop.run_attempts(
        "comp-widget",
        {"component_id": "comp-widget"},
        repo_root,
        "mock-model",
        max_attempts=max_attempts,
    )


def _reauthored(result):
    attempts = field(result, "attempts")
    return [list(field(a, "reauthored_tests")) for a in attempts]


def _outcomes(result):
    return [field(a, "outcome") for a in field(result, "attempts")]


def test_unchanged_test_file_is_deleted_once_before_third_attempt(tmp_path):
    repo_root, log_path, test_file = _build_repo(tmp_path, rewrite=False)

    result = _run(repo_root, 3)

    assert len(_calls(log_path, "verify")) == 3
    assert _outcomes(result) == ["verification_failed"] * 3
    assert _reauthored(result) == [[], ["AC-W-1"], []]
    assert not test_file.exists()


def test_changing_test_file_is_never_deleted(tmp_path):
    repo_root, log_path, test_file = _build_repo(tmp_path, rewrite=True)

    result = _run(repo_root, 3)

    assert len(_calls(log_path, "verify")) == 3
    assert _outcomes(result) == ["verification_failed"] * 3
    assert _reauthored(result) == [[], [], []]
    assert test_file.exists()


def test_no_deletion_when_no_attempt_follows(tmp_path):
    repo_root, log_path, test_file = _build_repo(tmp_path, rewrite=False)

    result = _run(repo_root, 2)

    assert len(_calls(log_path, "verify")) == 2
    assert _outcomes(result) == ["verification_failed"] * 2
    assert _reauthored(result) == [[], []]
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "x = 1"