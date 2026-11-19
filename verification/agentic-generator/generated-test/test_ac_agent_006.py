# hotdocs-criterion: sha256:df715451b9053f3d3352f469751c3828fcceb334482e0bba2da2cb8b0fe7ee0e
import json
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_TEMPLATE_HEAD = (
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "from pathlib import Path\n"
    "\n"
)

GENERATOR_BODY = (
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
    "\n"
    "def _log(path, record):\n"
    "    with open(path, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(record, default=repr) + '\\n')\n"
    "\n"
    "\n"
    "def check_write_allowed(bundle, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def render_prompt_sections(bundle, retry_feedback=None):\n"
    "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
    "\n"
    "\n"
    "def write_files(component_id, files, repo_root=None):\n"
    "    _log(WRITE_LOG, {'component_id': component_id, 'files': files, 'repo_root': str(repo_root)})\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log(ASSETS_LOG, {'component_id': component_id, 'files': files, 'repo_root': str(repo_root)})\n"
    "    for content in files.values():\n"
    "        if 'bad' in content:\n"
    "            return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)

LOOP_HEAD = (
    "import json\n"
    "from dataclasses import dataclass, field, asdict\n"
    "\n"
)

LOOP_BODY = (
    "\n"
    "@dataclass\n"
    "class ToolLoopResult:\n"
    "    text: str = ''\n"
    "    transcript: list = field(default_factory=list)\n"
    "    turns: int = 1\n"
    "    tool_calls: int = 0\n"
    "    stop: str = 'end_turn'\n"
    "    model_call_error: object = None\n"
    "\n"
    "    def to_dict(self):\n"
    "        return asdict(self)\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    with open(ARGS_LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
    "                             'tools': tools, 'max_turns': max_turns,\n"
    "                             'max_tool_calls': max_tool_calls,\n"
    "                             'wall_seconds': wall_seconds,\n"
    "                             'repo_root': str(repo_root),\n"
    "                             'claude_command': claude_command}, default=repr) + '\\n')\n"
    "    with open(SCRIPT, encoding='utf-8') as fh:\n"
    "        script = json.load(fh)\n"
    "    calls = 0\n"
    "    for step in script['steps']:\n"
    "        text, is_error = execute(step['name'], step['arguments'])\n"
    "        calls += 1\n"
    "        with open(RESULTS_LOG, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps([step['name'], step['arguments'], text, is_error], default=repr) + '\\n')\n"
    "    return ToolLoopResult(text='', transcript=[{'role': 'user', 'content': prompt}],\n"
    "                          turns=calls + 1, tool_calls=calls, stop=script['stop'],\n"
    "                          model_call_error=script['model_call_error'])\n"
)


@pytest.mark.parametrize(
    "stop, category",
    [
        ("budget_exhausted", "agent_budget_exhausted"),
        ("end_turn", "agent_unfinished"),
        ("error", "rate_limit"),
    ],
)
def test_no_finish_writes_nothing_and_sets_error(tmp_path, monkeypatch, stop, category):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))

    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    write_log = logs / "write_files.log"
    assets_log = logs / "check_assets.log"
    args_log = logs / "loop_args.log"
    results_log = logs / "loop_results.log"
    script_path = logs / "script.json"

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        GENERATOR_TEMPLATE_HEAD
        + "WRITE_LOG = " + repr(str(write_log)) + "\n"
        + "ASSETS_LOG = " + repr(str(assets_log)) + "\n"
        + GENERATOR_BODY,
        encoding="utf-8",
    )

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        LOOP_HEAD
        + "SCRIPT = " + repr(str(script_path)) + "\n"
        + "ARGS_LOG = " + repr(str(args_log)) + "\n"
        + "RESULTS_LOG = " + repr(str(results_log)) + "\n"
        + LOOP_BODY,
        encoding="utf-8",
    )

    loop_error = {"category": "rate_limit", "message": "m"} if stop == "error" else None
    script = {
        "steps": [
            {
                "name": "write_file",
                "arguments": {"path": "work/widget.py", "content": "def f():\n    return 1\n"},
            }
        ],
        "stop": stop,
        "model_call_error": loop_error,
    }
    script_path.write_text(json.dumps(script), encoding="utf-8")

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    result = agentic_generator.generate_agentic(
        bundle, "anthropic:claude-test", None, repo_root=repo_root
    )

    # The loop stand-in actually ran its script.
    assert args_log.exists()
    assert results_log.exists()

    files = field(result, "files")
    assert not files
    assert dict(files) == {}

    write_calls = write_log.read_text(encoding="utf-8").strip() if write_log.exists() else ""
    assert write_calls == ""

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == category