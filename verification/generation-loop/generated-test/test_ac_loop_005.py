# hotdocs-criterion: sha256:17da47620c9369d3a5e57e53fee22edb57871dac561a5153bd7b63019ae47628
import json
from pathlib import Path

import generation_loop


EXPECTED_ATTEMPT_KEYS = {
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _generator_source(gen_log, commit_log):
    return (
        "import json\n"
        "\n"
        "GEN_LOG = " + repr(str(gen_log)) + "\n"
        "COMMIT_LOG = " + repr(str(commit_log)) + "\n"
        "\n"
        "\n"
        "def _count():\n"
        "    try:\n"
        "        with open(GEN_LOG, encoding='utf-8') as f:\n"
        "            return len([l for l in f.readlines() if l.strip()])\n"
        "    except FileNotFoundError:\n"
        "        return 0\n"
        "\n"
        "\n"
        "def _bundle_get(bundle, key):\n"
        "    try:\n"
        "        return bundle[key]\n"
        "    except Exception:\n"
        "        return getattr(bundle, key, None)\n"
        "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    n = _count()\n"
        "    with open(GEN_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'generate', 'n': n + 1, 'model': model,\n"
        "                            'feedback': retry_feedback}) + '\\n')\n"
        "    result = {\n"
        "        'component_id': _bundle_get(bundle, 'component_id'),\n"
        "        'spec_bundle_hash': _bundle_get(bundle, 'spec_bundle_hash'),\n"
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
        "    if n == 0:\n"
        "        result['model_call_error'] = {'category': 'truncated_response',\n"
        "                                      'message': 'reply was truncated'}\n"
        "    else:\n"
        "        result['files'] = {'widget.py': 'X = 1\\n'}\n"
        "        result['transcript_sha256'] = 'sha256:t2'\n"
        "    return result\n"
        "\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    with open(COMMIT_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'commit_cache'}) + '\\n')\n"
        "    return None\n"
    )


def _surface_source(log):
    return (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'check_surface', 'component_id': component_id}) + '\\n')\n"
        "    return {'ok': True, 'findings': []}\n"
    )


def _verifier_source(log):
    return (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'verify', 'component_id': component_id}) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [\n"
        "            {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001',\n"
        "             'kind': 'generated-test', 'result': 'pass'}\n"
        "        ],\n"
        "        'requirement_results': {'R-WIDGET-001': 'pass'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
    )


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_ac_loop_005_on_attempt_and_attempt_records(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    gen_log = logs / "generate.log"
    commit_log = logs / "commit.log"
    surface_log = logs / "surface.log"
    verify_log = logs / "verify.log"

    _write(repo_root / "gen" / "generator" / "generator.py",
           _generator_source(gen_log, commit_log))
    _write(repo_root / "gen" / "surface-checker" / "surface_checker.py",
           _surface_source(surface_log))
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
           _verifier_source(verify_log))

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:bundle",
        "hint_code": None,
    }

    calls = []

    def callback(attempt, generation_result, verification_report):
        calls.append((attempt, generation_result, verification_report))

    result = generation_loop.run_attempts(
        "comp-widget",
        bundle,
        repo_root,
        "mock-model",
        on_attempt=callback,
    )

    # The stand-in generator ran twice.
    gen_calls = _read_log(gen_log)
    assert len(gen_calls) == 2

    # The callback was called twice.
    assert len(calls) == 2
    first_attempt, first_gen, first_report = calls[0]
    second_attempt, second_gen, second_report = calls[1]

    # First call's report is None; second's is the verify result.
    assert first_report is None
    assert second_report is not None
    assert field(second_report, "overall") == "pass"
    assert field(second_report, "component_id") == "comp-widget"
    assert second_report is field(result, "verification_report")

    # Generation results passed to the callback are the stand-in's.
    assert field(first_gen, "model_call_error")["category"] == "truncated_response"
    assert field(first_gen, "transcript_sha256") is None
    assert field(second_gen, "transcript_sha256") == "sha256:t2"

    # Callback attempt entries are numbered 1 and 2 with the transcripts.
    assert field(first_attempt, "number") == 1
    assert field(second_attempt, "number") == 2
    assert field(first_attempt, "transcript_sha256") is None
    assert field(second_attempt, "transcript_sha256") == "sha256:t2"

    # The result's attempts are numbered 1 and 2 with the transcripts.
    attempts = field(result, "attempts")
    assert len(attempts) == 2
    assert [field(a, "number") for a in attempts] == [1, 2]
    assert [field(a, "transcript_sha256") for a in attempts] == [None, "sha256:t2"]

    # The result's generation_result is the second generation result.
    generation_result = field(result, "generation_result")
    assert generation_result is second_gen
    assert field(generation_result, "transcript_sha256") == "sha256:t2"

    # to_dict() attempts entries carry exactly the listed keys
    # (the interface's later `reauthored_tests` key, R-LOOP-007, tolerated).
    as_dict = result.to_dict()
    assert isinstance(as_dict, dict)
    dict_attempts = as_dict["attempts"]
    assert len(dict_attempts) == 2
    for entry in dict_attempts:
        assert isinstance(entry, dict)
        keys = set(entry.keys())
        assert EXPECTED_ATTEMPT_KEYS <= keys
        assert keys - {"reauthored_tests"} == EXPECTED_ATTEMPT_KEYS
    assert [e["number"] for e in dict_attempts] == [1, 2]
    assert [e["transcript_sha256"] for e in dict_attempts] == [None, "sha256:t2"]