# hotdocs-criterion: sha256:543f3c4919e157683dbd2c23c1b85e2644709d92dab6249fda14f309532a3f5e
import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _generator_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _record(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "def _count(name):\n"
        "    try:\n"
        "        with open(LOG, 'r', encoding='utf-8') as fh:\n"
        "            lines = [json.loads(l) for l in fh if l.strip()]\n"
        "    except FileNotFoundError:\n"
        "        return 0\n"
        "    return sum(1 for e in lines if e.get('call') == name)\n"
        "\n"
        "def _result(files, error, feedback):\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'model': 'm',\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': files,\n"
        "        'model_call_error': error,\n"
        "        'refused': None,\n"
        "        'retry_feedback': feedback,\n"
        "        'mode': 'single',\n"
        "        'transcript_sha256': None,\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "    }\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    n = _count('generate')\n"
        "    _record({'call': 'generate', 'model': model, 'feedback': retry_feedback})\n"
        "    if n == 0:\n"
        "        return _result({}, {'category': 'missing_asset', 'message': 'asset missing'}, retry_feedback)\n"
        "    if n == 1:\n"
        "        return _result({}, {'category': 'malformed_layout', 'message': 'bad layout'}, retry_feedback)\n"
        "    return _result({'widget.py': 'X = 1'}, None, retry_feedback)\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _record({'call': 'commit_cache'})\n"
        "    return None\n"
    )


def _surface_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': 'check_surface', 'component_id': component_id}) + '\\n')\n"
        "    return {'ok': True, 'findings': []}\n"
    )


def _verifier_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': 'verify', 'component_id': component_id}) + '\\n')\n"
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


def _test_author_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': 'author_test'}) + '\\n')\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'criterion_id': 'AC-WIDGET-001',\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': 'verification/widget/generated-test/test_ac_widget_001.py', 'content': ''},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n"
    )


def _llm_endpoint_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': 'complete'}) + '\\n')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )


def test_ac_loop_008_retried_generation_errors_then_pass(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    _write(repo_root / "gen" / "generator" / "generator.py", _generator_source(log_path))
    _write(repo_root / "gen" / "surface-checker" / "surface_checker.py", _surface_source(log_path))
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", _verifier_source(log_path))
    _write(repo_root / "gen" / "test-author" / "test_author.py", _test_author_source(log_path))
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", _llm_endpoint_source(log_path))

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    result = generation_loop.run_attempts(
        "comp-widget", bundle, repo_root, "m", max_attempts=3
    )

    entries = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    generate_calls = [e for e in entries if e.get("call") == "generate"]
    assert len(generate_calls) == 3

    attempts = field(result, "attempts")
    assert len(attempts) == 3
    outcomes = [field(a, "outcome") for a in attempts]
    assert outcomes == ["generation_failed", "generation_failed", "passed"]
    categories = [field(a, "error_category") for a in attempts]
    assert categories == ["missing_asset", "malformed_layout", None]

    assert field(result, "passed") is True
    assert field(result, "stop_reason") == "passed"