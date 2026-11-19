# hotdocs-criterion: sha256:9fc805bbbc76c05c3e44b91aa94d7c4e893c825a1a4dda74550e0c13af655025
import json
from pathlib import Path

import agentic_generator


COMPONENT_ID = "comp-widget-maker"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generator_source(log_dir):
    return (
        "import dataclasses\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_DIR = " + repr(str(log_dir)) + "\n"
        "\n"
        "\n"
        "def _log(name, record):\n"
        "    with open(str(Path(LOG_DIR) / name), 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record, sort_keys=True, default=str) + '\\n')\n"
        "\n"
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
        "    _log('write_files.jsonl', {'component_id': component_id, 'files': dict(files),\n"
        "         'repo_root': None if repo_root is None else str(repo_root)})\n"
        "\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    _log('check_assets.jsonl', {'component_id': component_id, 'files': dict(files),\n"
        "         'repo_root': None if repo_root is None else str(repo_root)})\n"
        "    for content in files.values():\n"
        "        if 'bad' in content:\n"
        "            return ('malformed_layout', ['static/app.txt: bad'])\n"
        "    return (None, [])\n"
        "\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():\n"
        "        return ('environment', ['fake needs fakeprog >= 2'])\n"
        "    return (None, [])\n"
    )


def _loop_source(log_dir, script_path):
    return (
        "import dataclasses\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_DIR = " + repr(str(log_dir)) + "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "\n"
        "\n"
        "def _log(name, record):\n"
        "    with open(str(Path(LOG_DIR) / name), 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record, sort_keys=True, default=str) + '\\n')\n"
        "\n"
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
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    _log('loop_args.jsonl', {'system': system, 'prompt': prompt, 'model': model,\n"
        "         'tools': tools, 'max_turns': max_turns, 'max_tool_calls': max_tool_calls,\n"
        "         'wall_seconds': wall_seconds,\n"
        "         'repo_root': None if repo_root is None else str(repo_root),\n"
        "         'claude_command': claude_command})\n"
        "    with open(SCRIPT, 'r', encoding='utf-8') as fh:\n"
        "        script = json.load(fh)\n"
        "    transcript = [{'role': 'user', 'content': prompt}]\n"
        "    count = 0\n"
        "    for step in script:\n"
        "        name = step['name']\n"
        "        arguments = step['arguments']\n"
        "        count += 1\n"
        "        text, is_error = execute(name, arguments)\n"
        "        _log('loop_results.jsonl', {'name': name, 'arguments': arguments,\n"
        "             'text': text, 'is_error': is_error})\n"
        "        transcript.append({'role': 'assistant', 'tool': name, 'arguments': arguments})\n"
        "        transcript.append({'role': 'user', 'result': text, 'is_error': is_error})\n"
        "    return ToolLoopResult(text='done', transcript=transcript, turns=count + 1,\n"
        "                          tool_calls=count, stop='end_turn', model_call_error=None)\n"
    )


def _read_log(path):
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _setup(tmp_path, app_content):
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
    (gen_dir / "generator.py").write_text(_generator_source(log_dir), encoding="utf-8")

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        _loop_source(log_dir, script_path), encoding="utf-8"
    )
    return repo_root, log_dir


def _run(tmp_path, monkeypatch, app_content):
    repo_root, log_dir = _setup(tmp_path, app_content)
    missing = str(tmp_path / "no-such-sandbox-program")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)
    bundle = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }
    result = agentic_generator.generate_agentic(bundle, "m", repo_root=repo_root)
    return result, repo_root, log_dir


def _assert_tool_calls_succeeded(log_dir):
    results = _read_log(log_dir / "loop_results.jsonl")
    assert len(results) == 3, results
    for entry in results:
        assert entry["is_error"] is False, entry


def test_check_assets_failure_gives_its_category_and_writes_nothing(tmp_path, monkeypatch):
    result, repo_root, log_dir = _run(tmp_path, monkeypatch, "bad")
    _assert_tool_calls_succeeded(log_dir)

    assert field(result, "model_call_error") == {
        "category": "malformed_layout",
        "message": "static/app.txt: bad",
    }
    assert field(result, "files") == {}
    assert field(result, "mode") == "agentic"

    assert _read_log(log_dir / "write_files.jsonl") == []

    calls = _read_log(log_dir / "check_assets.jsonl")
    assert len(calls) == 1, calls
    call = calls[0]
    assert call["component_id"] == COMPONENT_ID
    assert call["files"] == {"widget_maker.py": "A = 1", "static/app.txt": "bad"}
    assert call["repo_root"] is not None
    assert Path(call["repo_root"]).resolve() == repo_root.resolve()


def test_check_assets_pass_writes_candidate_once(tmp_path, monkeypatch):
    result, repo_root, log_dir = _run(tmp_path, monkeypatch, "ok")
    _assert_tool_calls_succeeded(log_dir)

    expected = {"widget_maker.py": "A = 1", "static/app.txt": "ok"}
    assert field(result, "files") == expected
    assert field(result, "model_call_error") is None
    assert field(result, "mode") == "agentic"

    writes = _read_log(log_dir / "write_files.jsonl")
    assert len(writes) == 1, writes
    assert writes[0]["component_id"] == COMPONENT_ID
    assert writes[0]["files"] == expected
    assert writes[0]["repo_root"] is not None
    assert Path(writes[0]["repo_root"]).resolve() == repo_root.resolve()

    calls = _read_log(log_dir / "check_assets.jsonl")
    assert len(calls) == 1, calls
    assert calls[0]["component_id"] == COMPONENT_ID
    assert calls[0]["files"] == expected