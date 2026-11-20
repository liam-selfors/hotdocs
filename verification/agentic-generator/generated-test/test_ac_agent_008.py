# hotdocs-criterion: sha256:253c8943b2d00043f8cbedf9eba518e801b07a95460228ccab0cd4a9f9e5c7f4
import json
from pathlib import Path

import agentic_generator

CANARY = "CANARY-7f3a"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _generator_source(log_dir):
    write_log = str(log_dir / "write_files.log")
    assets_log = str(log_dir / "check_assets.log")
    return (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "from pathlib import Path\n"
        "\n"
        "WRITE_LOG = " + repr(write_log) + "\n"
        "ASSETS_LOG = " + repr(assets_log) + "\n"
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
        "def check_write_allowed(bundle, repo_root=None):\n"
        "    return None\n"
        "\n"
        "\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        "\n"
        "\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    with open(WRITE_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps([component_id, files, None if repo_root is None else str(repo_root)]) + '\\n')\n"
        "\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    with open(ASSETS_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps([component_id, files, None if repo_root is None else str(repo_root)]) + '\\n')\n"
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


def _loop_source(script_path, args_log, results_log):
    return (
        "import json\n"
        "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "ARGS_LOG = " + repr(str(args_log)) + "\n"
        "RESULTS_LOG = " + repr(str(results_log)) + "\n"
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
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(ARGS_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
        "                            'tools': tools, 'max_turns': max_turns,\n"
        "                            'max_tool_calls': max_tool_calls,\n"
        "                            'wall_seconds': wall_seconds,\n"
        "                            'repo_root': None if repo_root is None else str(repo_root),\n"
        "                            'claude_command': claude_command}, default=str) + '\\n')\n"
        "    with open(SCRIPT, encoding='utf-8') as f:\n"
        "        steps = json.load(f)\n"
        "    listed = []\n"
        "    count = [0]\n"
        "\n"
        "    def call(name, arguments):\n"
        "        count[0] += 1\n"
        "        text, is_error = execute(name, arguments)\n"
        "        with open(RESULTS_LOG, 'a', encoding='utf-8') as f:\n"
        "            f.write(json.dumps([name, arguments, text, is_error], default=str) + '\\n')\n"
        "        return text, is_error\n"
        "\n"
        "    for step in steps:\n"
        "        if step['name'] == 'read_listed':\n"
        "            for p in list(listed):\n"
        "                call('read_file', {'path': p})\n"
        "            continue\n"
        "        text, is_error = call(step['name'], step['arguments'])\n"
        "        if step['name'] == 'list_files' and not is_error and isinstance(text, str) and text:\n"
        "            listed.extend(line for line in text.split('\\n') if line)\n"
        "    return ToolLoopResult('done', [], 1, count[0], 'end_turn', None)\n"
    )


def test_ac_agent_008_no_repository_text_leaks(tmp_path, monkeypatch):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    logs = (tmp_path / "logs").resolve()
    logs.mkdir()

    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))

    acceptance_file = repo_root / "specs" / "components" / "widget" / "acceptance" / "AC-W-1.md"
    _write(acceptance_file, "# AC-W-1\n\nCovers: R-W-1\n\nSecret text " + CANARY + "\n")
    _write(repo_root / "verification" / "widget" / "test_w.py",
           "# " + CANARY + "\ndef test_w():\n    assert '" + CANARY + "'\n")

    _write(repo_root / "gen" / "generator" / "generator.py", _generator_source(logs))

    script_path = logs / "script.json"
    args_log = logs / "loop_args.log"
    results_log = logs / "loop_results.log"
    script = [
        {"name": "list_files", "arguments": {"path": "bundle"}},
        {"name": "list_files", "arguments": {"path": "work"}},
        {"name": "list_files", "arguments": {"path": "scratch"}},
        {"name": "read_listed", "arguments": {}},
        {"name": "read_file", "arguments": {"path": "../specs/components/widget/acceptance/AC-W-1.md"}},
        {"name": "read_file", "arguments": {"path": "bundle/../../verification/widget/test_w.py"}},
        {"name": "read_file", "arguments": {"path": str(acceptance_file)}},
        {"name": "finish", "arguments": {"summary": "done"}},
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")
    _write(repo_root / "gen" / "llm-tool-endpoint" / "llm_tool_endpoint.py",
           _loop_source(script_path, args_log, results_log))

    bundle = {"component_id": "comp-widget", "spec_bundle_hash": "sha256:" + "0" * 64, "hint_code": None}

    agentic_generator.generate_agentic(bundle, "m", repo_root=repo_root)

    assert args_log.is_file(), "loop stand-in was never called"
    arg_records = [json.loads(line) for line in args_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert arg_records
    for rec in arg_records:
        assert CANARY not in str(rec["system"])
        assert CANARY not in str(rec["prompt"])

    assert results_log.is_file(), "no tool results were recorded"
    result_records = [json.loads(line) for line in results_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    names = [r[0] for r in result_records]
    assert names.count("list_files") == 3
    assert "finish" in names
    assert names.count("read_file") >= 3

    for name, arguments, text, is_error in result_records:
        assert CANARY not in str(text), (name, arguments, text)