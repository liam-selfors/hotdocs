# hotdocs-criterion: sha256:b560d3e2a367a1127c8f66207448839b585d7f785b240cba13e138ce7583b7b5
import json
import os
import shlex
import stat
import sys
from pathlib import Path

import pytest

import agentic_generator


GENERATOR_STANDIN = '''
import json
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _log(name, payload):
    with open(HERE / (name + ".jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\\n")


@dataclass
class GenerationResult:
    component_id: str = ""
    spec_bundle_hash: str = ""
    model: str = ""
    prompt_version: str = ""
    cache_hit: bool = False
    files: dict = field(default_factory=dict)
    model_call_error: object = None
    refused: object = None
    retry_feedback: object = None
    mode: str = "single"
    transcript_sha256: object = None
    turns: int = 1
    tool_calls: int = 0
    isolation: object = None


def check_write_allowed(bundle, repo_root=None):
    return None


def render_prompt_sections(bundle, retry_feedback=None):
    return [("Spec", "SPEC TEXT"), ("Component interface", "IFACE TEXT")]


def write_files(component_id, files, repo_root=None):
    _log("write_files", {"component_id": component_id, "files": files, "repo_root": str(repo_root)})


def check_assets(component_id, files, repo_root=None):
    _log("check_assets", {"component_id": component_id, "files": files, "repo_root": str(repo_root)})
    for content in files.values():
        if "bad" in content:
            return ("malformed_layout", ["static/app.txt: bad"])
    return (None, [])


def check_asset_environment(component_id, repo_root=None):
    if repo_root is not None and (Path(repo_root) / "NO_ENV").exists():
        return ("environment", ["fake needs fakeprog >= 2"])
    return (None, [])
'''


LOOP_STANDIN = '''
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


class ToolLoopResult:
    def __init__(self, text, transcript, turns, tool_calls, stop, model_call_error):
        self.text = text
        self.transcript = transcript
        self.turns = turns
        self.tool_calls = tool_calls
        self.stop = stop
        self.model_call_error = model_call_error

    def to_dict(self):
        return {
            "text": self.text,
            "transcript": self.transcript,
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "stop": self.stop,
            "model_call_error": self.model_call_error,
        }


def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,
                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,
                  claude_command="claude"):
    with open(HERE / "loop_args.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "system": system, "prompt": prompt, "model": model, "tools": tools,
            "max_turns": max_turns, "max_tool_calls": max_tool_calls,
            "wall_seconds": wall_seconds, "repo_root": str(repo_root),
            "claude_command": claude_command,
        }, default=str) + "\\n")
    script = json.loads((HERE / "script.json").read_text(encoding="utf-8"))
    calls = 0
    for step in script:
        text, is_error = execute(step["name"], step["arguments"])
        calls += 1
        with open(HERE / "calls.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "name": step["name"], "arguments": step["arguments"],
                "text": text, "is_error": bool(is_error),
            }) + "\\n")
    return ToolLoopResult(
        text="done",
        transcript=[{"role": "user", "content": prompt}],
        turns=1,
        tool_calls=calls,
        stop="end_turn",
        model_call_error=None,
    )
'''


WIDGET_SRC = "import os\nKEY = os.environ.get('ANTHROPIC_API_KEY')\n"

SCRATCH_TEST_SRC = (
    "import socket\n"
    "import pytest\n"
    "import widget\n"
    "\n"
    "\n"
    "def test_w():\n"
    "    assert widget.KEY is None\n"
    "    with pytest.raises(OSError):\n"
    "        socket.create_connection((\"1.1.1.1\", 80), timeout=3)\n"
)

FULL_SCRIPT = [
    {"name": "write_file", "arguments": {"path": "work/widget.py", "content": WIDGET_SRC}},
    {"name": "write_file", "arguments": {"path": "scratch/test_w.py", "content": SCRATCH_TEST_SRC}},
    {"name": "check_import", "arguments": {}},
    {"name": "run_scratch_tests", "arguments": {}},
    {"name": "finish", "arguments": {"summary": "done"}},
]

