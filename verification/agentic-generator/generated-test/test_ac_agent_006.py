# hotdocs-criterion: sha256:02baf3a228518fb242e99aae783c2248d757466e2ee6adb9cbb92ec1dd09d24f
import json
import sys
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_generator_stand_in(repo_root, log_dir):
    write_log = str(log_dir / "write_files.log")
    assets_log = str(log_dir / "check_assets.log")
    no_env = str(repo_root / "NO_ENV")
    src = (
        "import json\n"
        "import os\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "WRITE_LOG = " + repr(write_log) + "\n"
        "ASSETS_LOG = " + repr(assets_log) + "\n"
        "NO_ENV = " + repr(no_env) + "\n"
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
        "    with open(WRITE_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'component_id': component_id, 'files': files,"
        " 'repo_root': str(repo_root)}) + '\\n')\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    with open(ASSETS_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'component_id': component_id, 'files': files,"
        " 'repo_root': str(repo_root)}) + '\\n')\n"
        "    for content in files.values():\n"
        "        if 'bad' in content:\n"
        "            return ('malformed_layout', ['static/app.txt: bad'])\n"
        "    return (None, [])\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    if os.path.exists(NO_ENV):\n"
        "        return ('environment', ['fake needs fakeprog >= 2'])\n"
        "    return (None, [])\n"
    )
    d = repo_root / "gen" / "generator"
    d.mkdir(parents=True, exist_ok=True)
    (d / "generator.py").write_text(src)
    return Path(write_log)


def _write_loop_stand_in(repo_root, log_dir, script, stop, model_call_error):
    script_path = log_dir / "script.json"
    script_path.write_text(json.dumps(script))
    args_log = str(log_dir / "loop_args.log")
    calls_log = str(log_dir / "loop_calls.log")
    src = (
        "import json\n"
        "from dataclasses import dataclass, field, asdict\n"
        "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "ARGS_LOG = " + repr(args_log) + "\n"
        "CALLS_LOG = " + repr(calls_log) + "\n"
        "STOP = " + repr(stop) + "\n"
        "MCE = " + repr(model_call_error) + "\n"
        "\n"
        "@dataclass\n"
        "class ToolLoopResult:\n"
        "    text: str = ''\n"
        "    transcript: list = field(default_factory=list)\n"
        "    turns: int = 0\n"
        "    tool_calls: int = 0\n"
        "    stop: str = 'end_turn'\n"
        "    model_call_error: object = None\n"
        "\n"
        "    def to_dict(self):\n"
        "        return asdict(self)\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(ARGS_LOG, 'a') as fh:\n"
        "        fh.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
        "                             'tools': [t.get('name') for t in tools],\n"
        "                             'max_turns': max_turns, 'max_tool_calls': max_tool_calls,\n"
        "                             'wall_seconds': wall_seconds,\n"
        "                             'repo_root': str(repo_root),\n"
        "                             'claude_command': claude_command}) + '\\n')\n"
        "    with open(SCRIPT) as fh:\n"
        "        steps = json.load(fh)\n"
        "    transcript = []\n"
        "    count = 0\n"
        "    for step in steps:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        count += 1\n"
        "        with open(CALLS_LOG, 'a') as fh:\n"
        "            fh.write(json.dumps([step['name'], step['arguments'], text,"
        " bool(is_error)]) + '\\n')\n"
        "        transcript.append({'role': 'user', 'content': text})\n"
        "    return ToolLoopResult(text='', transcript=transcript, turns=len(steps) + 1,\n"
        "                          tool_calls=count, stop=STOP, model_call_error=MCE)\n"
    )
    d = repo_root / "gen" / "llm-tool-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    (d / "llm_tool_endpoint.py").write_text(src)
    return Path(calls_log)


@pytest.mark.parametrize(
    "stop, category",
    [
        ("budget_exhausted", "agent_budget_exhausted"),
        ("end_turn", "agent_unfinished"),
        ("error", "rate_limit"),
    ],
)
def test_unfinished_loop_writes_nothing(tmp_path, monkeypatch, stop, category):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    loop_error = {"category": "rate_limit", "message": "m"} if stop == "error" else None
    script = [
        {"name": "write_file", "arguments": {"path": "work/widget.py", "content": "X = 1\n"}},
    ]
    write_log = _write_generator_stand_in(repo_root, log_dir)
    calls_log = _write_loop_stand_in(repo_root, log_dir, script, stop, loop_error)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    result = agentic_generator.generate_agentic(
        bundle, "anthropic:claude-sonnet-5", repo_root=repo_root
    )

    # The loop stand-in actually ran and its write succeeded.
    assert calls_log.is_file()
    calls = [json.loads(line) for line in calls_log.read_text().splitlines() if line.strip()]
    assert len(calls) == 1
    assert calls[0][0] == "write_file"
    assert calls[0][3] is False, calls[0]

    files = field(result, "files")
    assert files == {} or not files
    assert not files

    assert not write_log.exists() or write_log.read_text().strip() == ""

    mce = field(result, "model_call_error")
    assert mce is not None
    assert field(mce, "category") == category
    message = field(mce, "message")
    assert isinstance(message, str) and message != ""
    if stop == "error":
        assert mce == {"category": "rate_limit", "message": "m"}
    else:
        assert stop in message