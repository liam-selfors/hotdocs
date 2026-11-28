# hotdocs-criterion: sha256:544a9b2f93f0160f8ecea8ab22556615db8bb36dae7f4feecd4c80e9bc3d7cc5
import json
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SOURCE_TEMPLATE_HEAD = (
    "import json\n"
    "import os\n"
    "from dataclasses import dataclass, field\n"
    "\n"
)

GENERATOR_SOURCE_BODY = (
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
    "def _log(name, payload):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps([name, payload], default=str) + '\\n')\n"
    "\n"
    "\n"
    "def check_write_allowed(bundle, repo_root=None):\n"
    "    _log('check_write_allowed', [str(repo_root)])\n"
    "    return None\n"
    "\n"
    "\n"
    "def render_prompt_sections(bundle, retry_feedback=None):\n"
    "    _log('render_prompt_sections', [retry_feedback])\n"
    "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
    "\n"
    "\n"
    "def write_files(component_id, files, repo_root=None):\n"
    "    _log('write_files', [component_id, files, str(repo_root)])\n"
    "    return None\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log('check_assets', [component_id, files, str(repo_root)])\n"
    "    for content in files.values():\n"
    "        if 'bad' in content:\n"
    "            return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    _log('check_asset_environment', [component_id, str(repo_root)])\n"
    "    if repo_root is not None and os.path.exists(os.path.join(str(repo_root), 'NO_ENV')):\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)

LOOP_SOURCE_HEAD = (
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "\n"
)

LOOP_SOURCE_BODY = (
    "\n"
    "@dataclass\n"
    "class ToolLoopResult:\n"
    "    text: str = ''\n"
    "    transcript: list = field(default_factory=list)\n"
    "    turns: int = 1\n"
    "    tool_calls: int = 0\n"
    "    stop: str = 'end_turn'\n"
    "    model_call_error: object = None\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'text': self.text, 'transcript': self.transcript,\n"
    "                'turns': self.turns, 'tool_calls': self.tool_calls,\n"
    "                'stop': self.stop, 'model_call_error': self.model_call_error}\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    with open(ARGS_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
    "                             'tools': [t.get('name') for t in tools],\n"
    "                             'max_turns': max_turns, 'max_tool_calls': max_tool_calls,\n"
    "                             'wall_seconds': wall_seconds, 'repo_root': str(repo_root),\n"
    "                             'claude_command': claude_command}) + '\\n')\n"
    "    with open(SCRIPT_PATH, 'r', encoding='utf-8') as fh:\n"
    "        steps = json.load(fh)\n"
    "    count = 0\n"
    "    for step in steps:\n"
    "        text, is_error = execute(step['name'], step['arguments'])\n"
    "        count += 1\n"
    "        with open(CALLS_PATH, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps([step['name'], step['arguments'], text, is_error]) + '\\n')\n"
    "    return ToolLoopResult(text='done', transcript=[], turns=1, tool_calls=count,\n"
    "                          stop='end_turn', model_call_error=None)\n"
)


def _setup(repo_root, script):
    logs = repo_root / "_logs"
    logs.mkdir(parents=True, exist_ok=True)
    script_path = logs / "script.json"
    calls_path = logs / "calls.jsonl"
    args_path = logs / "loop_args.jsonl"
    gen_log = logs / "generator.jsonl"
    script_path.write_text(json.dumps(script), encoding="utf-8")

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "generator.py").write_text(
        GENERATOR_SOURCE_TEMPLATE_HEAD
        + "LOG_PATH = " + repr(str(gen_log)) + "\n"
        + GENERATOR_SOURCE_BODY,
        encoding="utf-8",
    )

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True, exist_ok=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        LOOP_SOURCE_HEAD
        + "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        + "CALLS_PATH = " + repr(str(calls_path)) + "\n"
        + "ARGS_PATH = " + repr(str(args_path)) + "\n"
        + LOOP_SOURCE_BODY,
        encoding="utf-8",
    )
    return calls_path


def _read_calls(calls_path):
    lines = Path(calls_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _bundle():
    return {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def _w(path, content):
    return {"name": "write_file", "arguments": {"path": path, "content": content}}


def test_ac_agent_009_tool_results_in_order(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    script = [
        _w("work/pkg/a.py", "A = 1"),
        _w("work/pkg/b.py", "B = 2"),
        {"name": "list_files", "arguments": {"path": "work"}},
        {"name": "read_file", "arguments": {"path": "work/pkg"}},
        _w("scratch/long.txt", "y" * 9000),
        {"name": "read_file", "arguments": {"path": "scratch/long.txt"}},
    ]
    for i in range(1, 198):
        script.append(_w("scratch/f" + str(i).zfill(3) + ".py", "x = 0"))
    script += [
        _w("scratch/f198.py", "x = 0"),
        _w("work/pkg/a.py", "A = 2"),
        {"name": "read_file", "arguments": {"path": "work/pkg/a.py"}},
        {"name": "delete_file", "arguments": {"path": "work/pkg/b.py"}},
        _w("scratch/f198.py", "x = 0"),
        {"name": "finish", "arguments": {"summary": "done"}},
    ]

    calls_path = _setup(repo_root, script)

    agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)

    expected = [
        ("wrote work/pkg/a.py", False),
        ("wrote work/pkg/b.py", False),
        ("work/pkg/a.py\nwork/pkg/b.py", False),
        ("not found: work/pkg", True),
        ("wrote scratch/long.txt", False),
        ("y" * 8192 + "\n[truncated]", False),
    ]
    for i in range(1, 198):
        expected.append(("wrote scratch/f" + str(i).zfill(3) + ".py", False))
    expected += [
        ("too many files: limit 200", True),
        ("wrote work/pkg/a.py", False),
        ("A = 2", False),
        ("deleted work/pkg/b.py", False),
        ("wrote scratch/f198.py", False),
        ("finished", False),
    ]

    calls = _read_calls(calls_path)
    got = [(c[2], c[3]) for c in calls]
    assert len(got) == len(expected)
    for index, (g, e) in enumerate(zip(got, expected)):
        assert g[0] == e[0], (index, g, e)
        assert isinstance(g[1], bool), (index, g)
        assert g[1] is e[1], (index, g, e)


def test_ac_agent_009_check_import_unisolated(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")

    script = [
        _w("work/widget.py", "A = 1"),
        {"name": "check_import", "arguments": {}},
        {"name": "finish", "arguments": {"summary": "done"}},
    ]
    calls_path = _setup(repo_root, script)

    result = agentic_generator.generate_agentic(
        _bundle(), "m", repo_root=repo_root, allow_unisolated_exec=True
    )

    calls = _read_calls(calls_path)
    check = [c for c in calls if c[0] == "check_import"]
    assert len(check) == 1
    assert check[0][2] == "0\n"
    assert check[0][3] is False
    assert field(result, "isolation") == "unisolated"