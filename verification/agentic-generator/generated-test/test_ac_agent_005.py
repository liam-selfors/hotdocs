# hotdocs-criterion: sha256:5573f361ac9a5a697ecbb4d8cd3a21e0972523f6b1982d97b45914fa741e651a
import agentic_generator

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TRANSCRIPT = [{"role": "user", "content": "p"}]

FIRST_SCRIPT = [
    {"name": "write_file", "arguments": {"path": "work/widget_maker/__init__.py", "content": "A = 1"}},
    {"name": "write_file", "arguments": {"path": "work/widget_maker/core.py", "content": "B = 2"}},
    {"name": "finish", "arguments": {"summary": "done"}},
]

NOTES_SCRIPT = [
    {"name": "write_file", "arguments": {"path": "work/notes.py", "content": "N = 0"}},
    {"name": "finish", "arguments": {"summary": "done"}},
]


GENERATOR_BODY = '''
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


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


def _log(name, record):
    with open(os.path.join(LOG_DIR, name), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\\n")


def check_write_allowed(bundle, repo_root=None):
    return None


def render_prompt_sections(bundle, retry_feedback=None):
    return [("Spec", "SPEC TEXT"), ("Component interface", "IFACE TEXT")]


def write_files(component_id, files, repo_root=None):
    _log("write_files.log", {"component_id": component_id, "files": dict(files), "repo_root": None if repo_root is None else str(repo_root)})


def check_assets(component_id, files, repo_root=None):
    _log("check_assets.log", {"component_id": component_id, "files": dict(files), "repo_root": None if repo_root is None else str(repo_root)})
    for content in files.values():
        if "bad" in content:
            return ("malformed_layout", ["static/app.txt: bad"])
    return (None, [])


def check_asset_environment(component_id, repo_root=None):
    if repo_root is not None and (Path(repo_root) / "NO_ENV").exists():
        return ("environment", ["fake needs fakeprog >= 2"])
    return (None, [])
'''


LOOP_BODY = '''
import dataclasses
import json
import os
from dataclasses import dataclass


@dataclass
class ToolLoopResult:
    text: str
    transcript: list
    turns: int
    tool_calls: int
    stop: str
    model_call_error: object = None

    def to_dict(self):
        return dataclasses.asdict(self)


def _log(name, record):
    with open(os.path.join(LOG_DIR, name), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\\n")


def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,
                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,
                  claude_command="claude"):
    _log("loop_args.log", {
        "system": system,
        "prompt": prompt,
        "model": model,
        "tools": [t.get("name") for t in tools],
        "max_turns": max_turns,
        "max_tool_calls": max_tool_calls,
        "wall_seconds": wall_seconds,
        "repo_root": None if repo_root is None else str(repo_root),
        "claude_command": claude_command,
    })
    with open(SCRIPT, "r", encoding="utf-8") as handle:
        steps = json.load(handle)
    for step in steps:
        text, is_error = execute(step["name"], step["arguments"])
        _log("execute.log", {"name": step["name"], "arguments": step["arguments"], "text": text, "is_error": is_error})
    return ToolLoopResult(
        text="done",
        transcript=[{"role": "user", "content": "p"}],
        turns=3,
        tool_calls=3,
        stop="end_turn",
        model_call_error=None,
    )
'''


KIND_PYTHON_BODY = '''
import sys

KIND = "python"


def layout_errors(asset_file):
    return []


def surface(asset_file):
    return {"names": []}


def provision(repo_root):
    return {"ok": True, "reason": None, "versions": {"python": sys.version.split()[0]},
            "lockfile_sha256": None, "interpreter": sys.executable}


def guidance():
    return {"generator": "gen guidance", "test_author": "test guidance"}


def asset_runner(asset_file):
    def run(entry, args):
        return None
    return run


def strength_sites(asset_file):
    return []


def apply_site(asset_file, site):
    return None
'''


def _setup(tmp_path, monkeypatch, script):
    repo = tmp_path / "repo"
    logs = tmp_path / "logs"
    repo.mkdir()
    logs.mkdir()
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")

    gen_dir = repo / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        "LOG_DIR = " + repr(str(logs)) + "\n" + GENERATOR_BODY, encoding="utf-8"
    )

    loop_dir = repo / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        "LOG_DIR = " + repr(str(logs)) + "\n" + "SCRIPT = " + repr(str(script_path)) + "\n" + LOOP_BODY,
        encoding="utf-8",
    )

    kind_dir = repo / "gen" / "kind-python"
    kind_dir.mkdir(parents=True)
    (kind_dir / "kind_python.py").write_text(KIND_PYTHON_BODY, encoding="utf-8")

    missing = str(tmp_path / "no-such-sandbox-program")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)
    return repo, logs


def _read_log(logs, name):
    path = logs / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _bundle(hint_code=None):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:h",
        "hint_code": hint_code,
    }


EXPECTED_FILES = {"widget_maker/__init__.py": "A = 1", "widget_maker/core.py": "B = 2"}


def _expected_sha():
    digest = hashlib.sha256(
        json.dumps(TRANSCRIPT, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return "sha256:" + digest


def test_cold_mode_candidate_is_work_dir_and_written_once(tmp_path, monkeypatch):
    repo, logs = _setup(tmp_path, monkeypatch, FIRST_SCRIPT)

    result = agentic_generator.generate_agentic(_bundle(), "m", ["R-W-1"], repo_root=repo)

    executed = _read_log(logs, "execute.log")
    assert len(executed) == 3, executed
    for entry in executed:
        assert entry["is_error"] is False, entry

    assert field(result, "model_call_error") is None
    assert dict(field(result, "files")) == EXPECTED_FILES
    assert field(result, "mode") == "agentic"
    assert field(result, "cache_hit") is False
    assert field(result, "prompt_version") == "agent-v2"
    assert field(result, "prompt_version") == agentic_generator.AGENT_PROMPT_VERSION
    assert list(field(result, "retry_feedback")) == ["R-W-1"]
    assert field(result, "spec_bundle_hash") == "sha256:h"
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 3
    assert field(result, "transcript_sha256") == _expected_sha()

    writes = _read_log(logs, "write_files.log")
    assert len(writes) == 1, writes
    assert writes[0]["component_id"] == "comp-widget-maker"
    assert writes[0]["files"] == EXPECTED_FILES
    assert writes[0]["repo_root"] is not None
    assert Path(writes[0]["repo_root"]).resolve() == repo.resolve()


def test_missing_module_when_only_notes_written(tmp_path, monkeypatch):
    repo, logs = _setup(tmp_path, monkeypatch, NOTES_SCRIPT)

    result = agentic_generator.generate_agentic(_bundle(), "m", ["R-W-1"], repo_root=repo)

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "missing_module"
    assert _read_log(logs, "write_files.log") == []


def test_hint_mode_returns_script_files_and_writes_nothing(tmp_path, monkeypatch):
    repo, logs = _setup(tmp_path, monkeypatch, FIRST_SCRIPT)

    result = agentic_generator.generate_agentic(
        _bundle(hint_code={"x.py": "1"}), "m", ["R-W-1"], repo_root=repo
    )

    assert field(result, "model_call_error") is None
    files = dict(field(result, "files"))
    assert files == EXPECTED_FILES
    assert files != {"x.py": "1"}
    assert _read_log(logs, "write_files.log") == []