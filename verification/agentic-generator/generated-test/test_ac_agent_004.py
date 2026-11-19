# hotdocs-criterion: sha256:e03bc95add619a40923bde5ddafe0f47ef1f04d3c865d02c3172147a6dd27a47
import json
import os
import sys
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SRC = (
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "\n"
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
    "def check_write_allowed(bundle, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def render_prompt_sections(bundle, retry_feedback=None):\n"
    "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
    "\n"
    "\n"
)


def _write_files_src(write_log):
    return (
        "def write_files(component_id, files, repo_root=None):\n"
        "    with open(" + repr(str(write_log)) + ", 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'component_id': component_id, 'files': files,\n"
        "                            'repo_root': None if repo_root is None else str(repo_root)}) + '\\n')\n"
    )


def _loop_src(script_path, log_path, calls_path):
    return (
        "import json\n"
        "\n"
        "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "CALLS_PATH = " + repr(str(calls_path)) + "\n"
        "\n"
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
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(CALLS_PATH, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
        "                            'tools': tools, 'max_turns': max_turns,\n"
        "                            'max_tool_calls': max_tool_calls,\n"
        "                            'wall_seconds': wall_seconds,\n"
        "                            'repo_root': None if repo_root is None else str(repo_root),\n"
        "                            'claude_command': claude_command}, default=str) + '\\n')\n"
        "    with open(SCRIPT_PATH, encoding='utf-8') as f:\n"
        "        steps = json.load(f)\n"
        "    count = 0\n"
        "    transcript = []\n"
        "    for step in steps:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        count += 1\n"
        "        transcript.append({'role': 'tool', 'content': text})\n"
        "        with open(LOG_PATH, 'a', encoding='utf-8') as f:\n"
        "            f.write(json.dumps([step['name'], step['arguments'], text, bool(is_error)]) + '\\n')\n"
        "    return ToolLoopResult('done', transcript, 1, count, 'end_turn', None)\n"
    )


WIDGET_SRC = "import os\nKEY = os.environ.get('ANTHROPIC_API_KEY')\n"

SCRATCH_TEST_SRC = (
    "import socket\n"
    "\n"
    "import pytest\n"
    "\n"
    "import widget\n"
    "\n"
    "\n"
    "def test_w():\n"
    "    assert widget.KEY is None\n"
    "    with pytest.raises(OSError):\n"
    "        socket.create_connection((\"1.1.1.1\", 80), timeout=3)\n"
)

SCRIPT = [
    {"name": "write_file", "arguments": {"path": "work/widget.py", "content": WIDGET_SRC}},
    {"name": "write_file", "arguments": {"path": "scratch/test_w.py", "content": SCRATCH_TEST_SRC}},
    {"name": "check_import", "arguments": {}},
    {"name": "run_scratch_tests", "arguments": {}},
    {"name": "finish", "arguments": {"summary": "done"}},
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    script_path = logs / "script.json"
    log_path = logs / "results.jsonl"
    calls_path = logs / "calls.jsonl"
    write_log = logs / "writes.jsonl"

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(GENERATOR_SRC + _write_files_src(write_log), encoding="utf-8")

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        _loop_src(script_path, log_path, calls_path), encoding="utf-8"
    )

    script_path.write_text(json.dumps(SCRIPT), encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    return {"repo_root": repo_root, "log_path": log_path}


def _bundle():
    return {"component_id": "comp-widget", "spec_bundle_hash": "sha256:" + "0" * 64, "hint_code": None}


def _run(env, **kwargs):
    log_path = env["log_path"]
    if log_path.exists():
        log_path.unlink()
    result = agentic_generator.generate_agentic(
        _bundle(), "anthropic:claude-test", None, repo_root=env["repo_root"], **kwargs
    )
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_name = {}
    for name, arguments, text, is_error in entries:
        by_name[name] = (text, is_error)
    return result, by_name


def test_sandboxed_run_on_macos(env):
    if not (sys.platform == "darwin" and os.path.exists("/usr/bin/sandbox-exec")):
        pytest.skip("sandbox-exec not available on this platform")
    assert os.environ.get("ANTHROPIC_API_KEY") == "k"

    result, by_name = _run(env)

    text, is_error = by_name["check_import"]
    assert text.startswith("0\n"), text
    assert not is_error

    text, is_error = by_name["run_scratch_tests"]
    assert text.startswith("0\n"), text

    assert field(result, "isolation") == "sandbox-exec"


def test_no_sandbox_refuses_then_unisolated_runs(env, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")

    result, by_name = _run(env)
    text, is_error = by_name["check_import"]
    assert text == "no OS sandbox available: code is not run"
    assert is_error is True
    assert field(result, "isolation") == "none"

    result, by_name = _run(env, allow_unisolated_exec=True)
    text, is_error = by_name["check_import"]
    assert text.startswith("0\n"), text
    assert field(result, "isolation") == "unisolated"