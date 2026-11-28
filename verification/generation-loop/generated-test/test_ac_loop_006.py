# hotdocs-criterion: sha256:9ef10bf988a07b390c19c89fe20454b6bb11fec16c617a4e2a247525477fec14
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


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.log"
    llm_log = logs / "llm.log"
    reply_cfg = logs / "reply.json"

    _write(repo_root / "gen" / "widget" / "widget.py", "CODE-MARK = 1\n")
    _write(repo_root / "gen" / "widget" / "__pycache__" / "x.pyc", "PYC-MARK\n")

    author_src = "\n".join([
        "import json",
        "LOG = " + repr(str(author_log)),
        "",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps({'bundle': dict(bundle), 'model': model, 'seed': seed,",
        "                            'repo_root': str(repo_root),",
        "                            'llm_backend_is_none': llm_backend is None}) + '\\n')",
        "    return {",
        "        'component_id': bundle['component_id'],",
        "        'criterion_id': 'AC-WIDGET-001',",
        "        'model': model,",
        "        'seed': seed,",
        "        'prompt_version': 'v1',",
        "        'cache_hit': False,",
        "        'file': {'path': 'verification/widget/generated-test/test_ac_widget_001.py',",
        "                 'content': 'AUTHORED-MARK'},",
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
        "REPLY = " + repr(str(reply_cfg)),
        "",
        "def complete(prompt, model, *, backend=None, **params):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps({'prompt': prompt, 'model': model}) + '\\n')",
        "    with open(REPLY, encoding='utf-8') as f:",
        "        cfg = json.load(f)",
        "    if cfg['kind'] == 'error':",
        "        return {'text': None, 'model': model, 'backend': 'mock',",
        "                'model_call_error': {'category': 'network', 'message': 'down'}}",
        "    return {'text': cfg['text'], 'model': model, 'backend': 'mock',",
        "            'model_call_error': None}",
        "",
    ])
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", llm_src)

    return repo_root, author_log, llm_log, reply_cfg


def _set_reply(reply_cfg, cfg):
    reply_cfg.write_text(json.dumps(cfg), encoding="utf-8")


def _lines(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_ac_loop_006_closures(tmp_path):
    repo_root, author_log, llm_log, reply_cfg = _build_repo(tmp_path)
    _set_reply(reply_cfg, {
        "kind": "text",
        "text": "```json\n{\"result\": \"pass\", \"rationale\": \"ok\"}\n```",
    })

    closures = generation_loop.make_closures("m", 4, repo_root)
    assert isinstance(closures, tuple)
    assert len(closures) == 2
    test_author, judge = closures

    # test_author closure
    authored = test_author(dict(BUNDLE))
    calls = _lines(author_log)
    assert len(calls) == 1
    assert calls[0]["bundle"] == BUNDLE
    assert calls[0]["model"] == "m"
    assert calls[0]["seed"] == 4
    assert field(field(authored, "file"), "content") == "AUTHORED-MARK"

    # judge closure, fenced pass reply
    verdict = judge(dict(BUNDLE))
    assert field(verdict, "result") == "pass"
    assert field(verdict, "rationale") == "ok"
    if isinstance(verdict, dict):
        assert verdict == {"result": "pass", "rationale": "ok"}

    prompts = _lines(llm_log)
    assert len(prompts) == 1
    prompt = prompts[0]["prompt"]
    assert "CRIT" in prompt
    assert "REQ" in prompt
    assert "IFACE" in prompt
    assert "CODE-MARK = 1" in prompt
    assert "PYC-MARK" not in prompt

    # failure replies
    cases = [
        {"kind": "text", "text": json.dumps({"result": "maybe", "rationale": "x"})},
        {"kind": "text", "text": "no json"},
        {"kind": "error"},
    ]
    for i, cfg in enumerate(cases):
        _set_reply(reply_cfg, cfg)
        before = len(_lines(llm_log))
        out = judge(dict(BUNDLE))
        after = len(_lines(llm_log))
        assert after == before + 1, cfg
        assert field(out, "result") == "fail", cfg
        rationale = field(out, "rationale")
        assert isinstance(rationale, str), cfg
        assert rationale.startswith("judge unavailable: "), (cfg, rationale)