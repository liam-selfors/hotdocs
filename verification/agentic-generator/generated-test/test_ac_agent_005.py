# hotdocs-criterion: sha256:d9d2a5bf128282bf491597e84d7703d2056fb9f4d45992f6ef24680698837822
import hashlib
import json
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _generator_source(write_log, assets_log):
    lines = [
        "import json",
        "import pathlib",
        "from dataclasses import dataclass, field",
        "",
        "WRITE_LOG = " + repr(str(write_log)),
        "ASSETS_LOG = " + repr(str(assets_log)),
        "",
        "",
        "@dataclass",
        "class GenerationResult:",
        "    component_id: str = ''",
        "    spec_bundle_hash: str = ''",
        "    model: str = ''",
        "    prompt_version: str = ''",
        "    cache_hit: bool = False",
        "    files: dict = field(default_factory=dict)",
        "    model_call_error: object = None",
        "    refused: object = None",
        "    retry_feedback: object = None",
        "    mode: str = 'single'",
        "    transcript_sha256: object = None",
        "    turns: int = 1",
        "    tool_calls: int = 0",
        "    isolation: object = None",
        "",
        "",
        "def check_write_allowed(bundle, repo_root=None):",
        "    return None",
        "",
        "",
        "def render_prompt_sections(bundle, retry_feedback=None):",
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]",
        "",
        "",
        "def write_files(component_id, files, repo_root=None):",
        "    with open(WRITE_LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps({'component_id': component_id, 'files': dict(files), 'repo_root': str(repo_root)}) + '\\n')",
        "",
        "",
        "def check_assets(component_id, files, repo_root=None):",
        "    with open(ASSETS_LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps({'component_id': component_id, 'files': dict(files), 'repo_root': str(repo_root)}) + '\\n')",
        "    for content in files.values():",
        "        if 'bad' in content:",
        "            return ('malformed_layout', ['static/app.txt: bad'])",
        "    return (None, [])",
        "",
        "",
        "def check_asset_environment(component_id, repo_root=None):",
        "    if repo_root is not None and (pathlib.Path(repo_root) / 'NO_ENV').exists():",
        "        return ('environment', ['fake needs fakeprog >= 2'])",
        "    return (None, [])",
        "",
    ]
    return "\n".join(lines)


def _loop_source(args_log, steps_log, script_path):
    lines = [
        "import json",
        "from dataclasses import dataclass",
        "",
        "ARGS_LOG = " + repr(str(args_log)),
        "STEPS_LOG = " + repr(str(steps_log)),
        "SCRIPT = " + repr(str(script_path)),
        "TRANSCRIPT = " + repr(TRANSCRIPT),
        "",
        "",
        "@dataclass",
        "class ToolLoopResult:",
        "    text: str",
        "    transcript: list",
        "    turns: int",
        "    tool_calls: int",
        "    stop: str",
        "    model_call_error: object",
        "",
        "    def to_dict(self):",
        "        return {'text': self.text, 'transcript': self.transcript, 'turns': self.turns,",
        "                'tool_calls': self.tool_calls, 'stop': self.stop,",
        "                'model_call_error': self.model_call_error}",
        "",
        "",
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40, max_tool_calls=120,",
        "                  wall_seconds=1800.0, repo_root=None, claude_command='claude'):",
        "    with open(ARGS_LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps({'system': system, 'prompt': prompt, 'model': model, 'tools': tools,",
        "                            'max_turns': max_turns, 'max_tool_calls': max_tool_calls,",
        "                            'wall_seconds': wall_seconds, 'repo_root': repo_root,",
        "                            'claude_command': claude_command}, default=str) + '\\n')",
        "    with open(SCRIPT, encoding='utf-8') as f:",
        "        steps = json.load(f)",
        "    for step in steps:",
        "        text, is_error = execute(step['name'], step['arguments'])",
        "        with open(STEPS_LOG, 'a', encoding='utf-8') as f:",
        "            f.write(json.dumps([step['name'], step['arguments'], text, is_error]) + '\\n')",
        "    return ToolLoopResult('done', [dict(m) for m in TRANSCRIPT], 3, 3, 'end_turn', None)",
        "",
    ]
    return "\n".join(lines)


def _setup(tmp_path, monkeypatch, script):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    script_path = logs / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    paths = {
        "write": logs / "write_files.log",
        "assets": logs / "check_assets.log",
        "args": logs / "loop_args.log",
        "steps": logs / "loop_steps.log",
    }
    (gen_dir / "generator.py").write_text(
        _generator_source(paths["write"], paths["assets"]), encoding="utf-8")
    (loop_dir / "llm_tool_endpoint.py").write_text(
        _loop_source(paths["args"], paths["steps"], script_path), encoding="utf-8")
    return repo_root, paths


def _read_log(path):
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _bundle(hint_code=None):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:h",
        "hint_code": hint_code,
    }


EXPECTED_FILES = {"widget_maker/__init__.py": "A = 1", "widget_maker/core.py": "B = 2"}


def test_cold_mode_collects_work_and_writes_once(tmp_path, monkeypatch):
    repo_root, paths = _setup(tmp_path, monkeypatch, FIRST_SCRIPT)

    result = agentic_generator.generate_agentic(_bundle(), "m", ["R-W-1"], repo_root=repo_root)

    assert dict(field(result, "files")) == EXPECTED_FILES
    assert field(result, "model_call_error") is None
    assert field(result, "mode") == "agentic"
    assert field(result, "cache_hit") is False
    assert field(result, "prompt_version") == "agent-v2"
    assert list(field(result, "retry_feedback")) == ["R-W-1"]
    assert field(result, "spec_bundle_hash") == "sha256:h"
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 3
    expected_sha = "sha256:" + hashlib.sha256(
        json.dumps(TRANSCRIPT, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    assert field(result, "transcript_sha256") == expected_sha

    writes = _read_log(paths["write"])
    assert len(writes) == 1
    assert writes[0]["component_id"] == "comp-widget-maker"
    assert writes[0]["files"] == EXPECTED_FILES


def test_missing_module_when_only_notes_written(tmp_path, monkeypatch):
    repo_root, paths = _setup(tmp_path, monkeypatch, NOTES_SCRIPT)

    result = agentic_generator.generate_agentic(_bundle(), "m", ["R-W-1"], repo_root=repo_root)

    error = field(result, "model_call_error")
    assert error is not None
    assert error["category"] == "missing_module"
    assert _read_log(paths["write"]) == []


def test_hint_mode_returns_candidate_not_hint_code_and_writes_nothing(tmp_path, monkeypatch):
    repo_root, paths = _setup(tmp_path, monkeypatch, FIRST_SCRIPT)

    result = agentic_generator.generate_agentic(
        _bundle(hint_code={"x.py": "1"}), "m", ["R-W-1"], repo_root=repo_root)

    assert dict(field(result, "files")) == EXPECTED_FILES
    assert _read_log(paths["write"]) == []