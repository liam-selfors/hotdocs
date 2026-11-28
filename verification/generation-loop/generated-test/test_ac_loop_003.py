# hotdocs-criterion: sha256:f9c0c386a73c964c6232a520b57f4630c427832757b4ee33d92bf78b86284c2f
import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_module(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def build_fixture(repo_root, log_path, counter_path, reports):
    gen_src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log({'call': 'generate', 'feedback': retry_feedback,\n"
        "          'repr': repr((bundle, model, retry_feedback, repo_root, llm_backend))})\n"
        "    return {\n"
        "        'component_id': 'comp-w',\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'model': model,\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': {'w.py': 'x = 1\\n'},\n"
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
        "def commit_cache(result, repo_root=None):\n"
        "    _log({'call': 'commit_cache'})\n"
    )
    write_module(repo_root, "generator", gen_src)

    agentic_src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,\n"
        "                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,\n"
        "                     wall_seconds=1800.0, claude_command='claude'):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'generate_agentic', 'feedback': retry_feedback,\n"
        "                            'repr': repr((bundle, model, retry_feedback))}) + '\\n')\n"
        "    return {\n"
        "        'component_id': 'comp-w', 'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'model': model, 'prompt_version': 'agent-v2', 'cache_hit': False,\n"
        "        'files': {'w.py': 'x = 1\\n'}, 'model_call_error': None, 'refused': None,\n"
        "        'retry_feedback': retry_feedback, 'mode': 'agentic',\n"
        "        'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
        "    }\n"
    )
    write_module(repo_root, "agentic-generator", agentic_src)

    surface_src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'surface-checker@1.2.0'\n"
        "\n"
        "def check_surface(component_id, repo_root, code_dir=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'check_surface'}) + '\\n')\n"
        "    return {'ok': True, 'findings': []}\n"
    )
    write_module(repo_root, "surface-checker", surface_src)

    verify_src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "COUNTER = " + repr(str(counter_path)) + "\n"
        "REPORTS = " + repr(reports) + "\n"
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    try:\n"
        "        with open(COUNTER, 'r', encoding='utf-8') as f:\n"
        "            n = int(f.read().strip() or '0')\n"
        "    except FileNotFoundError:\n"
        "        n = 0\n"
        "    with open(COUNTER, 'w', encoding='utf-8') as f:\n"
        "        f.write(str(n + 1))\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'verify', 'n': n}) + '\\n')\n"
        "    return REPORTS[min(n, len(REPORTS) - 1)]\n"
    )
    write_module(repo_root, "verifier-orchestrator", verify_src)

    author_src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'generated_test@3.0.0'\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'author_test'}) + '\\n')\n"
        "    return {\n"
        "        'component_id': 'comp-w', 'criterion_id': 'AC-W-1', 'model': model,\n"
        "        'seed': seed, 'prompt_version': 'v1', 'cache_hit': False,\n"
        "        'file': {'path': 'verification/w/generated-test/test_ac_w_1.py',\n"
        "                 'content': 'def test_x():\\n    pass\\n'},\n"
        "        'model_call_error': None, 'repair_attempts': 0, 'probe_findings': [],\n"
        "    }\n"
    )
    write_module(repo_root, "test-author", author_src)

    endpoint_src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'call': 'complete'}) + '\\n')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock',\n"
        "            'model_call_error': None}\n"
    )
    write_module(repo_root, "llm-endpoint", endpoint_src)


def make_report(criteria, overall):
    return {
        "component_id": "comp-w",
        "criteria": criteria,
        "requirement_results": {c["covers"]: c["result"] for c in criteria},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def test_ac_loop_003_feedback_accumulates_failed_requirement_ids_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    counter_path = tmp_path / "verify_counter.txt"

    reports = [
        make_report(
            [
                {"id": "AC-W-3", "covers": "R-W-3", "kind": "generated-test",
                 "result": "fail", "failure_origin": "implementation",
                 "failure_detail": {"message": "w3 failed"}},
                {"id": "AC-W-1", "covers": "R-W-1", "kind": "generated-test",
                 "result": "fail", "failure_origin": "test",
                 "failure_detail": {"message": "w1 failed"}},
                {"id": "AC-W-2", "covers": "R-W-2", "kind": "generated-test",
                 "result": "pass"},
            ],
            "fail",
        ),
        make_report(
            [
                {"id": "AC-W-2", "covers": "R-W-2", "kind": "generated-test",
                 "result": "fail", "failure_origin": "implementation",
                 "failure_detail": {"message": "secret detail"}},
            ],
            "fail",
        ),
        make_report(
            [
                {"id": "AC-W-2", "covers": "R-W-2", "kind": "generated-test",
                 "result": "pass"},
            ],
            "pass",
        ),
    ]
    build_fixture(repo_root, log_path, counter_path, reports)

    result = generation_loop.run_attempts(
        "comp-w",
        {"component_id": "comp-w"},
        repo_root,
        "mock-model",
        retry_feedback=["R-W-9", "R-W-9"],
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    gen_entries = [e for e in entries if e.get("call") == "generate"]

    feedbacks = [e["feedback"] for e in gen_entries]
    assert feedbacks == [
        ["R-W-9"],
        ["R-W-3", "R-W-9"],
        ["R-W-2", "R-W-3", "R-W-9"],
    ]

    attempts = field(result, "attempts")
    assert [field(a, "failed_requirements") for a in attempts] == [
        ["R-W-3"],
        ["R-W-2"],
        [],
    ]

    for e in gen_entries:
        assert "secret detail" not in json.dumps(e)
        assert "secret detail" not in e["repr"]