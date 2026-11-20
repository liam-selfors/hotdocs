# hotdocs-criterion: sha256:3af97adb1cb2455896623fc77f08bf8673ba1bfb52c63f71b4da6a3882e292f4
import json
from pathlib import Path

import generation_loop


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE = {
    "component_id": "comp-widget",
    "criterion_text": "CRIT",
    "requirement_text": "REQ",
    "interface": "IFACE",
}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _setup(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()

    _write(repo_root / "gen" / "widget" / "widget.py", "CODE-MARK = 1\n")
    pyc = repo_root / "gen" / "widget" / "__pycache__" / "x.pyc"
    pyc.parent.mkdir(parents=True, exist_ok=True)
    pyc.write_bytes(b"PYC-MARK-SHOULD-BE-SKIPPED\n")

    author_log = logs / "author.jsonl"
    llm_log = logs / "llm.jsonl"
    control = logs / "control.json"

    author_src = "\n".join([
        "import json",
        "LOG = " + repr(str(author_log)),
        "",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):",
        "    rec = {'bundle': dict(bundle), 'model': model, 'seed': seed,",
        "           'repo_root': None if repo_root is None else str(repo_root),",
        "           'llm_backend': repr(llm_backend)}",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps(rec) + '\\n')",
        "    return {",
        "        'component_id': bundle['component_id'],",
        "        'criterion_id': 'AC-WIDGET-001',",
        "        'model': model,",
        "        'seed': seed,",
        "        'prompt_version': 'v1',",
        "        'cache_hit': False,",
        "        'file': {'path': 'verification/widget/generated-test/test_ac_widget_001.py',",
        "                 'content': 'def test_x():\\n    pass\\n'},",
        "        'model_call_error': None,",
        "        'repair_attempts': 0,",
        "        'probe_findings': [],",
        "    }",
        "",
    ])
    _write(repo_root / "gen" / "test-author" / "test_author.py", author_src)

    llm_src = "\n".join([
        "import json",
        "LOG = " + repr(str(llm_log)),
        "CONTROL = " + repr(str(control)),
        "",
        "def complete(prompt, model, *, backend=None, **params):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps({'prompt': prompt, 'model': model}) + '\\n')",
        "    with open(CONTROL, encoding='utf-8') as f:",
        "        ctl = json.load(f)",
        "    if ctl.get('error') is not None:",
        "        return {'text': None, 'model': model, 'backend': 'mock',",
        "                'model_call_error': ctl['error']}",
        "    return {'text': ctl['text'], 'model': model, 'backend': 'mock',",
        "            'model_call_error': None}",
        "",
    ])
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", llm_src)

    return repo_root, author_log, llm_log, control


def _set_reply(control, text=None, error=None):
    control.write_text(json.dumps({"text": text, "error": error}), encoding="utf-8")


def _read_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_closures_call_author_test_and_judge_builds_prompt(tmp_path):
    repo_root, author_log, llm_log, control = _setup(tmp_path)
    _set_reply(control, text='```json\n{"result": "pass", "rationale": "ok"}\n```')

    closures = generation_loop.make_closures("m", 4, repo_root)
    assert len(closures) == 2
    test_author, judge = closures

    authored = test_author(dict(BUNDLE))
    records = _read_lines(author_log)
    assert len(records) == 1
    rec = records[0]
    assert rec["bundle"] == BUNDLE
    assert rec["model"] == "m"
    assert rec["seed"] == 4
    assert Path(rec["repo_root"]).resolve() == repo_root.resolve()
    assert field(authored, "component_id") == "comp-widget"
    assert field(authored, "seed") == 4
    assert field(authored, "model") == "m"

    verdict = judge(dict(BUNDLE))
    assert field(verdict, "result") == "pass"
    assert field(verdict, "rationale") == "ok"

    calls = _read_lines(llm_log)
    assert len(calls) == 1
    prompt = calls[0]["prompt"]
    assert "CRIT" in prompt
    assert "REQ" in prompt
    assert "IFACE" in prompt
    assert "CODE-MARK = 1" in prompt
    assert "PYC-MARK-SHOULD-BE-SKIPPED" not in prompt


def test_judge_unavailable_cases_fail(tmp_path):
    repo_root, author_log, llm_log, control = _setup(tmp_path)
    test_author, judge = generation_loop.make_closures("m", 4, repo_root)

    cases = [
        {"text": '{"result": "maybe", "rationale": "x"}', "error": None},
        {"text": "no json", "error": None},
        {"text": None, "error": {"category": "network", "message": "backend unreachable"}},
    ]
    for i, case in enumerate(cases):
        _set_reply(control, text=case["text"], error=case["error"])
        verdict = judge(dict(BUNDLE))
        assert field(verdict, "result") == "fail", case
        rationale = field(verdict, "rationale")
        assert isinstance(rationale, str)
        assert rationale.startswith("judge unavailable: "), (case, rationale)
        assert len(_read_lines(llm_log)) == i + 1