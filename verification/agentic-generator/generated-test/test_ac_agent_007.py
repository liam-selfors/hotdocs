# hotdocs-criterion: sha256:e159da2f2bbefe917e186f3eebd451a2ffe40aeafb9487a52fc10dd8225083f4
import json
import os
import tempfile
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _hotdocs_entries():
    tmp = Path(tempfile.gettempdir())
    dirs = set()
    sb_files = set()
    for entry in tmp.iterdir():
        name = entry.name
        if not name.startswith("hotdocs-agent-"):
            continue
        if entry.is_dir() and not entry.is_symlink():
            dirs.add(name)
        if name.endswith(".sb") and entry.is_file():
            sb_files.add(name)
    return dirs, sb_files


def _write_generator_stand_in(repo_root, log_path):
    src = (
        "import json\n"
        "import dataclasses\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(record):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(record) + '\\n')\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class GenerationResult:\n"
        "    component_id: str = ''\n"
        "    spec_bundle_hash: str = ''\n"
        "    model: str = ''\n"
        "    prompt_version: str = ''\n"
        "    cache_hit: bool = False\n"
        "    files: dict = dataclasses.field(default_factory=dict)\n"
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
        "    _log({'call': 'write_files', 'component_id': component_id,\n"
        "          'files': dict(files), 'repo_root': None if repo_root is None else str(repo_root)})\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    _log({'call': 'check_assets', 'component_id': component_id,\n"
        "          'files': dict(files), 'repo_root': None if repo_root is None else str(repo_root)})\n"
        "    for content in files.values():\n"
        "        if 'bad' in content:\n"
        "            return ('malformed_layout', ['static/app.txt: bad'])\n"
        "    return (None, [])\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():\n"
        "        return ('environment', ['fake needs fakeprog >= 2'])\n"
        "    return (None, [])\n"
    )
    d = repo_root / "gen" / "generator"
    d.mkdir(parents=True, exist_ok=True)
    (d / "generator.py").write_text(src, encoding="utf-8")


def _write_loop_stand_in(repo_root, script_path, log_path):
    src = (
        "import json\n"
        "import dataclasses\n"
        "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(record):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(record) + '\\n')\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class ToolLoopResult:\n"
        "    text: str = ''\n"
        "    transcript: list = dataclasses.field(default_factory=list)\n"
        "    turns: int = 0\n"
        "    tool_calls: int = 0\n"
        "    stop: str = 'end_turn'\n"
        "    model_call_error: object = None\n"
        "\n"
        "    def to_dict(self):\n"
        "        return dataclasses.asdict(self)\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    _log({'call': 'run_tool_loop', 'system': system, 'prompt': prompt,\n"
        "          'model': model, 'tools': [t.get('name') for t in tools],\n"
        "          'max_turns': max_turns, 'max_tool_calls': max_tool_calls,\n"
        "          'wall_seconds': wall_seconds,\n"
        "          'repo_root': None if repo_root is None else str(repo_root),\n"
        "          'claude_command': claude_command})\n"
        "    with open(SCRIPT, encoding='utf-8') as f:\n"
        "        steps = json.load(f)\n"
        "    calls = 0\n"
        "    for step in steps:\n"
        "        if 'raise' in step:\n"
        "            _log({'call': 'raise', 'message': step['raise']})\n"
        "            raise RuntimeError(step['raise'])\n"
        "        calls += 1\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        _log({'call': 'execute', 'name': step['name'],\n"
        "              'arguments': step['arguments'], 'text': text,\n"
        "              'is_error': bool(is_error)})\n"
        "    return ToolLoopResult(text='done', transcript=[], turns=1,\n"
        "                          tool_calls=calls, stop='end_turn',\n"
        "                          model_call_error=None)\n"
    )
    d = repo_root / "gen" / "llm-tool-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    (d / "llm_tool_endpoint.py").write_text(src, encoding="utf-8")


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_agent_007_sandbox_removed_when_loop_raises(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    gen_log = logs / "generator.log"
    loop_log = logs / "loop.log"
    script_path = logs / "script.json"

    script = [
        {"name": "write_file", "arguments": {"path": "work/a.py", "content": "X = 1\n"}},
        {"raise": "boom"},
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")

    _write_generator_stand_in(repo_root, gen_log)
    _write_loop_stand_in(repo_root, script_path, loop_log)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    before_dirs, before_sb = _hotdocs_entries()

    with pytest.raises(RuntimeError, match="boom"):
        agentic_generator.generate_agentic(
            bundle, "anthropic:claude-test", None, repo_root=repo_root
        )

    after_dirs, after_sb = _hotdocs_entries()

    records = _read_log(loop_log)
    calls = [r["call"] for r in records]
    assert "run_tool_loop" in calls, "loop stand-in was not called"
    executes = [r for r in records if r["call"] == "execute"]
    assert len(executes) == 1
    assert executes[0]["name"] == "write_file"
    assert executes[0]["text"] == "wrote work/a.py"
    assert executes[0]["is_error"] is False
    assert "raise" in calls

    new_dirs = after_dirs - before_dirs
    new_sb = after_sb - before_sb
    assert new_dirs == set(), "sandbox directories left behind: " + repr(sorted(new_dirs))
    assert new_sb == set(), "sandbox profile files left behind: " + repr(sorted(new_sb))