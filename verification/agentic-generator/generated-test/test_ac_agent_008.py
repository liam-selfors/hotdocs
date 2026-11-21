# hotdocs-criterion: sha256:7b86e7cc286ce0a09b20a6a5839f266f06ba80025455d59a2eebf937eecfca97
import json
from pathlib import Path

import agentic_generator


CANARY = "CANARY-7f3a"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "    with open(WRITE_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'component_id': component_id, 'files': files, 'repo_root': str(repo_root)}) + '\\n')\n"
        "\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    with open(ASSETS_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'component_id': component_id, 'files': files, 'repo_root': str(repo_root)}) + '\\n')\n"
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
        "class _LoopResult:\n"
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
        "def _record(entries):\n"
        "    with open(RESULTS_LOG, 'w', encoding='utf-8') as fh:\n"
        "        json.dump(entries, fh, default=str)\n"
        "\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(ARGS_LOG, 'w', encoding='utf-8') as fh:\n"
        "        json.dump({'system': system, 'prompt': prompt, 'model': model,\n"
        "                   'tools': tools, 'max_turns': max_turns,\n"
        "                   'max_tool_calls': max_tool_calls, 'wall_seconds': wall_seconds,\n"
        "                   'repo_root': str(repo_root), 'claude_command': claude_command},\n"
        "                  fh, default=str)\n"
        "    with open(SCRIPT, encoding='utf-8') as fh:\n"
        "        steps = json.load(fh)\n"
        "    entries = []\n"
        "    _record(entries)\n"
        "\n"
        "    def call(name, arguments):\n"
        "        text, is_error = execute(name, arguments)\n"
        "        entries.append([name, arguments, text, is_error])\n"
        "        _record(entries)\n"
        "        return text, is_error\n"
        "\n"
        "    for step in steps:\n"
        "        text, is_error = call(step['name'], step['arguments'])\n"
        "        if step.get('read_listed') and not is_error:\n"
        "            for line in str(text).split('\\n'):\n"
        "                if line:\n"
        "                    call('read_file', {'path': line})\n"
        "    return _LoopResult(text='done', transcript=[], turns=1,\n"
        "                       tool_calls=len(entries), stop='end_turn',\n"
        "                       model_call_error=None)\n"
    )


def test_ac_agent_008_no_repository_text_reaches_model(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    acceptance = repo_root / "specs" / "components" / "widget" / "acceptance"
    acceptance.mkdir(parents=True)
    ac_file = acceptance / "AC-W-1.md"
    ac_file.write_text("# AC-W-1\n\nCovers: R-W-1\n\n" + CANARY + "\n", encoding="utf-8")

    verification = repo_root / "verification" / "widget"
    verification.mkdir(parents=True)
    (verification / "test_w.py").write_text(
        "# " + CANARY + "\ndef test_w():\n    assert True\n", encoding="utf-8"
    )

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(_generator_source(log_dir), encoding="utf-8")

    script_path = log_dir / "script.json"
    args_log = log_dir / "loop_args.json"
    results_log = log_dir / "loop_results.json"
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        _loop_source(script_path, args_log, results_log), encoding="utf-8"
    )

    bad_paths = [
        "../specs/components/widget/acceptance/AC-W-1.md",
        "bundle/../../verification/widget/test_w.py",
        str(ac_file),
    ]
    steps = [
        {"name": "list_files", "arguments": {"path": "bundle"}, "read_listed": True},
        {"name": "list_files", "arguments": {"path": "work"}, "read_listed": True},
        {"name": "list_files", "arguments": {"path": "scratch"}, "read_listed": True},
    ]
    for p in bad_paths:
        steps.append({"name": "read_file", "arguments": {"path": p}})
    steps.append({"name": "finish", "arguments": {"summary": "done"}})
    script_path.write_text(json.dumps(steps), encoding="utf-8")

    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    agentic_generator.generate_agentic(bundle, "m", repo_root=repo_root)

    assert args_log.is_file(), "loop stand-in was never called"
    assert results_log.is_file(), "loop stand-in recorded no results"
    loop_args = json.loads(args_log.read_text(encoding="utf-8"))
    entries = json.loads(results_log.read_text(encoding="utf-8"))

    # Sanity: the script ran, including the bundle reads and the three bad paths.
    called_paths = [e[1].get("path") for e in entries if isinstance(e[1], dict)]
    for p in bad_paths:
        assert p in called_paths, "script step not executed: " + p
    assert any("SPEC TEXT" in str(e[2]) for e in entries), "bundle files were not listed/read"

    system_text = str(loop_args["system"])
    prompt_text = str(loop_args["prompt"])
    assert CANARY not in system_text
    assert CANARY not in prompt_text

    for name, arguments, text, is_error in entries:
        assert CANARY not in str(text), (
            "repository text leaked via " + repr(name) + " " + repr(arguments)
        )