FINISH_ONLY_SCRIPT = [
    {"name": "finish", "arguments": {"summary": "done"}},
]

HAS_SANDBOX_EXEC = sys.platform == "darwin" and os.path.exists("/usr/bin/sandbox-exec")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_repo(root, script):
    root.mkdir(parents=True, exist_ok=True)
    gdir = root / "gen" / "generator"
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / "generator.py").write_text(GENERATOR_STANDIN, encoding="utf-8")
    ldir = root / "gen" / "llm-tool-endpoint"
    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / "llm_tool_endpoint.py").write_text(LOOP_STANDIN, encoding="utf-8")
    (ldir / "script.json").write_text(json.dumps(script), encoding="utf-8")
    return root


def read_calls(root):
    path = root / "gen" / "llm-tool-endpoint" / "calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def call_for(calls, name):
    found = [c for c in calls if c["name"] == name]
    assert found, "no recorded call for " + name + ": " + repr(calls)
    return found[0]


def bundle():
    return {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def run(root, **kwargs):
    return agentic_generator.generate_agentic(bundle(), "claude-sonnet-5-5", None, repo_root=root, **kwargs)


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")


@pytest.mark.skipif(not HAS_SANDBOX_EXEC, reason="needs macOS with /usr/bin/sandbox-exec")
def test_sandbox_exec_runs_code_isolated(tmp_path, api_key):
    root = make_repo(tmp_path / "repo", FULL_SCRIPT)
    result = run(root)
    calls = read_calls(root)
    ci = call_for(calls, "check_import")
    rs = call_for(calls, "run_scratch_tests")
    assert ci["text"].startswith("0\n"), ci
    assert rs["text"].startswith("0\n"), rs
    assert field(result, "isolation") == "sandbox-exec"


@pytest.mark.skipif(not HAS_SANDBOX_EXEC, reason="needs macOS with /usr/bin/sandbox-exec")
def test_isolation_reported_when_nothing_ran(tmp_path, api_key):
    root = make_repo(tmp_path / "repo", FINISH_ONLY_SCRIPT)
    result = run(root)
    assert field(result, "isolation") == "sandbox-exec"


def test_no_sandbox_refuses_unless_allowed(tmp_path, monkeypatch, api_key):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")

    root = make_repo(tmp_path / "repo1", FULL_SCRIPT)
    result = run(root)
    ci = call_for(read_calls(root), "check_import")
    assert ci["text"] == "no OS sandbox available: code is not run"
    assert ci["is_error"] is True
    assert field(result, "isolation") == "none"

    root2 = make_repo(tmp_path / "repo2", FULL_SCRIPT)
    result2 = run(root2, allow_unisolated_exec=True)
    ci2 = call_for(read_calls(root2), "check_import")
    assert ci2["text"].startswith("0\n"), ci2
    assert field(result2, "isolation") == "unisolated"


def test_provisioned_interpreter_is_used(tmp_path, monkeypatch, api_key):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")

    interp_dir = tmp_path / "interp"
    interp_dir.mkdir()
    log = interp_dir / "interp.log"
    script_path = interp_dir / "python.sh"
    script_path.write_text(
        "#!/bin/sh\n"
        + "echo run >> " + shlex.quote(str(log)) + "\n"
        + "exec " + shlex.quote(sys.executable) + ' "$@"\n',
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    root = make_repo(tmp_path / "repo", FULL_SCRIPT)
    kdir = root / "gen" / "kind-python"
    kdir.mkdir(parents=True)
    adapter_src = (
        "from pathlib import Path\n"
        "\n"
        "KIND = 'python'\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {'names': []}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': None, 'versions': {}, 'lockfile_sha256': None,\n"
        "            'interpreter': " + repr(str(script_path)) + "}\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def _run(entry, args):\n"
        "        return None\n"
        "    return _run\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )
    (kdir / "kind_python.py").write_text(adapter_src, encoding="utf-8")

    run(root, allow_unisolated_exec=True)
    ci = call_for(read_calls(root), "check_import")
    assert ci["text"].startswith("0\n"), ci
    assert log.exists()
    lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2, lines