# hotdocs-criterion: sha256:1b91d821cf6c28db6ab3e33a0b25e9334fdbe886819b6fdbbab4b4a41f9e0557
import json
import os
import sys
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SOURCE = (
    "import dataclasses\n"
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "\n"
    "LOG_DIR = __import__('os').path.dirname(__import__('os').path.abspath(__file__))\n"
    "\n"
    "def _log(name, payload):\n"
    "    path = __import__('os').path.join(LOG_DIR, name)\n"
    "    with open(path, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps(payload, default=str) + '\\n')\n"
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
    "    _log('write_files.log', [component_id, files, str(repo_root)])\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log('check_assets.log', [component_id, files, str(repo_root)])\n"
    "    for content in files.values():\n"
    "        if 'bad' in content:\n"
    "            return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    import os\n"
    "    if repo_root is not None and os.path.exists(os.path.join(str(repo_root), 'NO_ENV')):\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)


def loop_source(script_path, calls_log, args_log):
    return (
        "import json\n"
        "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "CALLS_LOG = " + repr(str(calls_log)) + "\n"
        "ARGS_LOG = " + repr(str(args_log)) + "\n"
        "\n"
        "class ToolLoopResult:\n"
        "    def __init__(self, text, transcript, turns, tool_calls, stop, model_call_error):\n"
        "        self.text = text\n"
        "        self.transcript = transcript\n"
        "        self.turns = turns\n"
        "        self.tool_calls = tool_calls\n"
        "        self.stop = stop\n"
        "        self.model_call_error = model_call_error\n"
        "    def to_dict(self):\n"
        "        return {'text': self.text, 'transcript': self.transcript, 'turns': self.turns,\n"
        "                'tool_calls': self.tool_calls, 'stop': self.stop,\n"
        "                'model_call_error': self.model_call_error}\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(ARGS_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
        "                            'tools': tools, 'max_turns': max_turns,\n"
        "                            'max_tool_calls': max_tool_calls,\n"
        "                            'wall_seconds': wall_seconds,\n"
        "                            'repo_root': repo_root,\n"
        "                            'claude_command': claude_command}, default=str) + '\\n')\n"
        "    with open(SCRIPT, encoding='utf-8') as f:\n"
        "        steps = json.load(f)\n"
        "    calls = 0\n"
        "    transcript = []\n"
        "    for step in steps:\n"
        "        name = step['name']\n"
        "        arguments = step['arguments']\n"
        "        text, is_error = execute(name, arguments)\n"
        "        calls += 1\n"
        "        transcript.append({'role': 'tool', 'name': name, 'content': text})\n"
        "        with open(CALLS_LOG, 'a', encoding='utf-8') as f:\n"
        "            f.write(json.dumps([name, arguments, text, bool(is_error)]) + '\\n')\n"
        "    return ToolLoopResult(text='done', transcript=transcript, turns=len(steps) + 1,\n"
        "                          tool_calls=calls, stop='end_turn', model_call_error=None)\n"
    )


WIDGET = "import os\nKEY = os.environ.get('ANTHROPIC_API_KEY')\n"

SCRATCH_TEST = (
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
    {"name": "write_file", "arguments": {"path": "work/widget.py", "content": WIDGET}},
    {"name": "write_file", "arguments": {"path": "scratch/test_w.py", "content": SCRATCH_TEST}},
    {"name": "check_import", "arguments": {}},
    {"name": "run_scratch_tests", "arguments": {}},
    {"name": "finish", "arguments": {"summary": "done"}},
]


def make_repo(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    gen_dir = root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(GENERATOR_SOURCE, encoding="utf-8")
    loop_dir = root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    logs = root / "logs"
    logs.mkdir()
    script_path = logs / "script.json"
    script_path.write_text(json.dumps(SCRIPT), encoding="utf-8")
    calls_log = logs / "calls.log"
    args_log = logs / "args.log"
    (loop_dir / "llm_tool_endpoint.py").write_text(
        loop_source(script_path, calls_log, args_log), encoding="utf-8"
    )
    return root, calls_log


def bundle():
    return {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def read_calls(calls_log):
    records = []
    with open(calls_log, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def call_result(records, name):
    for rec in records:
        if rec[0] == name:
            return rec
    raise AssertionError("tool " + repr(name) + " was never called: " + repr(records))


def run(repo_root, **kwargs):
    return agentic_generator.generate_agentic(
        bundle(), "anthropic:claude-test", None, repo_root=repo_root, **kwargs
    )


@pytest.mark.skipif(
    sys.platform != "darwin" or not os.path.exists("/usr/bin/sandbox-exec"),
    reason="needs macOS with /usr/bin/sandbox-exec",
)
def test_sandbox_exec_runs_code_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/usr/bin/sandbox-exec")
    repo_root, calls_log = make_repo(tmp_path / "repo")

    result = run(repo_root)
    records = read_calls(calls_log)

    ci = call_result(records, "check_import")
    assert ci[2].startswith("0\n"), ci
    rs = call_result(records, "run_scratch_tests")
    assert rs[2].startswith("0\n"), rs
    assert field(result, "isolation") == "sandbox-exec"


def test_no_sandbox_refuses_unless_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")

    repo_root, calls_log = make_repo(tmp_path / "repo1")
    result = run(repo_root)
    records = read_calls(calls_log)
    ci = call_result(records, "check_import")
    assert ci[2] == "no OS sandbox available: code is not run", ci
    assert ci[3] is True, ci
    assert field(result, "isolation") == "none"

    repo_root2, calls_log2 = make_repo(tmp_path / "repo2")
    result2 = run(repo_root2, allow_unisolated_exec=True)
    records2 = read_calls(calls_log2)
    ci2 = call_result(records2, "check_import")
    assert ci2[2].startswith("0\n"), ci2
    assert field(result2, "isolation") == "unisolated"