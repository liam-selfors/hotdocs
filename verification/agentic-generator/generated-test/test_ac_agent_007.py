# hotdocs-criterion: sha256:f2fbab5311eed0521e69b616526b6bf0383b542945a7fe9a9814103a1f1bb426
import json
import os
import tempfile
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SOURCE_TEMPLATE = (
    "import dataclasses\n"
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "\n"
    "LOG_PATH = __LOG_PATH__\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry, sort_keys=True, default=str) + '\\n')\n"
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
    "    _log(['check_write_allowed'])\n"
    "    return None\n"
    "\n"
    "def render_prompt_sections(bundle, retry_feedback=None):\n"
    "    _log(['render_prompt_sections'])\n"
    "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
    "\n"
    "def write_files(component_id, files, repo_root=None):\n"
    "    _log(['write_files', component_id, dict(files), str(repo_root)])\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log(['check_assets', component_id, dict(files), str(repo_root)])\n"
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


LOOP_SOURCE_TEMPLATE = (
    "import json\n"
    "\n"
    "ARGS_LOG = __ARGS_LOG__\n"
    "STEPS_LOG = __STEPS_LOG__\n"
    "SCRIPT_PATH = __SCRIPT_PATH__\n"
    "\n"
    "class _Result:\n"
    "    def __init__(self, text, transcript, turns, tool_calls, stop, model_call_error):\n"
    "        self.text = text\n"
    "        self.transcript = transcript\n"
    "        self.turns = turns\n"
    "        self.tool_calls = tool_calls\n"
    "        self.stop = stop\n"
    "        self.model_call_error = model_call_error\n"
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
    "                             'claude_command': claude_command},\n"
    "                            sort_keys=True, default=str) + '\\n')\n"
    "    with open(SCRIPT_PATH, encoding='utf-8') as fh:\n"
    "        script = json.load(fh)\n"
    "    calls = 0\n"
    "    for step in script:\n"
    "        if 'raise' in step:\n"
    "            raise RuntimeError(step['raise'])\n"
    "        calls += 1\n"
    "        text, is_error = execute(step['name'], step['arguments'])\n"
    "        with open(STEPS_LOG, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps([step['name'], step['arguments'], text, is_error]) + '\\n')\n"
    "    return _Result('done', [], 1, calls, 'end_turn', None)\n"
)


def _snapshot():
    root = tempfile.gettempdir()
    dirs = set()
    sb_files = set()
    for name in os.listdir(root):
        if not name.startswith("hotdocs-agent-"):
            continue
        full = os.path.join(root, name)
        if os.path.isdir(full):
            dirs.add(name)
        if name.endswith(".sb") and os.path.isfile(full):
            sb_files.add(name)
    return dirs, sb_files


def test_ac_agent_007_sandbox_removed_when_loop_raises(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    gen_log = logs / "generator.log"
    args_log = logs / "loop_args.log"
    steps_log = logs / "loop_steps.log"
    script_path = logs / "script.json"

    script = [
        {"name": "write_file", "arguments": {"path": "work/a.py", "content": "X = 1\n"}},
        {"raise": "boom"},
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        GENERATOR_SOURCE_TEMPLATE.replace("__LOG_PATH__", repr(str(gen_log))),
        encoding="utf-8",
    )

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        LOOP_SOURCE_TEMPLATE.replace("__ARGS_LOG__", repr(str(args_log)))
        .replace("__STEPS_LOG__", repr(str(steps_log)))
        .replace("__SCRIPT_PATH__", repr(str(script_path))),
        encoding="utf-8",
    )

    missing = str(tmp_path / "does-not-exist" / "nope")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)

    bundle = {
        "component_id": "comp-a",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    before_dirs, before_sb = _snapshot()

    with pytest.raises(RuntimeError, match="boom"):
        agentic_generator.generate_agentic(
            bundle, "anthropic:claude-sonnet-5", None, repo_root=repo_root
        )

    after_dirs, after_sb = _snapshot()

    # The loop stand-in actually ran and its write_file call reached the sandbox.
    assert args_log.exists(), "loop stand-in was never called"
    assert steps_log.exists(), "loop stand-in never executed a tool call"
    steps = [json.loads(line) for line in steps_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(steps) == 1
    assert steps[0][0] == "write_file"
    assert steps[0][1] == {"path": "work/a.py", "content": "X = 1\n"}

    new_dirs = after_dirs - before_dirs
    new_sb = after_sb - before_sb
    assert new_dirs == set(), "sandbox directories left behind: " + repr(sorted(new_dirs))
    assert new_sb == set(), "sandbox profile files left behind: " + repr(sorted(new_sb))