# hotdocs-criterion: sha256:f3aa393885ee68a18520bebf9f8e5a1394ad17a1d6052380e6255ccceb564021
import json
import os
from pathlib import Path

import agentic_generator


CANARY = "CANARY-7f3a"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generator_stand_in_source(log_dir):
    write_log = str(log_dir / "write_files.jsonl")
    assets_log = str(log_dir / "check_assets.jsonl")
    return (
        "import json\n"
        "import os\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "WRITE_LOG = " + repr(write_log) + "\n"
        "ASSETS_LOG = " + repr(assets_log) + "\n"
        "\n"
        "@dataclass\n"
        "class GenerationResult:\n"
        "    component_id: str = ''\n"
        "    spec_bundle_hash: str = ''\n"
        "    model: str = ''\n"
        "    prompt_version: str = ''\n"
        "    cache_hit: bool = False\n"
        "    files: dict = field(default_factory=dict)\n"
        "    model_call_error: object = None\n"
        "    refused: object = None\n"
        "    retry_feedback: object = None\n"
        "    mode: str = 'single'\n"
        "    transcript_sha256: object = None\n"
        "    turns: int = 1\n"
        "    tool_calls: int = 0\n"
        "    isolation: object = None\n"
        "\n"
        "def check_write_allowed(bundle, repo_root=None):\n"
        "    return None\n"
        "\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        "\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    with open(WRITE_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'component_id': component_id, 'files': files,\n"
        "                            'repo_root': str(repo_root)}) + '\\n')\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    with open(ASSETS_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'component_id': component_id, 'files': files,\n"
        "                            'repo_root': str(repo_root)}) + '\\n')\n"
        "    for content in files.values():\n"
        "        if 'bad' in content:\n"
        "            return ('malformed_layout', ['static/app.txt: bad'])\n"
        "    return (None, [])\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    if repo_root is not None and os.path.exists(os.path.join(str(repo_root), 'NO_ENV')):\n"
        "        return ('environment', ['fake needs fakeprog >= 2'])\n"
        "    return (None, [])\n"
    )


def _loop_stand_in_source(args_log, calls_log, script_path):
    return (
        "import json\n"
        "from types import SimpleNamespace\n"
        "\n"
        "ARGS_LOG = " + repr(str(args_log)) + "\n"
        "CALLS_LOG = " + repr(str(calls_log)) + "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "\n"
        "def _tool_name(tool):\n"
        "    return tool['name'] if isinstance(tool, dict) else getattr(tool, 'name', None)\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(ARGS_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
        "                            'tools': [_tool_name(t) for t in tools]}) + '\\n')\n"
        "    with open(SCRIPT, encoding='utf-8') as f:\n"
        "        steps = json.load(f)\n"
        "    count = [0]\n"
        "    def call(name, arguments):\n"
        "        text, is_error = execute(name, arguments)\n"
        "        count[0] += 1\n"
        "        with open(CALLS_LOG, 'a', encoding='utf-8') as f:\n"
        "            f.write(json.dumps({'name': name, 'arguments': arguments,\n"
        "                                'text': text, 'is_error': bool(is_error)}) + '\\n')\n"
        "        return text, is_error\n"
        "    for step in steps:\n"
        "        text, is_error = call(step['name'], dict(step['arguments']))\n"
        "        if step.get('read_listed') and not is_error:\n"
        "            for line in text.split('\\n'):\n"
        "                if line:\n"
        "                    call('read_file', {'path': line})\n"
        "    return SimpleNamespace(text='done', transcript=[], turns=1,\n"
        "                           tool_calls=count[0], stop='end_turn',\n"
        "                           model_call_error=None)\n"
    )


def test_ac_agent_008_no_repository_text_reaches_model(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))

    repo_root = Path(os.path.realpath(str(tmp_path / "repo")))
    repo_root.mkdir(parents=True)
    log_dir = Path(os.path.realpath(str(tmp_path / "logs")))
    log_dir.mkdir()

    acceptance = repo_root / "specs" / "components" / "widget" / "acceptance" / "AC-W-1.md"
    acceptance.parent.mkdir(parents=True)
    acceptance.write_text("# AC-W-1\n\nCovers: R-W-1\n\n" + CANARY + "\n", encoding="utf-8")

    verification = repo_root / "verification" / "widget" / "test_w.py"
    verification.parent.mkdir(parents=True)
    verification.write_text("# " + CANARY + "\ndef test_w():\n    assert True\n", encoding="utf-8")

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(_generator_stand_in_source(log_dir), encoding="utf-8")

    args_log = log_dir / "loop_args.jsonl"
    calls_log = log_dir / "loop_calls.jsonl"
    script_path = log_dir / "script.json"
    script = [
        {"name": "list_files", "arguments": {"path": "bundle"}, "read_listed": True},
        {"name": "list_files", "arguments": {"path": "work"}, "read_listed": True},
        {"name": "list_files", "arguments": {"path": "scratch"}, "read_listed": True},
        {"name": "read_file",
         "arguments": {"path": "../specs/components/widget/acceptance/AC-W-1.md"}},
        {"name": "read_file",
         "arguments": {"path": "bundle/../../verification/widget/test_w.py"}},
        {"name": "read_file", "arguments": {"path": str(acceptance)}},
        {"name": "finish", "arguments": {"summary": "done"}},
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        _loop_stand_in_source(args_log, calls_log, script_path), encoding="utf-8"
    )

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    agentic_generator.generate_agentic(bundle, "m", repo_root=repo_root)

    assert args_log.is_file(), "loop stand-in was never called"
    arg_records = [json.loads(l) for l in args_log.read_text(encoding="utf-8").splitlines() if l]
    assert arg_records
    for rec in arg_records:
        assert CANARY not in (rec["system"] or "")
        assert CANARY not in (rec["prompt"] or "")

    assert calls_log.is_file(), "no tool call results were recorded"
    call_records = [json.loads(l) for l in calls_log.read_text(encoding="utf-8").splitlines() if l]

    names = [r["name"] for r in call_records]
    assert names.count("list_files") == 3
    assert "finish" in names
    paths_read = [r["arguments"].get("path") for r in call_records if r["name"] == "read_file"]
    assert "../specs/components/widget/acceptance/AC-W-1.md" in paths_read
    assert "bundle/../../verification/widget/test_w.py" in paths_read
    assert str(acceptance) in paths_read

    for rec in call_records:
        assert CANARY not in (rec["text"] or ""), (
            "repository text leaked via " + rec["name"] + " " + repr(rec["arguments"])
        )