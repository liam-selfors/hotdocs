# hotdocs-criterion: sha256:3c827a0a450d4785cc25831a62da21a1de10f0ce2cda260c0bd5c44eb829fd5f
import hashlib
import json
from pathlib import Path

import pytest

import agentic_generator


TRANSCRIPT = [{"role": "user", "content": "p"}]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generator_source(log_path):
    return (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(kind, payload):\n"
        "    entry = dict(payload)\n"
        "    entry['kind'] = kind\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry, sort_keys=True, default=str) + '\\n')\n"
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
        "    _log('write_files', {'component_id': component_id, 'files': dict(files),\n"
        "                         'repo_root': str(repo_root)})\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    _log('check_assets', {'component_id': component_id, 'files': dict(files),\n"
        "                          'repo_root': str(repo_root)})\n"
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


def _loop_source(script_path, log_path):
    return (
        "import json\n"
        "from dataclasses import dataclass, field, asdict\n"
        "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry, sort_keys=True, default=str) + '\\n')\n"
        "\n"
        "class ToolUseUnsupported(Exception):\n"
        "    pass\n"
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
        "    _log({'kind': 'args', 'model': model,\n"
        "          'tools': [t.get('name') for t in tools],\n"
        "          'max_turns': max_turns, 'max_tool_calls': max_tool_calls,\n"
        "          'wall_seconds': wall_seconds, 'repo_root': str(repo_root),\n"
        "          'claude_command': claude_command})\n"
        "    with open(SCRIPT, encoding='utf-8') as f:\n"
        "        steps = json.load(f)\n"
        "    for step in steps:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        _log({'kind': 'call', 'name': step['name'], 'arguments': step['arguments'],\n"
        "              'text': text, 'is_error': is_error})\n"
        "    return ToolLoopResult(text='done',\n"
        "                          transcript=[{'role': 'user', 'content': 'p'}],\n"
        "                          turns=3, tool_calls=3, stop='end_turn',\n"
        "                          model_call_error=None)\n"
    )


FIRST_SCRIPT = [
    {"name": "write_file",
     "arguments": {"path": "work/widget_maker/__init__.py", "content": "A = 1"}},
    {"name": "write_file",
     "arguments": {"path": "work/widget_maker/core.py", "content": "B = 2"}},
    {"name": "finish", "arguments": {"summary": "done"}},
]

NOTES_SCRIPT = [
    {"name": "write_file", "arguments": {"path": "work/notes.py", "content": "N = 3"}},
    {"name": "finish", "arguments": {"summary": "done"}},
]


def _setup(root, script):
    root.mkdir(parents=True, exist_ok=True)
    logs = root.parent / (root.name + "-logs")
    logs.mkdir(parents=True, exist_ok=True)
    gen_log = logs / "generator.log"
    loop_log = logs / "loop.log"
    script_path = logs / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")

    gdir = root / "gen" / "generator"
    gdir.mkdir(parents=True)
    (gdir / "generator.py").write_text(_generator_source(gen_log), encoding="utf-8")

    ldir = root / "gen" / "llm-tool-endpoint"
    ldir.mkdir(parents=True)
    (ldir / "llm_tool_endpoint.py").write_text(
        _loop_source(script_path, loop_log), encoding="utf-8")
    return gen_log, loop_log


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _bundle(hint_code=None):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:h",
        "hint_code": hint_code,
    }


@pytest.fixture(autouse=True)
def _no_sandbox(monkeypatch, tmp_path):
    missing = str(tmp_path / "does-not-exist" / "nothing")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)


EXPECTED_FILES = {"widget_maker/__init__.py": "A = 1", "widget_maker/core.py": "B = 2"}


def test_cold_mode_candidate_is_work_files_and_written_once(tmp_path):
    repo_root = tmp_path / "repo-cold"
    gen_log, loop_log = _setup(repo_root, FIRST_SCRIPT)

    result = agentic_generator.generate_agentic(
        _bundle(None), "m", ["R-W-1"], repo_root=repo_root)

    calls = [e for e in _read_log(loop_log) if e["kind"] == "call"]
    assert len(calls) == 3
    assert not any(c["is_error"] for c in calls), calls

    assert field(result, "model_call_error") is None
    assert field(result, "files") == EXPECTED_FILES
    assert field(result, "mode") == "agentic"
    assert field(result, "cache_hit") is False
    assert field(result, "prompt_version") == "agent-v2"
    assert field(result, "prompt_version") == agentic_generator.AGENT_PROMPT_VERSION
    assert field(result, "retry_feedback") == ["R-W-1"]
    assert field(result, "spec_bundle_hash") == "sha256:h"
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 3

    expected_sha = "sha256:" + hashlib.sha256(
        json.dumps(TRANSCRIPT, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    assert field(result, "transcript_sha256") == expected_sha

    writes = [e for e in _read_log(gen_log) if e["kind"] == "write_files"]
    assert len(writes) == 1
    assert writes[0]["component_id"] == "comp-widget-maker"
    assert writes[0]["files"] == EXPECTED_FILES


def test_missing_module_when_only_notes_written(tmp_path):
    repo_root = tmp_path / "repo-missing"
    gen_log, _ = _setup(repo_root, NOTES_SCRIPT)

    result = agentic_generator.generate_agentic(
        _bundle(None), "m", ["R-W-1"], repo_root=repo_root)

    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "missing_module"

    writes = [e for e in _read_log(gen_log) if e["kind"] == "write_files"]
    assert writes == []


def test_hint_mode_returns_script_files_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo-hint"
    gen_log, _ = _setup(repo_root, FIRST_SCRIPT)

    result = agentic_generator.generate_agentic(
        _bundle({"x.py": "1"}), "m", ["R-W-1"], repo_root=repo_root)

    assert field(result, "model_call_error") is None
    assert field(result, "files") == EXPECTED_FILES
    assert field(result, "files") != {"x.py": "1"}

    writes = [e for e in _read_log(gen_log) if e["kind"] == "write_files"]
    assert writes == []