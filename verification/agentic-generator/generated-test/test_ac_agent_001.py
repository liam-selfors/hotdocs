# hotdocs-criterion: sha256:c91c5a80910356f126318f6dc8e5b8aaf0cbda67530a7e5bff8e0b6c3a7739c4
import os
import tempfile
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_generator_stand_in(repo_root, log_path):
    src = (
        "from dataclasses import dataclass, field\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
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
        "    _log('check_write_allowed')\n"
        "    return 'sealed-component'\n"
        "\n"
        "\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    _log('render_prompt_sections')\n"
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        "\n"
        "\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    _log('write_files ' + repr(component_id) + ' ' + repr(sorted(files)))\n"
    )
    d = repo_root / "gen" / "generator"
    d.mkdir(parents=True, exist_ok=True)
    (d / "generator.py").write_text(src, encoding="utf-8")


def _write_loop_stand_in(repo_root, log_path, script_path, results_path):
    src = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        "RESULTS_PATH = " + repr(str(results_path)) + "\n"
        "\n"
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
        "    def to_dict(self):\n"
        "        return {'text': self.text, 'transcript': self.transcript,\n"
        "                'turns': self.turns, 'tool_calls': self.tool_calls,\n"
        "                'stop': self.stop, 'model_call_error': self.model_call_error}\n"
        "\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'called': True, 'model': model,\n"
        "                             'max_turns': max_turns,\n"
        "                             'max_tool_calls': max_tool_calls}) + '\\n')\n"
        "    with open(SCRIPT_PATH, 'r', encoding='utf-8') as fh:\n"
        "        script = json.load(fh)\n"
        "    count = 0\n"
        "    for step in script:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        count += 1\n"
        "        with open(RESULTS_PATH, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(json.dumps([step['name'], step['arguments'], text, is_error]) + '\\n')\n"
        "    return _Result('done', [{'role': 'user', 'content': prompt}], 1, count,\n"
        "                   'end_turn', None)\n"
    )
    d = repo_root / "gen" / "llm-tool-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    (d / "llm_tool_endpoint.py").write_text(src, encoding="utf-8")


def test_ac_agent_001_refusal_skips_sandbox_and_loop(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    gen_log = logs / "generator.log"
    loop_log = logs / "loop.log"
    loop_results = logs / "loop_results.log"
    script_path = logs / "script.json"
    script_path.write_text("[]", encoding="utf-8")

    _write_generator_stand_in(repo_root, gen_log)
    _write_loop_stand_in(repo_root, loop_log, script_path, loop_results)

    # Isolate the temp directory so the "no hotdocs-agent-* directory"
    # check is exact and unaffected by other processes.
    private_tmp = tmp_path / "systmp"
    private_tmp.mkdir()
    monkeypatch.setenv("TMPDIR", str(private_tmp))
    monkeypatch.setattr(tempfile, "tempdir", str(private_tmp))

    # Make OS sandboxes unavailable; irrelevant here but keeps the run inert.
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))

    bundle = {"component_id": "comp-widget", "spec_bundle_hash": "sha256:x", "hint_code": None}

    result = agentic_generator.generate_agentic(bundle, "m", repo_root=repo_root)

    assert field(result, "refused") == "sealed-component"
    assert field(result, "mode") == "agentic"
    assert field(result, "turns") == 0
    assert field(result, "tool_calls") == 0

    # check_write_allowed was consulted
    assert gen_log.is_file()
    assert "check_write_allowed" in gen_log.read_text(encoding="utf-8").splitlines()

    # The loop stand-in was never called
    assert not loop_log.exists() or loop_log.read_text(encoding="utf-8").strip() == ""
    assert not loop_results.exists()

    # No sandbox directory was created
    tmpdir = tempfile.gettempdir()
    leftovers = [name for name in os.listdir(tmpdir) if name.startswith("hotdocs-agent-")]
    assert [n for n in leftovers if os.path.isdir(os.path.join(tmpdir, n))] == []

    # Nothing written into gen/widget either
    assert not (Path(repo_root) / "gen" / "widget").exists()