# hotdocs-criterion: sha256:6ecafc87733e4dd0b063725032e45511c0dbc7d459039d856a15a0e66c3ee443
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

import agentic_generator


PREFIX = "hotdocs-agent-"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sandbox_leftovers():
    """Directories, and files ending ".sb", directly under gettempdir()
    whose names start with "hotdocs-agent-"."""
    tmp = tempfile.gettempdir()
    found = set()
    try:
        names = os.listdir(tmp)
    except OSError:
        return found
    for name in names:
        if not name.startswith(PREFIX):
            continue
        full = os.path.join(tmp, name)
        if os.path.isdir(full):
            found.add(("dir", name))
        elif name.endswith(".sb") and os.path.lexists(full):
            found.add(("sb", name))
    return found


def _write_generator_stand_in(repo_root, log_path):
    path = repo_root / "gen" / "generator" / "generator.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry, default=str) + '\\n')\n"
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
        "    _log({'fn': 'write_files', 'component_id': component_id,\n"
        "          'files': files, 'repo_root': repo_root})\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    _log({'fn': 'check_assets', 'component_id': component_id,\n"
        "          'files': files, 'repo_root': repo_root})\n"
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
    path.write_text(src, encoding="utf-8")


def _write_python_adapter_stand_in(repo_root):
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "KIND = 'python'\n"
        "\n"
        "class AssetError(Exception):\n"
        "    pass\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {'names': []}\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': None, 'versions': {},\n"
        "            'lockfile_sha256': None, 'interpreter': sys.executable}\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        raise AssetError('not supported')\n"
        "    return run\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )
    path.write_text(src, encoding="utf-8")


def _write_loop_stand_in(repo_root, script_path, log_path):
    path = repo_root / "gen" / "llm-tool-endpoint" / "llm_tool_endpoint.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "import json\n"
        "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry, default=str) + '\\n')\n"
        "\n"
        "class ToolUseUnsupported(Exception):\n"
        "    pass\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class ToolLoopResult:\n"
        "    text: str = ''\n"
        "    transcript: list = dataclasses.field(default_factory=list)\n"
        "    turns: int = 0\n"
        "    tool_calls: int = 0\n"
        "    stop: str = 'end_turn'\n"
        "    model_call_error: object = None\n"
        "    def to_dict(self):\n"
        "        return dataclasses.asdict(self)\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *,\n"
        "                  max_turns=40, max_tool_calls=120,\n"
        "                  wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    _log({'event': 'args', 'model': model,\n"
        "          'tools': [t.get('name') for t in tools],\n"
        "          'max_turns': max_turns, 'max_tool_calls': max_tool_calls,\n"
        "          'wall_seconds': wall_seconds, 'repo_root': repo_root,\n"
        "          'claude_command': claude_command})\n"
        "    with open(SCRIPT, 'r', encoding='utf-8') as f:\n"
        "        steps = json.load(f)\n"
        "    for step in steps:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        _log({'event': 'call', 'name': step['name'],\n"
        "              'arguments': step['arguments'],\n"
        "              'text': text, 'is_error': is_error})\n"
        "    raise RuntimeError('boom')\n"
        "\n"
        "def serve_mcp(socket_path, tools_path):\n"
        "    return 0\n"
    )
    path.write_text(src, encoding="utf-8")


def test_ac_agent_007_sandbox_removed_when_loop_raises(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    loop_log = logs / "loop.log"
    gen_log = logs / "generator.log"
    script_path = logs / "script.json"

    script_path.write_text(
        json.dumps(
            [
                {
                    "name": "write_file",
                    "arguments": {"path": "work/a.py", "content": "x = 1\n"},
                }
            ]
        ),
        encoding="utf-8",
    )

    _write_generator_stand_in(repo_root, gen_log)
    _write_python_adapter_stand_in(repo_root)
    _write_loop_stand_in(repo_root, script_path, loop_log)

    # No OS sandbox available: code is never run.
    missing = str(tmp_path / "does-not-exist" / "nothing")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    before = _sandbox_leftovers()

    with pytest.raises(RuntimeError) as excinfo:
        agentic_generator.generate_agentic(
            bundle, "claude-sonnet-5", None, repo_root=repo_root
        )

    assert "boom" in str(excinfo.value)

    # The loop stand-in ran and issued the write_file call.
    assert loop_log.is_file(), "loop stand-in was never called"
    entries = [
        json.loads(line)
        for line in loop_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    calls = [e for e in entries if e.get("event") == "call"]
    assert len(calls) == 1
    assert calls[0]["name"] == "write_file"
    assert calls[0]["arguments"] == {"path": "work/a.py", "content": "x = 1\n"}

    after = _sandbox_leftovers()
    new = after - before
    new_dirs = sorted(name for kind, name in new if kind == "dir")
    new_sb = sorted(name for kind, name in new if kind == "sb")
    assert new_dirs == [], "sandbox directory left behind: " + repr(new_dirs)
    assert new_sb == [], "sandbox profile left behind: " + repr(new_sb)