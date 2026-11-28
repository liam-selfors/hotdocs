# hotdocs-criterion: sha256:a3f025b3378aa3f26590b7bfb146ef0c69290e8eaec80e9ab95b8a9259d4786d
import json
import os
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SOURCE = (
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "\n"
    "LOG_DIR = __LOG_DIR__\n"
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
    "    import os\n"
    "    with open(os.path.join(LOG_DIR, name), 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(record) + '\\n')\n"
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
    "    _log('write_files.log', [component_id, dict(files), None if repo_root is None else str(repo_root)])\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log('check_assets.log', [component_id, dict(files), None if repo_root is None else str(repo_root)])\n"
    "    for content in files.values():\n"
    "        if 'bad' in content:\n"
    "            return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    import os\n"
    "    if repo_root is not None and os.path.exists(os.path.join(str(repo_root), 'NO_ENV')):\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)


LOOP_SOURCE = (
    "import json\n"
    "import os\n"
    "\n"
    "LOG_DIR = __LOG_DIR__\n"
    "SCRIPT = __SCRIPT__\n"
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
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40, max_tool_calls=120,\n"
    "                  wall_seconds=1800.0, repo_root=None, claude_command='claude'):\n"
    "    with open(os.path.join(LOG_DIR, 'loop_args.log'), 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'model': model, 'tools': [t['name'] for t in tools],\n"
    "                             'max_turns': max_turns, 'max_tool_calls': max_tool_calls}) + '\\n')\n"
    "    with open(SCRIPT, encoding='utf-8') as fh:\n"
    "        steps = json.load(fh)\n"
    "    transcript = []\n"
    "    count = 0\n"
    "    for name, arguments in steps:\n"
    "        text, is_error = execute(name, arguments)\n"
    "        count += 1\n"
    "        transcript.append({'role': 'tool', 'name': name, 'text': text, 'is_error': bool(is_error)})\n"
    "        with open(os.path.join(LOG_DIR, 'steps.log'), 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps([name, arguments, text, bool(is_error)]) + '\\n')\n"
    "    return ToolLoopResult('done', transcript, count + 1, count, 'end_turn', None)\n"
)


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_repo(root, app_content):
    root.mkdir(parents=True, exist_ok=True)
    logs = root / "logs"
    logs.mkdir()
    script = root / "script.json"
    script.write_text(
        json.dumps(
            [
                ["write_file", {"path": "work/widget_maker.py", "content": "A = 1"}],
                ["write_file", {"path": "work/static/app.txt", "content": app_content}],
                ["finish", {"summary": "done"}],
            ]
        ),
        encoding="utf-8",
    )
    gen_dir = root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        GENERATOR_SOURCE.replace("__LOG_DIR__", repr(str(logs))), encoding="utf-8"
    )
    loop_dir = root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        LOOP_SOURCE.replace("__LOG_DIR__", repr(str(logs))).replace("__SCRIPT__", repr(str(script))),
        encoding="utf-8",
    )
    return logs


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def _same_path(a, b):
    return os.path.realpath(str(a)) == os.path.realpath(str(b))


def test_ac_agent_010_bad_asset_is_rejected_and_not_written(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))
    repo = tmp_path / "repo"
    logs = _make_repo(repo, "bad")

    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo)

    steps = _read_log(logs / "steps.log")
    assert [s[0] for s in steps] == ["write_file", "write_file", "finish"], steps
    assert all(not s[3] for s in steps), steps

    assert field(result, "model_call_error") == {
        "category": "malformed_layout",
        "message": "static/app.txt: bad",
    }
    assert dict(field(result, "files")) == {}
    assert field(result, "mode") == "agentic"

    assert _read_log(logs / "write_files.log") == []

    calls = _read_log(logs / "check_assets.log")
    assert len(calls) == 1, calls
    component_id, files, repo_root = calls[0]
    assert component_id == "comp-widget-maker"
    assert files == {"widget_maker.py": "A = 1", "static/app.txt": "bad"}
    assert repo_root is not None and _same_path(repo_root, repo)


def test_ac_agent_010_good_asset_is_returned_and_written(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))
    repo = tmp_path / "repo"
    logs = _make_repo(repo, "ok")

    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo)

    steps = _read_log(logs / "steps.log")
    assert [s[0] for s in steps] == ["write_file", "write_file", "finish"], steps
    assert all(not s[3] for s in steps), steps

    expected = {"widget_maker.py": "A = 1", "static/app.txt": "ok"}
    assert field(result, "model_call_error") is None
    assert dict(field(result, "files")) == expected
    assert field(result, "mode") == "agentic"

    writes = _read_log(logs / "write_files.log")
    assert len(writes) == 1, writes
    component_id, files, repo_root = writes[0]
    assert component_id == "comp-widget-maker"
    assert files == expected
    assert repo_root is not None and _same_path(repo_root, repo)