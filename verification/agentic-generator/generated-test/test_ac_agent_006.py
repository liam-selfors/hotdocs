# hotdocs-criterion: sha256:df715451b9053f3d3352f469751c3828fcceb334482e0bba2da2cb8b0fe7ee0e
import json
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _read_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_generator_stand_in(repo_root, write_log):
    target = repo_root / "gen" / "generator" / "generator.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "WRITE_LOG = " + repr(str(write_log)) + "\n"
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
        "        fh.write(json.dumps({'component_id': component_id, 'files': dict(files),\n"
        "                             'repo_root': None if repo_root is None else str(repo_root)}) + '\\n')\n"
    )
    target.write_text(source, encoding="utf-8")


def _write_loop_stand_in(repo_root, script_path, calls_log, steps_log):
    target = repo_root / "gen" / "llm-tool-endpoint" / "llm_tool_endpoint.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "import dataclasses\n"
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        "CALLS_LOG = " + repr(str(calls_log)) + "\n"
        "STEPS_LOG = " + repr(str(steps_log)) + "\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class ToolLoopResult:\n"
        "    text: str = ''\n"
        "    transcript: list = field(default_factory=list)\n"
        "    turns: int = 0\n"
        "    tool_calls: int = 0\n"
        "    stop: str = 'end_turn'\n"
        "    model_call_error: object = None\n"
        "\n"
        "    def to_dict(self):\n"
        "        return dataclasses.asdict(self)\n"
        "\n"
        "\n"
        "class ToolUseUnsupported(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    names = []\n"
        "    for t in tools:\n"
        "        names.append(t.get('name') if isinstance(t, dict) else getattr(t, 'name', None))\n"
        "    with open(CALLS_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
        "                             'tools': names, 'max_turns': max_turns,\n"
        "                             'max_tool_calls': max_tool_calls,\n"
        "                             'wall_seconds': wall_seconds,\n"
        "                             'repo_root': None if repo_root is None else str(repo_root),\n"
        "                             'claude_command': claude_command}) + '\\n')\n"
        "    with open(SCRIPT_PATH, encoding='utf-8') as fh:\n"
        "        script = json.load(fh)\n"
        "    count = 0\n"
        "    for step in script['steps']:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        count += 1\n"
        "        with open(STEPS_LOG, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(json.dumps([step['name'], step['arguments'], text, bool(is_error)]) + '\\n')\n"
        "    return ToolLoopResult(text='working', transcript=[{'role': 'user', 'content': prompt}],\n"
        "                          turns=1, tool_calls=count, stop=script['stop'],\n"
        "                          model_call_error=script['model_call_error'])\n"
    )
    target.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    "stop, category",
    [
        ("budget_exhausted", "agent_budget_exhausted"),
        ("end_turn", "agent_unfinished"),
        ("error", "rate_limit"),
    ],
)
def test_unfinished_run_writes_nothing_and_reports_stop(tmp_path, monkeypatch, stop, category):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    write_log = logs / "write_files.log"
    calls_log = logs / "loop_calls.log"
    steps_log = logs / "loop_steps.log"
    script_path = logs / "script.json"

    loop_error = {"category": "rate_limit", "message": "m"} if stop == "error" else None
    script = {
        "steps": [
            {
                "name": "write_file",
                "arguments": {"path": "work/widget.py", "content": "def hello():\n    return 1\n"},
            }
        ],
        "stop": stop,
        "model_call_error": loop_error,
    }
    script_path.write_text(json.dumps(script), encoding="utf-8")

    _write_generator_stand_in(repo_root, write_log)
    _write_loop_stand_in(repo_root, script_path, calls_log, steps_log)

    missing = str(tmp_path / "no-such-sandbox-binary")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    result = agentic_generator.generate_agentic(
        bundle, "anthropic:test-model", None, repo_root=repo_root
    )

    # The loop stand-in actually ran and its scripted write step was executed.
    assert len(_read_lines(calls_log)) == 1
    steps = _read_lines(steps_log)
    assert len(steps) == 1
    assert steps[0][0] == "write_file"

    files = field(result, "files")
    assert not files
    assert len(files) == 0

    assert _read_lines(write_log) == []

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == category
    message = field(error, "message")
    assert isinstance(message, str)
    assert message != ""
    if stop == "error":
        assert field(error, "category") == "rate_limit"
        assert message == "m"
    else:
        assert stop in message