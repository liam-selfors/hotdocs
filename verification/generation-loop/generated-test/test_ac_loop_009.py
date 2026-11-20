# hotdocs-criterion: sha256:b846811c76cab85f4df2218a3a0b5facc4f7c5137c0db94555e007bd8169fc81
import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_helper(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "def _log(name, **kw):\n"
        "    rec = {'call': name}\n"
        "    rec.update({k: repr(v) for k, v in kw.items()})\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(rec) + '\\n')\n"
    )


def _build_fixture(tmp_path, gen_mode):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    log_path = logs / "calls.log"

    generator_src = (
        _log_helper(log_path)
        + "GEN_MODE = " + repr(gen_mode) + "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generate', model=model, retry_feedback=retry_feedback)\n"
        "    base = {\n"
        "        'component_id': 'comp-widget',\n"
        "        'spec_bundle_hash': 'sha256:abc',\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': {},\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "        'mode': 'single',\n"
        "        'transcript_sha256': None,\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "    }\n"
        "    if GEN_MODE == 'files':\n"
        "        base['files'] = " + repr({"widget.py": "X = 1"}) + "\n"
        "    else:\n"
        "        base['model_call_error'] = " + repr(
            {"category": "environment", "message": "javascript needs node >= 24"}
        ) + "\n"
        "    return base\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log('commit_cache')\n"
        "    return None\n"
    )
    _write(repo_root / "gen" / "generator" / "generator.py", generator_src)

    surface_src = (
        _log_helper(log_path)
        + "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log('check_surface', component_id=component_id)\n"
        "    return {'ok': True, 'findings': []}\n"
    )
    _write(repo_root / "gen" / "surface-checker" / "surface_checker.py", surface_src)

    criteria = [
        {
            "id": "AC-W-001",
            "covers": "R-W-1",
            "kind": "generated-test",
            "result": "fail",
            "failure_origin": "environment",
            "failure_detail": {"message": "javascript needs node >= 24"},
        },
        {
            "id": "AC-W-002",
            "covers": "R-W-2",
            "kind": "generated-test",
            "result": "fail",
            "failure_origin": "implementation",
            "failure_detail": {"message": "assertion failed"},
        },
    ]
    verifier_src = (
        _log_helper(log_path)
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': " + repr(criteria) + ",\n"
        "        'requirement_results': " + repr({"R-W-1": "fail", "R-W-2": "fail"}) + ",\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'overall': 'fail',\n"
        "    }\n"
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        verifier_src,
    )
    return repo_root, log_path


def _calls(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)["call"]
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


BUNDLE = {"component_id": "comp-widget", "spec_bundle_hash": "sha256:abc", "hint_code": None}


def test_environment_failure_origin_stops_loop(tmp_path):
    repo_root, log_path = _build_fixture(tmp_path, "files")
    result = generation_loop.run_attempts(
        "comp-widget", BUNDLE, repo_root, "m", max_attempts=3
    )
    calls = _calls(log_path)
    assert calls.count("generate") == 1
    assert calls.count("verify") == 1
    assert "commit_cache" not in calls

    attempts = field(result, "attempts")
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["outcome"] == "verification_failed"
    assert attempt["failed_requirements"] == ["R-W-2"]
    assert field(result, "passed") is False
    assert field(result, "stop_reason") == "environment"


def test_environment_generation_error_stops_loop(tmp_path):
    repo_root, log_path = _build_fixture(tmp_path, "error")
    result = generation_loop.run_attempts(
        "comp-widget", BUNDLE, repo_root, "m", max_attempts=3
    )
    calls = _calls(log_path)
    assert calls.count("generate") == 1
    assert "verify" not in calls

    attempts = field(result, "attempts")
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "generation_failed"
    assert field(result, "stop_reason") == "environment"