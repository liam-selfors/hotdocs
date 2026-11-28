# hotdocs-criterion: sha256:e4cd151247d16a2364d9838790e958f834149e0612ac99fe3331d4bc127975ce
import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "\n"
    "def _log(rec):\n"
    "    with open(LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps(rec) + '\\n')\n"
    "\n"
    "def _count(dep):\n"
    "    n = 0\n"
    "    try:\n"
    "        with open(LOG, encoding='utf-8') as f:\n"
    "            for line in f:\n"
    "                line = line.strip()\n"
    "                if line and json.loads(line).get('dep') == dep:\n"
    "                    n += 1\n"
    "    except FileNotFoundError:\n"
    "        pass\n"
    "    return n\n"
    "\n"
)


GENERATOR_BODY = (
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    _log({'dep': 'generate', 'model': model, 'retry_feedback': retry_feedback})\n"
    "    return {\n"
    "        'component_id': 'comp-widget',\n"
    "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
    "        'model': model,\n"
    "        'prompt_version': 'v12',\n"
    "        'cache_hit': False,\n"
    "        'files': {'widget.py': 'X = 1'},\n"
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
    "    _log({'dep': 'commit_cache'})\n"
    "    return None\n"
)


SURFACE_BODY = (
    "GATE_VERSION = 'surface-checker@1.2.0'\n"
    "\n"
    "def check_surface(component_id, repo_root, code_dir=None):\n"
    "    n = _count('check_surface')\n"
    "    _log({'dep': 'check_surface', 'component_id': component_id})\n"
    "    if n == 0:\n"
    "        return {'ok': False, 'findings': [\n"
    "            {'kind': 'import_error', 'message': 'widget could not be imported'}]}\n"
    "    return {'ok': True, 'findings': []}\n"
)


VERIFIER_BODY = (
    "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'dep': 'verify', 'component_id': component_id,\n"
    "          'judge_callable': callable(judge),\n"
    "          'test_author_callable': callable(test_author)})\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [\n"
    "            {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001',\n"
    "             'kind': 'compiled', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-WIDGET-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'assets': [],\n"
    "        'drivers': [],\n"
    "        'overall': 'pass',\n"
    "    }\n"
)


TEST_AUTHOR_BODY = (
    "GATE_VERSION = 'generated_test@3.0.0'\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    _log({'dep': 'author_test', 'model': model, 'seed': seed})\n"
    "    cid = bundle['criterion_id']\n"
    "    return {\n"
    "        'component_id': bundle['component_id'],\n"
    "        'criterion_id': cid,\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'file': {'path': 'verification/widget/generated-test/test_'\n"
    "                 + cid.lower().replace('-', '_') + '.py',\n"
    "                 'content': 'def test_x():\\n    assert True\\n'},\n"
    "        'model_call_error': None,\n"
    "        'repair_attempts': 0,\n"
    "        'probe_findings': [],\n"
    "    }\n"
)


LLM_ENDPOINT_BODY = (
    "DEFAULT_TIMEOUT_SECONDS = 600\n"
    "\n"
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    _log({'dep': 'complete', 'model': model})\n"
    "    return {'text': 'pass', 'model': model, 'backend': 'mock',\n"
    "            'model_call_error': None}\n"
)


def write_fake(repo_root, slug, body, log_path):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    source = "LOG = " + repr(str(log_path)) + "\n" + LOG_HELPER + body
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def read_log(log_path):
    if not log_path.exists():
        return []
    out = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def test_ac_loop_002_surface_failed_then_passed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.jsonl"

    write_fake(repo_root, "generator", GENERATOR_BODY, log_path)
    write_fake(repo_root, "surface-checker", SURFACE_BODY, log_path)
    write_fake(repo_root, "verifier-orchestrator", VERIFIER_BODY, log_path)
    write_fake(repo_root, "test-author", TEST_AUTHOR_BODY, log_path)
    write_fake(repo_root, "llm-endpoint", LLM_ENDPOINT_BODY, log_path)

    bundle = {"component_id": "comp-widget", "spec_bundle_hash": "sha256:" + "0" * 64}

    result = generation_loop.run_attempts("comp-widget", bundle, Path(repo_root), "m")

    attempts = field(result, "attempts")
    assert len(attempts) == 2

    first, second = attempts[0], attempts[1]

    assert field(first, "outcome") == "surface_failed"
    assert field(first, "surface_ok") is False
    assert field(first, "overall") is None

    assert field(second, "outcome") == "passed"
    assert field(second, "surface_ok") is True
    assert field(second, "overall") == "pass"

    calls = read_log(log_path)
    surface_calls = [c for c in calls if c["dep"] == "check_surface"]
    assert len(surface_calls) == 2

    verify_calls = [c for c in calls if c["dep"] == "verify"]
    assert len(verify_calls) == 1
    assert verify_calls[0]["judge_callable"] is True
    assert verify_calls[0]["test_author_callable"] is True