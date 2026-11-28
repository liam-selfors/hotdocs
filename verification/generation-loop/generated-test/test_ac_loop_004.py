# hotdocs-criterion: sha256:54a85b53e45ad7973343ec49e1ecf09bd0766b2244161c06467c2bc3ee28ac60
import json
from pathlib import Path

import generation_loop


COMPONENT_ID = "comp-widget"
MODEL = "mock-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _log_helper_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps(entry) + '\\n')\n"
    )


def _generation_result_source(mode_value, transcript_value):
    return (
        "    result = {\n"
        "        'component_id': " + repr(COMPONENT_ID) + ",\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': {'widget.py': '# generation ' + str(n) + '\\n'},\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "        'mode': " + repr(mode_value) + ",\n"
        "        'transcript_sha256': " + repr(transcript_value) + ",\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "    }\n"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(root, overall_sequence):
    repo_root = root / "repo"
    repo_root.mkdir(parents=True)
    log_path = root / "calls.log"
    helper = _log_helper_source(log_path)

    generator_src = (
        helper
        + "_results = []\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    n = len(_results) + 1\n"
        + _generation_result_source("single", None)
        + "    _results.append(result)\n"
        "    _log({'fn': 'generate', 'n': n, 'model': model, 'feedback': retry_feedback})\n"
        "    return result\n"
        "def commit_cache(result, repo_root=None):\n"
        "    idx = None\n"
        "    for i, r in enumerate(_results):\n"
        "        if r is result:\n"
        "            idx = i + 1\n"
        "    _log({'fn': 'commit_cache', 'identity_index': idx, 'count': len(_results)})\n"
        "    return None\n"
    )
    _write(repo_root / "gen" / "generator" / "generator.py", generator_src)

    agentic_src = (
        helper
        + "_results = []\n"
        "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        "                     wall_seconds=1800.0, claude_command='claude'):\n"
        "    n = len(_results) + 1\n"
        + _generation_result_source("agentic", "sha256:" + "1" * 64)
        + "    _results.append(result)\n"
        "    _log({'fn': 'generate_agentic', 'n': n, 'model': model, 'feedback': retry_feedback})\n"
        "    return result\n"
    )
    _write(repo_root / "gen" / "agentic-generator" / "agentic_generator.py", agentic_src)

    surface_src = (
        helper
        + "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    _log({'fn': 'check_surface', 'component_id': component_id})\n"
        "    return {'ok': True, 'findings': []}\n"
    )
    _write(repo_root / "gen" / "surface-checker" / "surface_checker.py", surface_src)

    verifier_src = (
        helper
        + "SEQ = " + repr(list(overall_sequence)) + "\n"
        "_count = [0]\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    i = _count[0]\n"
        "    _count[0] += 1\n"
        "    overall = SEQ[min(i, len(SEQ) - 1)]\n"
        "    _log({'fn': 'verify', 'n': i + 1, 'overall': overall})\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [],\n"
        "        'requirement_results': {},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': overall,\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", verifier_src)

    test_author_src = (
        helper
        + "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log({'fn': 'author_test'})\n"
        "    return {\n"
        "        'component_id': bundle['component_id'],\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': 'verification/widget/generated-test/test_x.py', 'content': ''},\n"
        "        'model_call_error': None,\n"
        "        'repair_attempts': 0,\n"
        "        'probe_findings': [],\n"
        "    }\n"
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", test_author_src)

    llm_src = (
        helper
        + "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log({'fn': 'complete'})\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", llm_src)

    return repo_root, log_path


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def calls(entries, fn):
    return [e for e in entries if e["fn"] == fn]


def test_always_failing_verification_stops_at_max_attempts(tmp_path):
    repo_root, log_path = make_repo(tmp_path / "s1", ["fail"])
    result = generation_loop.run_attempts(
        COMPONENT_ID, {"component_id": COMPONENT_ID}, repo_root, MODEL, max_attempts=2
    )
    entries = read_log(log_path)
    assert len(calls(entries, "generate")) == 2
    assert field(result, "passed") is False
    assert field(result, "stop_reason") == "max_attempts"
    assert calls(entries, "commit_cache") == []


def test_fail_then_pass_single_mode_commits_second_result(tmp_path):
    repo_root, log_path = make_repo(tmp_path / "s2", ["fail", "pass"])
    result = generation_loop.run_attempts(
        COMPONENT_ID, {"component_id": COMPONENT_ID}, repo_root, MODEL,
        mode="single", max_attempts=3,
    )
    entries = read_log(log_path)
    assert len(calls(entries, "generate")) == 2
    assert field(result, "passed") is True
    assert field(result, "stop_reason") == "passed"
    commits = calls(entries, "commit_cache")
    assert len(commits) == 1
    # commit_cache received the very object returned by the second generate call
    assert commits[0]["identity_index"] == 2
    assert commits[0]["count"] == 2
    gen_result = field(result, "generation_result")
    assert field(gen_result, "files") == {"widget.py": "# generation 2\n"}


def test_fail_then_pass_agentic_mode_never_commits(tmp_path):
    repo_root, log_path = make_repo(tmp_path / "s3", ["fail", "pass"])
    result = generation_loop.run_attempts(
        COMPONENT_ID, {"component_id": COMPONENT_ID}, repo_root, MODEL, mode="agentic"
    )
    entries = read_log(log_path)
    assert len(calls(entries, "generate_agentic")) == 2
    assert calls(entries, "generate") == []
    assert calls(entries, "commit_cache") == []
    assert field(result, "passed") is True
    assert field(result, "stop_reason") == "passed"