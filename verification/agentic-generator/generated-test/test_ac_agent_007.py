# hotdocs-criterion: sha256:f2fbab5311eed0521e69b616526b6bf0383b542945a7fe9a9814103a1f1bb426
import json
import os
import tempfile
from pathlib import Path

import pytest

import agentic_generator


GENERATOR_SOURCE = (
    "import dataclasses\n"
    "import json\n"
    "\n"
    "LOG = " + "{LOG}" + "\n"
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
    "    with open(LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps({'event': 'write_files', 'component_id': component_id,\n"
    "                            'files': files, 'repo_root': str(repo_root)}) + '\\n')\n"
)


LOOP_SOURCE = (
    "import dataclasses\n"
    "import json\n"
    "\n"
    "LOG = " + "{LOG}" + "\n"
    "SCRIPT = " + "{SCRIPT}" + "\n"
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
    "    with open(LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps({'event': 'args', 'model': model,\n"
    "                            'tools': [t.get('name') for t in tools],\n"
    "                            'max_turns': max_turns,\n"
    "                            'max_tool_calls': max_tool_calls}) + '\\n')\n"
    "    with open(SCRIPT, encoding='utf-8') as f:\n"
    "        steps = json.load(f)\n"
    "    for step in steps:\n"
    "        text, is_error = execute(step['name'], step['arguments'])\n"
    "        with open(LOG, 'a', encoding='utf-8') as f:\n"
    "            f.write(json.dumps({'event': 'call', 'name': step['name'],\n"
    "                                'arguments': step['arguments'],\n"
    "                                'text': text, 'is_error': bool(is_error)}) + '\\n')\n"
    "    raise RuntimeError('boom')\n"
)


def _fill(template, **values):
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", repr(value))
    return out


def _agent_entries():
    tmp = tempfile.gettempdir()
    dirs = set()
    sb_files = set()
    for name in os.listdir(tmp):
        if not name.startswith("hotdocs-agent-"):
            continue
        full = os.path.join(tmp, name)
        if os.path.isdir(full):
            dirs.add(name)
        elif name.endswith(".sb"):
            sb_files.add(name)
    return dirs, sb_files


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_sandbox_removed_when_tool_loop_raises(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "log.jsonl"
    script_path = tmp_path / "script.json"

    script = [
        {"name": "write_file", "arguments": {"path": "work/a.py", "content": "x = 1\n"}},
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        _fill(GENERATOR_SOURCE, LOG=str(log_path)), encoding="utf-8"
    )

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        _fill(LOOP_SOURCE, LOG=str(log_path), SCRIPT=str(script_path)), encoding="utf-8"
    )

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    before_dirs, before_sb = _agent_entries()

    with pytest.raises(RuntimeError, match="boom"):
        agentic_generator.generate_agentic(
            bundle,
            "claude-cli:test-model",
            None,
            repo_root=repo_root,
        )

    after_dirs, after_sb = _agent_entries()

    new_dirs = after_dirs - before_dirs
    new_sb = after_sb - before_sb
    assert new_dirs == set(), "sandbox directories left behind: " + repr(sorted(new_dirs))
    assert new_sb == set(), "sandbox profile files left behind: " + repr(sorted(new_sb))

    # Confirm the loop stand-in actually ran and the write happened inside a sandbox.
    entries = _read_log(log_path)
    assert any(e.get("event") == "args" for e in entries)
    calls = [e for e in entries if e.get("event") == "call"]
    assert len(calls) == 1
    assert calls[0]["name"] == "write_file"
    assert calls[0]["is_error"] is False
    assert calls[0]["text"] == "wrote work/a.py"