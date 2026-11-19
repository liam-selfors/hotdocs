# hotdocs-criterion: sha256:2b23aa14481ac0b0cfa3e3874d81695235dfa0abacf8d6ec52f42a34c3689d48
import json
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_generator_stand_in(repo_root, write_log):
    d = repo_root / "gen" / "generator"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "import json\n"
        "\n"
        "WRITE_LOG = " + repr(str(write_log)) + "\n"
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
        "    with open(WRITE_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'component_id': component_id, 'files': files,"
        " 'repo_root': None if repo_root is None else str(repo_root)}) + '\\n')\n"
    )
    (d / "generator.py").write_text(src, encoding="utf-8")


def _write_loop_stand_in(repo_root, args_log, results_log, script_path):
    d = repo_root / "gen" / "llm-tool-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "\n"
        "ARGS_LOG = " + repr(str(args_log)) + "\n"
        "RESULTS_LOG = " + repr(str(results_log)) + "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
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
        "        return {'text': self.text, 'transcript': self.transcript, 'turns': self.turns,"
        " 'tool_calls': self.tool_calls, 'stop': self.stop,"
        " 'model_call_error': self.model_call_error}\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,"
        " max_tool_calls=120, wall_seconds=1800.0, repo_root=None, claude_command='claude'):\n"
        "    with open(ARGS_LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({\n"
        "            'system': system,\n"
        "            'prompt': prompt,\n"
        "            'model': model,\n"
        "            'tool_names': [t['name'] for t in tools],\n"
        "            'max_turns': max_turns,\n"
        "            'max_tool_calls': max_tool_calls,\n"
        "            'wall_seconds': wall_seconds,\n"
        "            'repo_root': None if repo_root is None else str(repo_root),\n"
        "            'claude_command': claude_command,\n"
        "        }) + '\\n')\n"
        "    with open(SCRIPT, encoding='utf-8') as f:\n"
        "        script = json.load(f)\n"
        "    count = 0\n"
        "    transcript = []\n"
        "    for step in script:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        count += 1\n"
        "        transcript.append({'role': 'user', 'content': text})\n"
        "        with open(RESULTS_LOG, 'a', encoding='utf-8') as f:\n"
        "            f.write(json.dumps([step['name'], step['arguments'], text, is_error]) + '\\n')\n"
        "    return ToolLoopResult('Done.', transcript, 1, count, 'end_turn', None)\n"
    )
    (d / "llm_tool_endpoint.py").write_text(src, encoding="utf-8")


def test_ac_agent_002(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    args_log = logs / "args.jsonl"
    results_log = logs / "results.jsonl"
    write_log = logs / "write.jsonl"
    script_path = logs / "script.json"

    script = [
        {"name": "list_files", "arguments": {"path": "bundle"}},
        {"name": "read_file", "arguments": {"path": "bundle/01-spec.md"}},
        {"name": "read_file", "arguments": {"path": "bundle/02-component-interface.md"}},
        {"name": "write_file", "arguments": {"path": "bundle/x.md", "content": "x"}},
        {"name": "list_files", "arguments": {"path": "work"}},
        {"name": "finish", "arguments": {"summary": "done"}},
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")

    _write_generator_stand_in(repo_root, write_log)
    _write_loop_stand_in(repo_root, args_log, results_log, script_path)

    bundle = {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    agentic_generator.generate_agentic(bundle, "m", repo_root=repo_root, max_turns=7)

    # Recorded results, in order.
    assert results_log.is_file(), "loop stand-in never ran execute"
    lines = [l for l in results_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    records = [json.loads(l) for l in lines]
    assert len(records) == 6
    texts = [r[2] for r in records]
    errors = [r[3] for r in records]

    assert texts[0] == "bundle/01-spec.md\nbundle/02-component-interface.md"
    assert not errors[0]
    assert texts[1] == "SPEC TEXT"
    assert not errors[1]
    assert texts[2] == "IFACE TEXT"
    assert not errors[2]
    assert texts[3].startswith("path not allowed:")
    assert errors[3]
    assert texts[4] == ""
    assert not errors[4]
    assert texts[5] == "finished"
    assert not errors[5]

    # Loop arguments.
    assert args_log.is_file(), "run_tool_loop never called"
    arg_lines = [l for l in args_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(arg_lines) == 1, "run_tool_loop must be called exactly once"
    args = json.loads(arg_lines[0])

    assert args["tool_names"] == [
        "list_files",
        "read_file",
        "write_file",
        "delete_file",
        "check_import",
        "run_scratch_tests",
        "finish",
    ]
    assert args["max_turns"] == 7
    assert args["model"] == "m"

    system = args["system"]
    for needle in ("work/", "scratch/", "widget_maker.py", "finish"):
        assert needle in system, "system text lacks " + repr(needle)

    prompt = args["prompt"]
    assert "bundle/01-spec.md" in prompt
    assert "bundle/02-component-interface.md" in prompt
    assert prompt.index("bundle/01-spec.md") < prompt.index("bundle/02-component-interface.md")