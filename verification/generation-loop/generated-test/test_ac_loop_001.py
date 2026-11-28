# hotdocs-criterion: sha256:b7c7ee6d2475a5cc286103c961dc56d1c95d501d22ab363dca19230c88896901
import json
from pathlib import Path

import pytest

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


LOG_HELPER = (
    "import json\n"
    "def _log(name, **kw):\n"
    "    entry = dict(kw)\n"
    "    entry['fn'] = name\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry, default=str) + '\\n')\n"
    "def _count(name):\n"
    "    try:\n"
    "        with open(LOG, encoding='utf-8') as fh:\n"
    "            lines = [l for l in fh.read().splitlines() if l.strip()]\n"
    "    except FileNotFoundError:\n"
    "        return 0\n"
    "    return sum(1 for l in lines if json.loads(l).get('fn') == name)\n"
)


def _gen_result_source():
    return (
        "def _result(spec, model, retry_feedback, mode):\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': {},\n"
        "        'model_call_error': spec.get('model_call_error'),\n"
        "        'refused': spec.get('refused'),\n"
        "        'retry_feedback': retry_feedback,\n"
        "        'mode': mode,\n"
        "        'transcript_sha256': None,\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "    }\n"
        "def _pick(name):\n"
        "    n = _count(name)\n"
        "    return RESULTS[min(n, len(RESULTS) - 1)]\n"
    )


def plant_stand_ins(repo_root, log_path, results):
    head = "LOG = " + repr(str(log_path)) + "\nRESULTS = " + repr(results) + "\n" + LOG_HELPER

    _write(
        repo_root / "gen" / "generator" / "generator.py",
        head
        + _gen_result_source()
        + "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    spec = _pick('generate')\n"
        "    _log('generate', model=model, feedback=retry_feedback)\n"
        "    return _result(spec, model, retry_feedback, 'single')\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log('commit_cache')\n"
        "    return None\n",
    )

    _write(
        repo_root / "gen" / "agentic-generator" / "agentic_generator.py",
        head
        + _gen_result_source()
        + "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        "                     wall_seconds=1800.0, claude_command='claude'):\n"
        "    spec = _pick('generate_agentic')\n"
        "    _log('generate_agentic', model=model, feedback=retry_feedback)\n"
        "    return _result(spec, model, retry_feedback, 'agentic')\n",
    )

    _write(
        repo_root / "gen" / "surface-checker" / "surface_checker.py",
        head
        + "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log('check_surface', component_id=component_id)\n"
        "    return {'ok': True, 'findings': []}\n",
    )

    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        head
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [],\n"
        "        'requirement_results': {},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': 'pass',\n"
        "    }\n",
    )

    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        head
        + "GATE_VERSION = 'generated_test@3.0.0'\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log('author_test', model=model)\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'criterion_id': 'AC-WIDGET-001',\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': None,\n"
        "        'model_call_error': {'category': 'network', 'message': 'stand-in'},\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n",
    )

    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        head
        + "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('complete', model=model)\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'stand-in', 'model_call_error': None}\n",
    )


def read_calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def fn_names(calls):
    return [c["fn"] for c in calls]


def test_non_retried_error_ends_loop_after_retried_one(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    results = [
        {"model_call_error": {"category": "truncated_response", "message": "cut off"}},
        {"model_call_error": {"category": "rate_limit", "message": "429"}},
    ]
    plant_stand_ins(repo_root, log_path, results)

    bundle = {"component_id": "comp-widget"}
    result = generation_loop.run_attempts("comp-widget", bundle, repo_root, "m")

    names = fn_names(read_calls(log_path))
    assert names.count("generate") == 2
    assert "check_surface" not in names
    assert "verify" not in names

    attempts = field(result, "attempts")
    assert [a["outcome"] for a in attempts] == ["generation_failed", "generation_failed"]
    assert [a["error_category"] for a in attempts] == ["truncated_response", "rate_limit"]
    assert field(result, "stop_reason") == "not_retried"


def test_refused_ends_loop_at_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    plant_stand_ins(repo_root, log_path, [{"refused": "sealed-component"}])

    bundle = {"component_id": "comp-widget"}
    result = generation_loop.run_attempts(
        "comp-widget", bundle, repo_root, "m", max_attempts=3
    )

    names = fn_names(read_calls(log_path))
    assert names.count("generate") == 1
    attempts = field(result, "attempts")
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "refused"
    assert field(result, "stop_reason") == "refused"


@pytest.mark.parametrize("kwargs", [{"mode": "turbo"}, {"max_attempts": 0}])
def test_invalid_arguments_raise_before_any_call(tmp_path, kwargs):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    plant_stand_ins(repo_root, log_path, [{"refused": "sealed-component"}])

    bundle = {"component_id": "comp-widget"}
    with pytest.raises(ValueError):
        generation_loop.run_attempts("comp-widget", bundle, repo_root, "m", **kwargs)

    assert read_calls(log_path) == []