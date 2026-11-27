# hotdocs-criterion: sha256:768b920b624e328ce1425040216068a26fa6a64cabdcbe4caf4f0c1ce6a04a30
# Test for AC-LOOP-008 (covers R-LOOP-001): retried generation_failed
# categories ("missing_asset", "malformed_layout") lead to further attempts,
# and a third attempt that generates files, passes the surface check and
# verifies "pass" ends the loop with stop_reason "passed".

import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_helpers(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry, default=str) + '\\n')\n"
        "\n"
        "def _count(fn):\n"
        "    try:\n"
        "        with open(LOG, encoding='utf-8') as f:\n"
        "            return sum(1 for line in f if line.strip() and json.loads(line)['fn'] == fn)\n"
        "    except FileNotFoundError:\n"
        "        return 0\n"
        "\n"
    )


def _generator_source(log_path):
    return (
        _log_helpers(log_path)
        + "def _result(model, retry_feedback):\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
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
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    n = _count('generate')\n"
        "    _log({'fn': 'generate', 'model': model, 'retry_feedback': retry_feedback})\n"
        "    r = _result(model, retry_feedback)\n"
        "    if n == 0:\n"
        "        r['model_call_error'] = {'category': 'missing_asset', 'message': 'asset missing'}\n"
        "    elif n == 1:\n"
        "        r['model_call_error'] = {'category': 'malformed_layout', 'message': 'bad layout'}\n"
        "    else:\n"
        "        r['files'] = {'widget.py': 'X = 1'}\n"
        "    return r\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log({'fn': 'commit_cache'})\n"
        "    return None\n"
        "\n"
        "def check_write_allowed(bundle, repo_root=None):\n"
        "    return None\n"
    )


def _surface_source(log_path):
    return (
        _log_helpers(log_path)
        + "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log({'fn': 'check_surface', 'component_id': component_id})\n"
        "    return {'ok': True, 'findings': []}\n"
    )


def _verifier_source(log_path):
    return (
        _log_helpers(log_path)
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log({'fn': 'verify', 'component_id': component_id})\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [\n"
        "            {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001',\n"
        "             'kind': 'generated-test', 'result': 'pass'},\n"
        "        ],\n"
        "        'requirement_results': {'R-WIDGET-001': 'pass'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 1.0,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
    )


def _agentic_source(log_path):
    return (
        _log_helpers(log_path)
        + "AGENT_PROMPT_VERSION = 'agent-v2'\n"
        "\n"
        "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        "                     wall_seconds=1800.0, claude_command='claude'):\n"
        "    _log({'fn': 'generate_agentic'})\n"
        "    raise AssertionError('agentic generator must not be used in single mode')\n"
    )


def _test_author_source(log_path):
    return (
        _log_helpers(log_path)
        + "GATE_VERSION = 'generated_test@3.0.0'\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log({'fn': 'author_test'})\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'criterion_id': 'AC-WIDGET-001',\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': 'verification/widget/generated-test/test_ac_widget_001.py',\n"
        "                 'content': 'def test_x():\\n    assert True\\n'},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n"
    )


def _llm_endpoint_source(log_path):
    return (
        _log_helpers(log_path)
        + "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log({'fn': 'complete'})\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock',\n"
        "            'model_call_error': None}\n"
    )


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def test_ac_loop_008_retried_categories_then_pass(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    gen = repo_root / "gen"
    _write(gen / "generator" / "generator.py", _generator_source(log_path))
    _write(gen / "agentic-generator" / "agentic_generator.py", _agentic_source(log_path))
    _write(gen / "surface-checker" / "surface_checker.py", _surface_source(log_path))
    _write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", _verifier_source(log_path))
    _write(gen / "test-author" / "test_author.py", _test_author_source(log_path))
    _write(gen / "llm-endpoint" / "llm_endpoint.py", _llm_endpoint_source(log_path))

    bundle = {"component_id": "comp-widget", "spec_bundle_hash": "sha256:" + "0" * 64,
              "hint_code": None}

    result = generation_loop.run_attempts("comp-widget", bundle, repo_root, "m",
                                          max_attempts=3)

    calls = _read_log(log_path)
    generate_calls = [c for c in calls if c["fn"] == "generate"]
    assert len(generate_calls) == 3

    attempts = field(result, "attempts")
    assert [field(a, "outcome") for a in attempts] == [
        "generation_failed", "generation_failed", "passed",
    ]
    assert [field(a, "error_category") for a in attempts] == [
        "missing_asset", "malformed_layout", None,
    ]
    assert field(result, "passed") is True
    assert field(result, "stop_reason") == "passed"