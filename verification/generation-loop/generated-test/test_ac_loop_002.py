# hotdocs-criterion: sha256:c7d27f149c52dfe4bfcf9e2b3d9ce3f4cfe81d6a314e5e26835efe14fee558c6
import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _plant_stand_ins(repo_root, log_path, counter_path):
    log_helper = (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "def _log(entry):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
    )

    generator_src = (
        log_helper
        + "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log({'call': 'generate', 'model': model, 'feedback': retry_feedback})\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'spec_bundle_hash': 'sha256:abc',\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': {'widget.py': 'X = 1'},\n"
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
        "    _log({'call': 'commit_cache'})\n"
        "    return None\n"
    )
    _write(repo_root / "gen" / "generator" / "generator.py", generator_src)

    surface_src = (
        log_helper
        + "import os\n"
        "COUNTER_PATH = " + repr(str(counter_path)) + "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    n = 0\n"
        "    if os.path.exists(COUNTER_PATH):\n"
        "        with open(COUNTER_PATH, 'r', encoding='utf-8') as fh:\n"
        "            n = int(fh.read().strip() or '0')\n"
        "    with open(COUNTER_PATH, 'w', encoding='utf-8') as fh:\n"
        "        fh.write(str(n + 1))\n"
        "    _log({'call': 'check_surface', 'component_id': component_id})\n"
        "    if n == 0:\n"
        "        return {'ok': False, 'findings': [{'kind': 'import_error', 'message': 'boom'}]}\n"
        "    return {'ok': True, 'findings': []}\n"
    )
    _write(repo_root / "gen" / "surface-checker" / "surface_checker.py", surface_src)

    verifier_src = (
        log_helper
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log({'call': 'verify', 'component_id': component_id,\n"
        "          'judge_callable': callable(judge),\n"
        "          'test_author_callable': callable(test_author)})\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [\n"
        "            {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001', 'kind': 'compiled', 'result': 'pass'}\n"
        "        ],\n"
        "        'requirement_results': {'R-WIDGET-001': 'pass'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", verifier_src)


def test_ac_loop_002_surface_failed_then_passed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    counter_path = tmp_path / "surface_counter.txt"
    _plant_stand_ins(repo_root, log_path, counter_path)

    bundle = {"component_id": "comp-widget", "spec_bundle_hash": "sha256:abc", "hint_code": None}

    result = generation_loop.run_attempts("comp-widget", bundle, repo_root, "m")

    attempts = field(result, "attempts")
    assert len(attempts) == 2

    first, second = attempts[0], attempts[1]
    assert first["outcome"] == "surface_failed"
    assert first["surface_ok"] is False
    assert first["overall"] is None

    assert second["outcome"] == "passed"
    assert second["surface_ok"] is True
    assert second["overall"] == "pass"

    calls = _log_lines(log_path)
    surface_calls = [c for c in calls if c["call"] == "check_surface"]
    assert len(surface_calls) == 2

    verify_calls = [c for c in calls if c["call"] == "verify"]
    assert len(verify_calls) == 1
    assert verify_calls[0]["judge_callable"] is True
    assert verify_calls[0]["test_author_callable"] is True