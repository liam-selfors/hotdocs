# hotdocs-criterion: sha256:2622749b989c34b31d9492ab0bf3f43a97ce2742a87491e130e310e1f58302a5
import json
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SOURCE_TEMPLATE = (
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "from pathlib import Path\n"
    "\n"
    "LOG_DIR = Path(__LOG_DIR__)\n"
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
    "def _log(name, record):\n"
    "    LOG_DIR.mkdir(parents=True, exist_ok=True)\n"
    "    with open(LOG_DIR / name, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(record, sort_keys=True) + '\\n')\n"
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
    "def write_files(component_id, files, repo_root=None):\n"
    "    _log('write_files.log', {'component_id': component_id, 'files': dict(files),\n"
    "         'repo_root': None if repo_root is None else str(repo_root)})\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log('check_assets.log', {'component_id': component_id, 'files': dict(files),\n"
    "         'repo_root': None if repo_root is None else str(repo_root)})\n"
    "    if any('bad' in content for content in files.values()):\n"
    "        return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)


LOOP_SOURCE_TEMPLATE = (
    "import json\n"
    "from dataclasses import dataclass\n"
    "from pathlib import Path\n"
    "\n"
    "LOG_DIR = Path(__LOG_DIR__)\n"
    "SCRIPT = Path(__SCRIPT__)\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class ToolLoopResult:\n"
    "    text: str\n"
    "    transcript: list\n"
    "    turns: int\n"
    "    tool_calls: int\n"
    "    stop: str\n"
    "    model_call_error: object\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'text': self.text, 'transcript': self.transcript, 'turns': self.turns,\n"
    "                'tool_calls': self.tool_calls, 'stop': self.stop,\n"
    "                'model_call_error': self.model_call_error}\n"
    "\n"
    "\n"
    "def _log(name, record):\n"
    "    LOG_DIR.mkdir(parents=True, exist_ok=True)\n"
    "    with open(LOG_DIR / name, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(record, sort_keys=True, default=str) + '\\n')\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    _log('loop_args.log', {'system': system, 'prompt': prompt, 'model': model,\n"
    "         'tools': tools, 'max_turns': max_turns, 'max_tool_calls': max_tool_calls,\n"
    "         'wall_seconds': wall_seconds,\n"
    "         'repo_root': None if repo_root is None else str(repo_root),\n"
    "         'claude_command': claude_command})\n"
    "    steps = json.loads(SCRIPT.read_text(encoding='utf-8'))\n"
    "    count = 0\n"
    "    for step in steps:\n"
    "        name = step['name']\n"
    "        arguments = step['arguments']\n"
    "        count += 1\n"
    "        text, is_error = execute(name, arguments)\n"
    "        _log('loop_results.log', [name, arguments, text, is_error])\n"
    "    transcript = [{'role': 'user', 'content': 'go'},\n"
    "                  {'role': 'assistant', 'content': 'done'}]\n"
    "    return ToolLoopResult(text='done', transcript=transcript, turns=3,\n"
    "                          tool_calls=count, stop='end_turn', model_call_error=None)\n"
)


def _build_fixture(tmp_path, app_content):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    script_path = tmp_path / "script.json"
    script = [
        {"name": "write_file", "arguments": {"path": "work/widget_maker.py", "content": "A = 1"}},
        {"name": "write_file", "arguments": {"path": "work/static/app.txt", "content": app_content}},
        {"name": "finish", "arguments": {"summary": "done"}},
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        GENERATOR_SOURCE_TEMPLATE.replace("__LOG_DIR__", repr(str(log_dir))),
        encoding="utf-8",
    )

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        LOOP_SOURCE_TEMPLATE.replace("__LOG_DIR__", repr(str(log_dir))).replace(
            "__SCRIPT__", repr(str(script_path))
        ),
        encoding="utf-8",
    )
    return repo_root, log_dir


def _read_log(log_dir, name):
    path = log_dir / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def _no_sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))


def _assert_writes_succeeded(log_dir):
    results = _read_log(log_dir, "loop_results.log")
    assert len(results) == 3, results
    for name, _arguments, text, is_error in results:
        assert is_error is False, (name, text)


def test_ac_agent_010_bad_asset_is_malformed_layout(tmp_path, monkeypatch):
    _no_sandbox(monkeypatch, tmp_path)
    repo_root, log_dir = _build_fixture(tmp_path, "bad")

    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)

    _assert_writes_succeeded(log_dir)

    assert field(result, "model_call_error") == {
        "category": "malformed_layout",
        "message": "static/app.txt: bad",
    }
    assert field(result, "files") == {}
    assert field(result, "mode") == "agentic"

    assert _read_log(log_dir, "write_files.log") == []

    calls = _read_log(log_dir, "check_assets.log")
    assert len(calls) == 1, calls
    call = calls[0]
    assert call["component_id"] == "comp-widget-maker"
    assert call["files"] == {"widget_maker.py": "A = 1", "static/app.txt": "bad"}
    assert call["repo_root"] is not None
    assert Path(call["repo_root"]).resolve() == repo_root.resolve()


def test_ac_agent_010_good_asset_is_written(tmp_path, monkeypatch):
    _no_sandbox(monkeypatch, tmp_path)
    repo_root, log_dir = _build_fixture(tmp_path, "ok")

    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)

    _assert_writes_succeeded(log_dir)

    expected = {"widget_maker.py": "A = 1", "static/app.txt": "ok"}
    assert field(result, "files") == expected
    assert field(result, "model_call_error") is None
    assert field(result, "mode") == "agentic"

    writes = _read_log(log_dir, "write_files.log")
    assert len(writes) == 1, writes
    write = writes[0]
    assert write["component_id"] == "comp-widget-maker"
    assert write["files"] == expected
    assert write["repo_root"] is not None
    assert Path(write["repo_root"]).resolve() == repo_root.resolve()