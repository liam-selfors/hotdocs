# hotdocs-criterion: sha256:f67a4f80893def18476ee671b0ae9b1f8e25e042ec85c29f11800b46c7fdce0b
# AC-LOOP-004: the loop stops at the first pass or after max_attempts,
# commits the cache only on a single-mode pass, never in agentic mode.
import json
from pathlib import Path

import generation_loop


COMPONENT_ID = "comp-widget"
MODEL = "mock-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(fn, **kw):\n"
    "    entry = {'fn': fn}\n"
    "    entry.update(kw)\n"
    "    with open(LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps(entry, default=repr) + '\\n')\n"
    "\n"
    "def _next(name):\n"
    "    p = Path(STATE_DIR) / (name + '.count')\n"
    "    n = int(p.read_text()) if p.exists() else 0\n"
    "    n += 1\n"
    "    p.write_text(str(n))\n"
    "    return n\n"
    "\n"
)


def _header(log_path, state_dir):
    return "LOG = " + repr(str(log_path)) + "\n" + "STATE_DIR = " + repr(str(state_dir)) + "\n"


def _gen_result_src(mode_value, transcript_expr):
    return (
        "    result = {\n"
        "        'component_id': bundle['component_id'],\n"
        "        'spec_bundle_hash': bundle['spec_bundle_hash'],\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': {'widget.py': '# generation ' + str(n) + '\\n'},\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "        'mode': " + repr(mode_value) + ",\n"
        "        'transcript_sha256': " + transcript_expr + ",\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "    }\n"
    )


def write_stand_ins(tmp_path, overall_sequence):
    repo_root = tmp_path / "repo"
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    log_path = tmp_path / "calls.jsonl"
    log_path.write_text("", encoding="utf-8")
    head = _header(log_path, state_dir) + COMMON

    generator_src = (
        head
        + "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        + "    n = _next('generate')\n"
        + _gen_result_src("single", "None")
        + "    _log('generate', n=n, obj_id=id(result), feedback=retry_feedback)\n"
        + "    return result\n"
        + "\n"
        + "def commit_cache(result, repo_root=None):\n"
        + "    files = result['files'] if isinstance(result, dict) else result.files\n"
        + "    _log('commit_cache', obj_id=id(result), files=files)\n"
        + "    return None\n"
    )

    agentic_src = (
        head
        + "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        + "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        + "                     wall_seconds=1800.0, claude_command='claude'):\n"
        + "    n = _next('generate_agentic')\n"
        + _gen_result_src("agentic", "'sha256:' + ('0' * 63) + str(n % 10)")
        + "    _log('generate_agentic', n=n, obj_id=id(result), feedback=retry_feedback)\n"
        + "    return result\n"
    )

    surface_src = (
        head
        + "def check_surface(component_id, repo_root, code_dir=None):\n"
        + "    _log('check_surface', component_id=component_id)\n"
        + "    return {'ok': True, 'findings': []}\n"
    )

    verifier_src = (
        head
        + "SEQUENCE = " + repr(list(overall_sequence)) + "\n"
        + "\n"
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        + "    n = _next('verify')\n"
        + "    overall = SEQUENCE[min(n, len(SEQUENCE)) - 1]\n"
        + "    _log('verify', n=n, overall=overall)\n"
        + "    return {\n"
        + "        'component_id': component_id,\n"
        + "        'criteria': [],\n"
        + "        'requirement_results': {},\n"
        + "        'interface_drift': False,\n"
        + "        'mutation_score': None,\n"
        + "        'mutation_error': None,\n"
        + "        'assets': [],\n"
        + "        'overall': overall,\n"
        + "    }\n"
    )

    test_author_src = (
        head
        + "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        + "    _log('author_test')\n"
        + "    return {\n"
        + "        'component_id': bundle['component_id'],\n"
        + "        'criterion_id': bundle['criterion_id'],\n"
        + "        'model': model,\n"
        + "        'seed': seed,\n"
        + "        'prompt_version': 'v1',\n"
        + "        'cache_hit': False,\n"
        + "        'file': {'path': 'x.py', 'content': ''},\n"
        + "        'model_call_error': None,\n"
        + "        'repair_attempts': 0,\n"
        + "        'probe_findings': [],\n"
        + "    }\n"
    )

    endpoint_src = (
        head
        + "def complete(prompt, model, *, backend=None, **params):\n"
        + "    _log('complete')\n"
        + "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )

    files = {
        "generator/generator.py": generator_src,
        "agentic-generator/agentic_generator.py": agentic_src,
        "surface-checker/surface_checker.py": surface_src,
        "verifier-orchestrator/verifier_orchestrator.py": verifier_src,
        "test-author/test_author.py": test_author_src,
        "llm-endpoint/llm_endpoint.py": endpoint_src,
    }
    for rel, src in files.items():
        p = repo_root / "gen" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")
    return repo_root, log_path


def read_calls(log_path):
    lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def calls_of(calls, fn):
    return [c for c in calls if c["fn"] == fn]


def make_bundle():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "hint_code": None,
    }


def test_always_failing_verification_stops_at_max_attempts(tmp_path):
    repo_root, log_path = write_stand_ins(tmp_path, ["fail"])

    result = generation_loop.run_attempts(
        COMPONENT_ID, make_bundle(), repo_root, MODEL, max_attempts=2
    )

    calls = read_calls(log_path)
    assert len(calls_of(calls, "generate")) == 2
    assert field(result, "passed") is False
    assert field(result, "stop_reason") == "max_attempts"
    assert calls_of(calls, "commit_cache") == []


def test_single_mode_pass_on_second_attempt_commits_that_result(tmp_path):
    repo_root, log_path = write_stand_ins(tmp_path, ["fail", "pass"])

    result = generation_loop.run_attempts(
        COMPONENT_ID, make_bundle(), repo_root, MODEL, mode="single", max_attempts=3
    )

    calls = read_calls(log_path)
    generates = calls_of(calls, "generate")
    commits = calls_of(calls, "commit_cache")
    assert len(generates) == 2
    assert field(result, "passed") is True
    assert field(result, "stop_reason") == "passed"
    assert len(commits) == 1
    second = generates[1]
    assert second["n"] == 2
    assert commits[0]["obj_id"] == second["obj_id"]
    assert commits[0]["files"] == {"widget.py": "# generation 2\n"}


def test_agentic_mode_never_calls_generate_or_commit_cache(tmp_path):
    repo_root, log_path = write_stand_ins(tmp_path, ["fail", "pass"])

    generation_loop.run_attempts(
        COMPONENT_ID, make_bundle(), repo_root, MODEL, mode="agentic"
    )

    calls = read_calls(log_path)
    assert len(calls_of(calls, "generate_agentic")) == 2
    assert calls_of(calls, "generate") == []
    assert calls_of(calls, "commit_cache") == []