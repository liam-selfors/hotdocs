# hotdocs-criterion: sha256:6fc3f03cc0558be09fe9f430376170dffe28f9c7795204f5457513c49e8ff3fa
import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _logger_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(name, data):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': name, 'data': data}, default=str) + '\\n')\n"
    )


def _generator_source(log_path):
    return (
        _logger_source(log_path)
        + "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generate', {'model': model, 'feedback': retry_feedback, 'repo_root': str(repo_root)})\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'spec_bundle_hash': 'sha256:0',\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': {'widget.py': 'x = 1\\n'},\n"
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
        "    _log('commit_cache', {'repo_root': str(repo_root)})\n"
        "    return None\n"
    )


def _surface_source(log_path):
    return (
        _logger_source(log_path)
        + "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log('check_surface', {'component_id': component_id, 'repo_root': str(repo_root)})\n"
        "    return {'ok': True, 'findings': []}\n"
    )


def _verifier_source(log_path, counter_path, rewrite):
    return (
        _logger_source(log_path)
        + "import os\n"
        "COUNTER = " + repr(str(counter_path)) + "\n"
        "REWRITE = " + repr(bool(rewrite)) + "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', {'component_id': component_id, 'repo_root': str(repo_root)})\n"
        "    if REWRITE:\n"
        "        n = 0\n"
        "        if os.path.exists(COUNTER):\n"
        "            with open(COUNTER, 'r', encoding='utf-8') as fh:\n"
        "                n = int(fh.read().strip() or '0')\n"
        "        n += 1\n"
        "        with open(COUNTER, 'w', encoding='utf-8') as fh:\n"
        "            fh.write(str(n))\n"
        "        target = os.path.join(str(repo_root), 'verification', 'widget', 'generated-test', 'test_ac_w_1.py')\n"
        "        os.makedirs(os.path.dirname(target), exist_ok=True)\n"
        "        with open(target, 'w', encoding='utf-8') as fh:\n"
        "            fh.write('x = ' + str(100 + n) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [\n"
        "            {'id': 'AC-W-1', 'covers': 'R-W-1', 'kind': 'generated-test',\n"
        "             'result': 'fail', 'failure_origin': 'implementation',\n"
        "             'failure_detail': {'message': 'assertion failed', 'expected': 1, 'actual': 2}},\n"
        "        ],\n"
        "        'requirement_results': {'R-W-1': 'fail'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'overall': 'fail',\n"
        "    }\n"
    )


def _build_repo(tmp_path, rewrite):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / "calls.log"
    counter_path = logs / "counter.txt"
    _write(repo_root / "gen" / "generator" / "generator.py", _generator_source(log_path))
    _write(repo_root / "gen" / "surface-checker" / "surface_checker.py", _surface_source(log_path))
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        _verifier_source(log_path, counter_path, rewrite),
    )
    test_file = repo_root / "verification" / "widget" / "generated-test" / "test_ac_w_1.py"
    _write(test_file, "x = 1")
    return repo_root, test_file, log_path


def _bundle():
    return {"component_id": "comp-widget", "spec_bundle_hash": "sha256:0", "hint_code": None}


def _calls(log_path, name):
    if not log_path.exists():
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
        "comp-widget", _bundle(), repo_root, "fake-model", max_attempts=max_attempts
    )


def test_unchanged_failing_test_is_deleted_once_before_next_attempt(tmp_path):
    repo_root, test_file, log_path = _build_repo(tmp_path, rewrite=False)
    result = _run(repo_root, 3)
    attempts = field(result, "attempts")
    assert len(attempts) == 3
    assert len(_calls(log_path, "verify")) == 3
    for a in attempts:
        assert field(a, "outcome") == "verification_failed"
    assert [field(a, "reauthored_tests") for a in attempts] == [[], ["AC-W-1"], []]
    assert not test_file.exists()


def test_changing_test_file_is_never_deleted(tmp_path):
    repo_root, test_file, log_path = _build_repo(tmp_path, rewrite=True)
    result = _run(repo_root, 3)
    attempts = field(result, "attempts")
    assert len(attempts) == 3
    assert len(_calls(log_path, "verify")) == 3
    for a in attempts:
        assert field(a, "reauthored_tests") == []
    assert test_file.exists()


def test_no_deletion_when_no_attempt_follows(tmp_path):
    repo_root, test_file, log_path = _build_repo(tmp_path, rewrite=False)
    result = _run(repo_root, 2)
    attempts = field(result, "attempts")
    assert len(attempts) == 2
    assert len(_calls(log_path, "verify")) == 2
    for a in attempts:
        assert field(a, "reauthored_tests") == []
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == "x = 1"