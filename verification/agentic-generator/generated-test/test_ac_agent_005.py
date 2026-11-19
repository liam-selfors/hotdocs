# hotdocs-criterion: sha256:7c1e61284999b2788b5c8d4f9ffb8fe0f863a1f672b4bfad17078fb345215fef
import hashlib
import json
from pathlib import Path

import pytest

import agentic_generator


TRANSCRIPT = [{"role": "user", "content": "p"}]

FIRST_SCRIPT = [
    {"name": "write_file", "arguments": {"path": "work/widget_maker/__init__.py", "content": "A = 1"}},
    {"name": "write_file", "arguments": {"path": "work/widget_maker/core.py", "content": "B = 2"}},
    {"name": "finish", "arguments": {"summary": "done"}},
]

NOTES_SCRIPT = [
    {"name": "write_file", "arguments": {"path": "work/notes.py", "content": "N = 1"}},
    {"name": "finish", "arguments": {"summary": "done"}},
]

EXPECTED_FILES = {"widget_maker/__init__.py": "A = 1", "widget_maker/core.py": "B = 2"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generator_source(write_log):
    return (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "WRITE_LOG = " + repr(str(write_log)) + "\n"
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
        "        f.write(json.dumps({'component_id': component_id, 'files': dict(files),\n"
        "                            'repo_root': None if repo_root is None else str(repo_root)}) + '\\n')\n"
    )


def _loop_source(script_path, loop_log):
    return (
        "import json\n"
        "\n"
        "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        "LOOP_LOG = " + repr(str(loop_log)) + "\n"
        "TRANSCRIPT = " + repr(TRANSCRIPT) + "\n"
        "\n"
        "class ToolLoopResult:\n"
        "    def __init__(self, text, transcript, turns, tool_calls, stop, model_call_error):\n"
        "        self.text = text\n"
        "        self.transcript = transcript\n"
        "        self.turns = turns\n"
        "        self.tool_calls = tool_calls\n"
        "        self.stop = stop\n"
        "        self.model_call_error = model_call_error\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'text': self.text, 'transcript': self.transcript, 'turns': self.turns,\n"
        "                'tool_calls': self.tool_calls, 'stop': self.stop,\n"
        "                'model_call_error': self.model_call_error}\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOOP_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry, default=str) + '\\n')\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40, max_tool_calls=120,\n"
        "                  wall_seconds=1800.0, repo_root=None, claude_command='claude'):\n"
        "    _log({'kind': 'args', 'system': system, 'prompt': prompt, 'model': model,\n"
        "          'tools': [t.get('name') for t in tools], 'max_turns': max_turns,\n"
        "          'max_tool_calls': max_tool_calls, 'wall_seconds': wall_seconds,\n"
        "          'repo_root': None if repo_root is None else str(repo_root),\n"
        "          'claude_command': claude_command})\n"
        "    with open(SCRIPT_PATH, encoding='utf-8') as f:\n"
        "        script = json.load(f)\n"
        "    for step in script:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        _log({'kind': 'step', 'name': step['name'], 'arguments': step['arguments'],\n"
        "              'text': text, 'is_error': is_error})\n"
        "    return ToolLoopResult('done', TRANSCRIPT, 3, 3, 'end_turn', None)\n"
    )


def _setup(tmp_path, script, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    write_log = logs / "write_files.log"
    loop_log = logs / "loop.log"
    script_path = logs / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(_generator_source(write_log), encoding="utf-8")

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(_loop_source(script_path, loop_log), encoding="utf-8")

    missing = str(tmp_path / "no-such-sandbox-binary")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)
    return repo_root, write_log, loop_log


def _read_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _bundle(hint_code=None):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:h",
        "hint_code": hint_code,
    }


def test_cold_mode_candidate_is_work_dir_and_written_once(tmp_path, monkeypatch):
    repo_root, write_log, loop_log = _setup(tmp_path, FIRST_SCRIPT, monkeypatch)

    result = agentic_generator.generate_agentic(_bundle(), "m", ["R-W-1"], repo_root=repo_root)

    steps = [e for e in _read_lines(loop_log) if e.get("kind") == "step"]
    assert len(steps) == 3
    assert all(not s["is_error"] for s in steps), steps

    assert field(result, "files") == EXPECTED_FILES
    assert field(result, "model_call_error") is None
    assert field(result, "mode") == "agentic"
    assert field(result, "cache_hit") is False
    assert field(result, "prompt_version") == "agent-v1"
    assert field(result, "prompt_version") == agentic_generator.AGENT_PROMPT_VERSION
    assert field(result, "retry_feedback") == ["R-W-1"]
    assert field(result, "spec_bundle_hash") == "sha256:h"
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 3
    expected_sha = "sha256:" + hashlib.sha256(
        json.dumps(TRANSCRIPT, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    assert field(result, "transcript_sha256") == expected_sha

    writes = _read_lines(write_log)
    assert len(writes) == 1
    assert writes[0]["component_id"] == "comp-widget-maker"
    assert writes[0]["files"] == EXPECTED_FILES
    assert writes[0]["repo_root"] is not None
    assert Path(writes[0]["repo_root"]).resolve() == repo_root.resolve()


def test_missing_module_gives_error_and_no_write(tmp_path, monkeypatch):
    repo_root, write_log, loop_log = _setup(tmp_path, NOTES_SCRIPT, monkeypatch)

    result = agentic_generator.generate_agentic(_bundle(), "m", ["R-W-1"], repo_root=repo_root)

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "missing_module"
    assert _read_lines(write_log) == []


def test_hint_mode_returns_candidate_not_hint_code_and_writes_nothing(tmp_path, monkeypatch):
    repo_root, write_log, loop_log = _setup(tmp_path, FIRST_SCRIPT, monkeypatch)

    result = agentic_generator.generate_agentic(
        _bundle(hint_code={"x.py": "1"}), "m", ["R-W-1"], repo_root=repo_root
    )

    assert field(result, "files") == EXPECTED_FILES
    assert field(result, "files") != {"x.py": "1"}
    assert field(result, "model_call_error") is None
    assert _read_lines(write_log) == []