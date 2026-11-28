# hotdocs-criterion: sha256:44a1725771db126d4de075ca91ef6fdcb4edbfa2175b2479932eceb90df7071c
import json
import sys
import types
from pathlib import Path

import pytest

import generation_loop


REGISTRY_NAME = "ac_loop_005_test_registry"

ATTEMPT_KEYS = {
    "number",
    "outcome",
    "retry_feedback",
    "error_category",
    "surface_ok",
    "overall",
    "failed_requirements",
    "transcript_sha256",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def header(log_path, registry_name):
    return (
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REG = " + repr(registry_name) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry, default=str) + '\\n')\n"
        "\n"
    )


def generator_source(log_path, counter_path, registry_name):
    return header(log_path, registry_name) + (
        "COUNTER = " + repr(str(counter_path)) + "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    p = Path(COUNTER)\n"
        "    n = int(p.read_text()) + 1 if p.exists() else 1\n"
        "    p.write_text(str(n))\n"
        "    _log({'fn': 'generate', 'n': n, 'model': model, 'retry_feedback': retry_feedback})\n"
        "    base = {\n"
        "        'component_id': 'comp-foo',\n"
        "        'spec_bundle_hash': 'sha256:bundle',\n"
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
        "    if n == 1:\n"
        "        res = dict(base)\n"
        "        res['model_call_error'] = {'category': 'truncated_response', 'message': 'reply truncated'}\n"
        "    else:\n"
        "        res = dict(base)\n"
        "        res['files'] = {'foo.py': 'X = 1\\n'}\n"
        "        res['transcript_sha256'] = 'sha256:t2'\n"
        "    sys.modules[REG].generation_results.append(res)\n"
        "    return res\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log({'fn': 'commit_cache'})\n"
        "    return None\n"
    )


def agentic_source(log_path, registry_name):
    return header(log_path, registry_name) + (
        "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        "                     wall_seconds=1800.0, claude_command='claude'):\n"
        "    _log({'fn': 'generate_agentic'})\n"
        "    raise AssertionError('generate_agentic must not be called in single mode')\n"
    )


def surface_source(log_path, registry_name):
    return header(log_path, registry_name) + (
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log({'fn': 'check_surface', 'component_id': component_id})\n"
        "    res = {'ok': True, 'findings': []}\n"
        "    sys.modules[REG].surface_results.append(res)\n"
        "    return res\n"
        "\n"
        "GATE_VERSION = 'surface-checker@1.2.0'\n"
    )


def verifier_source(log_path, registry_name):
    return header(log_path, registry_name) + (
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log({'fn': 'verify', 'component_id': component_id})\n"
        "    res = {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [\n"
        "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'},\n"
        "        ],\n"
        "        'requirement_results': {'R-FOO-001': 'pass'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 1.0,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
        "    sys.modules[REG].verify_results.append(res)\n"
        "    return res\n"
    )


def author_stub_source(log_path, registry_name):
    return header(log_path, registry_name) + (
        "GATE_VERSION = 'generated_test@3.0.0'\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log({'fn': 'author_test'})\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': 'AC-FOO-001',\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': 'verification/foo/generated-test/test_ac_foo_001.py', 'content': ''},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n"
    )


def llm_endpoint_source(log_path, registry_name):
    return header(log_path, registry_name) + (
        "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log({'fn': 'complete'})\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )


@pytest.fixture
def registry():
    reg = types.ModuleType(REGISTRY_NAME)
    reg.generation_results = []
    reg.surface_results = []
    reg.verify_results = []
    sys.modules[REGISTRY_NAME] = reg
    try:
        yield reg
    finally:
        sys.modules.pop(REGISTRY_NAME, None)


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_loop_005_on_attempt_and_attempt_records(tmp_path, registry):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    log_path = state / "calls.log"
    counter_path = state / "generate_counter.txt"

    gen = repo_root / "gen"
    write(gen / "generator" / "generator.py", generator_source(log_path, counter_path, REGISTRY_NAME))
    write(gen / "agentic-generator" / "agentic_generator.py", agentic_source(log_path, REGISTRY_NAME))
    write(gen / "surface-checker" / "surface_checker.py", surface_source(log_path, REGISTRY_NAME))
    write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", verifier_source(log_path, REGISTRY_NAME))
    write(gen / "test-author" / "test_author.py", author_stub_source(log_path, REGISTRY_NAME))
    write(gen / "llm-endpoint" / "llm_endpoint.py", llm_endpoint_source(log_path, REGISTRY_NAME))

    calls = []

    def callback(attempt, generation_result, verification_report):
        calls.append((attempt, generation_result, verification_report))

    bundle = {"component_id": "comp-foo", "spec_bundle_hash": "sha256:bundle"}

    result = generation_loop.run_attempts(
        "comp-foo", bundle, repo_root, "mock-model",
        max_attempts=3, on_attempt=callback,
    )

    # The stand-ins really ran: two generations, one surface check, one verify.
    log = read_log(log_path)
    fns = [entry["fn"] for entry in log]
    assert fns.count("generate") == 2
    assert fns.count("check_surface") == 1
    assert fns.count("verify") == 1
    assert len(registry.generation_results) == 2
    assert len(registry.verify_results) == 1

    # The callback was called twice.
    assert len(calls) == 2

    # First call's report is None; second's is the verify result itself.
    assert calls[0][2] is None
    assert calls[1][2] is registry.verify_results[0]

    # Each call received its own attempt's generation result, the very object.
    assert calls[0][1] is registry.generation_results[0]
    assert calls[1][1] is registry.generation_results[1]

    # Attempts numbered 1 and 2 with the transcript hashes copied.
    assert [field(c[0], "number") for c in calls] == [1, 2]
    assert [field(c[0], "transcript_sha256") for c in calls] == [None, "sha256:t2"]

    attempts = field(result, "attempts")
    assert len(attempts) == 2
    assert [field(a, "number") for a in attempts] == [1, 2]
    assert [field(a, "transcript_sha256") for a in attempts] == [None, "sha256:t2"]

    # The result's generation_result is the second generation result.
    assert field(result, "generation_result") is registry.generation_results[1]
    assert field(field(result, "generation_result"), "transcript_sha256") == "sha256:t2"

    # to_dict() gives attempt entries with exactly the stated keys
    # (reauthored_tests, which the AttemptLoopResult interface also lists, tolerated).
    as_dict = result.to_dict()
    assert isinstance(as_dict, dict)
    dict_attempts = as_dict["attempts"]
    assert len(dict_attempts) == 2
    allowed_extra = {"reauthored_tests"}
    for entry in dict_attempts:
        assert isinstance(entry, dict)
        keys = set(entry.keys())
        assert ATTEMPT_KEYS <= keys
        assert keys - ATTEMPT_KEYS <= allowed_extra
    assert [e["number"] for e in dict_attempts] == [1, 2]
    assert [e["transcript_sha256"] for e in dict_attempts] == [None, "sha256:t2"]