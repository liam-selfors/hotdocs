# hotdocs-criterion: sha256:b577e6c1635b55ea7f894348f31038dd563c5e4a1459c5ac447edc60bd277425
import json
from pathlib import Path

import pytest

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE = {
    "component_id": "comp-widget",
    "spec_bundle_hash": "sha256:" + "0" * 64,
    "hint_code": None,
}


def _header(log_path):
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
        "            lines = [l for l in f.read().splitlines() if l.strip()]\n"
        "    except FileNotFoundError:\n"
        "        return 0\n"
        "    return sum(1 for l in lines if json.loads(l).get('fn') == fn)\n"
        "\n"
    )


def _generator_source(log_path, script_path):
    return _header(log_path) + (
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "\n"
        "def _result(bundle, model, retry_feedback, step):\n"
        "    err = step.get('error')\n"
        "    refused = step.get('refused')\n"
        "    files = step.get('files') or {}\n"
        "    return {\n"
        "        'component_id': bundle['component_id'],\n"
        "        'spec_bundle_hash': bundle['spec_bundle_hash'],\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': files,\n"
        "        'model_call_error': ({'category': err, 'message': 'fake ' + err} if err else None),\n"
        "        'refused': refused,\n"
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
        "    _log({'fn': 'generate', 'model': model, 'feedback': retry_feedback})\n"
        "    with open(SCRIPT, encoding='utf-8') as f:\n"
        "        script = json.load(f)\n"
        "    step = script[min(n, len(script) - 1)]\n"
        "    return _result(bundle, model, retry_feedback, step)\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log({'fn': 'commit_cache'})\n"
        "    return None\n"
        "\n"
        "def check_write_allowed(bundle, repo_root=None):\n"
        "    _log({'fn': 'check_write_allowed'})\n"
        "    return None\n"
        "\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    _log({'fn': 'render_prompt_sections'})\n"
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        "\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    _log({'fn': 'write_files'})\n"
        "    return None\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    _log({'fn': 'check_assets'})\n"
        "    return (None, [])\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    _log({'fn': 'check_asset_environment'})\n"
        "    return (None, [])\n"
    )


def _agentic_source(log_path):
    return _header(log_path) + (
        "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        "                     wall_seconds=1800.0, claude_command='claude'):\n"
        "    _log({'fn': 'generate_agentic'})\n"
        "    return {\n"
        "        'component_id': bundle['component_id'],\n"
        "        'spec_bundle_hash': bundle['spec_bundle_hash'],\n"
        "        'model': model, 'prompt_version': 'agent-v2', 'cache_hit': False,\n"
        "        'files': {},\n"
        "        'model_call_error': {'category': 'rate_limit', 'message': 'fake'},\n"
        "        'refused': None, 'retry_feedback': retry_feedback, 'mode': 'agentic',\n"
        "        'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
        "    }\n"
    )


def _surface_source(log_path):
    return _header(log_path) + (
        "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log({'fn': 'check_surface'})\n"
        "    return {'ok': True, 'findings': []}\n"
    )


def _verifier_source(log_path):
    return _header(log_path) + (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log({'fn': 'verify'})\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [],\n"
        "        'requirement_results': {},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
    )


def _test_author_source(log_path):
    return _header(log_path) + (
        "GATE_VERSION = 'generated_test@3.0.0'\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log({'fn': 'author_test'})\n"
        "    return {\n"
        "        'component_id': bundle['component_id'],\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model, 'seed': seed, 'prompt_version': 'v1', 'cache_hit': False,\n"
        "        'file': {'path': 'verification/widget/generated-test/test_x.py', 'content': ''},\n"
        "        'model_call_error': None, 'repair_attempts': 0, 'probe_findings': [],\n"
        "    }\n"
    )


def _llm_endpoint_source(log_path):
    return _header(log_path) + (
        "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log({'fn': 'complete'})\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    )


def _make_repo(tmp_path, script):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    modules = {
        ("generator", "generator"): _generator_source(log_path, script_path),
        ("agentic-generator", "agentic_generator"): _agentic_source(log_path),
        ("surface-checker", "surface_checker"): _surface_source(log_path),
        ("verifier-orchestrator", "verifier_orchestrator"): _verifier_source(log_path),
        ("test-author", "test_author"): _test_author_source(log_path),
        ("llm-endpoint", "llm_endpoint"): _llm_endpoint_source(log_path),
    }
    for (slug, module_name), source in modules.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (module_name + ".py")).write_text(source, encoding="utf-8")
    return repo_root, log_path


def _calls(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _fns(log_path, name):
    return [c for c in _calls(log_path) if c.get("fn") == name]


def test_non_retried_category_ends_loop_with_not_retried(tmp_path):
    repo_root, log_path = _make_repo(
        tmp_path, [{"error": "truncated_response"}, {"error": "rate_limit"}]
    )
    result = generation_loop.run_attempts("comp-widget", BUNDLE, repo_root, "m")

    assert len(_fns(log_path, "generate")) == 2

    attempts = field(result, "attempts")
    assert len(attempts) == 2
    assert [field(a, "outcome") for a in attempts] == [
        "generation_failed",
        "generation_failed",
    ]
    assert [field(a, "error_category") for a in attempts] == [
        "truncated_response",
        "rate_limit",
    ]
    assert field(result, "stop_reason") == "not_retried"

    assert _fns(log_path, "check_surface") == []
    assert _fns(log_path, "verify") == []


def test_refused_ends_loop_at_once(tmp_path):
    repo_root, log_path = _make_repo(tmp_path, [{"refused": "sealed-component"}])
    result = generation_loop.run_attempts(
        "comp-widget", BUNDLE, repo_root, "m", max_attempts=3
    )

    assert len(_fns(log_path, "generate")) == 1

    attempts = field(result, "attempts")
    assert len(attempts) == 1
    assert field(attempts[0], "outcome") == "refused"
    assert field(result, "stop_reason") == "refused"


@pytest.mark.parametrize(
    "kwargs",
    [{"mode": "turbo"}, {"max_attempts": 0}],
    ids=["mode-turbo", "max-attempts-0"],
)
def test_invalid_arguments_raise_before_any_call(tmp_path, kwargs):
    repo_root, log_path = _make_repo(tmp_path, [{"error": "rate_limit"}])
    with pytest.raises(ValueError):
        generation_loop.run_attempts("comp-widget", BUNDLE, repo_root, "m", **kwargs)
    assert _calls(log_path) == []