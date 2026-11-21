# hotdocs-criterion: sha256:4d233e81ed751ac3eedf099cc1e5b9ac7f00560cc34c1c7bbc6bd0070ff9701f
import json
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generator_source(gen_log, write_log, repo_root):
    lines = [
        "import json",
        "import os",
        "from dataclasses import dataclass, field",
        "",
        "GEN_LOG = " + repr(str(gen_log)),
        "WRITE_LOG = " + repr(str(write_log)),
        "",
        "",
        "def _log(path, kind, payload):",
        "    with open(path, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps([kind, payload], default=str) + '\\n')",
        "",
        "",
        "@dataclass",
        "class GenerationResult:",
        "    component_id: str = ''",
        "    spec_bundle_hash: str = ''",
        "    model: str = ''",
        "    prompt_version: str = ''",
        "    cache_hit: bool = False",
        "    files: dict = field(default_factory=dict)",
        "    model_call_error: object = None",
        "    refused: object = None",
        "    retry_feedback: object = None",
        "    mode: str = 'single'",
        "    transcript_sha256: object = None",
        "    turns: int = 1",
        "    tool_calls: int = 0",
        "    isolation: object = None",
        "",
        "",
        "def check_write_allowed(bundle, repo_root=None):",
        "    _log(GEN_LOG, 'check_write_allowed', {'repo_root': repo_root})",
        "    return None",
        "",
        "",
        "def render_prompt_sections(bundle, retry_feedback=None):",
        "    _log(GEN_LOG, 'render_prompt_sections', {'retry_feedback': retry_feedback})",
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]",
        "",
        "",
        "def write_files(component_id, files, repo_root=None):",
        "    _log(WRITE_LOG, 'write_files', {'component_id': component_id, 'files': files, 'repo_root': repo_root})",
        "",
        "",
        "def check_assets(component_id, files, repo_root=None):",
        "    _log(GEN_LOG, 'check_assets', {'component_id': component_id, 'files': files, 'repo_root': repo_root})",
        "    for content in files.values():",
        "        if 'bad' in content:",
        "            return ('malformed_layout', ['static/app.txt: bad'])",
        "    return (None, [])",
        "",
        "",
        "def check_asset_environment(component_id, repo_root=None):",
        "    _log(GEN_LOG, 'check_asset_environment', {'component_id': component_id, 'repo_root': repo_root})",
        "    root = repo_root if repo_root is not None else " + repr(str(repo_root)),
        "    if os.path.exists(os.path.join(str(root), 'NO_ENV')):",
        "        return ('environment', ['fake needs fakeprog >= 2'])",
        "    return (None, [])",
        "",
    ]
    return "\n".join(lines)


def _loop_source(script_path, loop_log):
    lines = [
        "import json",
        "import types",
        "",
        "SCRIPT = " + repr(str(script_path)),
        "LOOP_LOG = " + repr(str(loop_log)),
        "",
        "",
        "def _log(kind, payload):",
        "    with open(LOOP_LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps([kind, payload], default=str) + '\\n')",
        "",
        "",
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,",
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,",
        "                  claude_command='claude'):",
        "    _log('args', {'system': system, 'prompt': prompt, 'model': model,",
        "                  'tools': tools, 'max_turns': max_turns,",
        "                  'max_tool_calls': max_tool_calls, 'wall_seconds': wall_seconds,",
        "                  'repo_root': repo_root, 'claude_command': claude_command})",
        "    with open(SCRIPT, encoding='utf-8') as fh:",
        "        script = json.load(fh)",
        "    calls = 0",
        "    for step in script['steps']:",
        "        calls += 1",
        "        text, is_error = execute(step['name'], step['arguments'])",
        "        _log('result', [step['name'], step['arguments'], text, is_error])",
        "    return types.SimpleNamespace(",
        "        text=script.get('text', ''),",
        "        transcript=[],",
        "        turns=1,",
        "        tool_calls=calls,",
        "        stop=script['stop'],",
        "        model_call_error=script['model_call_error'],",
        "    )",
        "",
    ]
    return "\n".join(lines)


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize(
    "stop, category",
    [
        ("budget_exhausted", "agent_budget_exhausted"),
        ("end_turn", "agent_unfinished"),
        ("error", "rate_limit"),
    ],
)
def test_ac_agent_006_unfinished_writes_nothing(tmp_path, monkeypatch, stop, category):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    gen_log = logs / "generator.log"
    write_log = logs / "write_files.log"
    loop_log = logs / "loop.log"
    script_path = logs / "script.json"

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        _generator_source(gen_log, write_log, repo_root), encoding="utf-8"
    )
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        _loop_source(script_path, loop_log), encoding="utf-8"
    )

    loop_error = {"category": "rate_limit", "message": "m"} if stop == "error" else None
    script = {
        "steps": [
            {
                "name": "write_file",
                "arguments": {"path": "work/widget.py", "content": "VALUE = 1\n"},
            }
        ],
        "stop": stop,
        "model_call_error": loop_error,
        "text": "",
    }
    script_path.write_text(json.dumps(script), encoding="utf-8")

    missing = str(tmp_path / "does-not-exist" / "sandbox")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    result = agentic_generator.generate_agentic(
        bundle, "anthropic:claude-sonnet-5", repo_root=repo_root
    )

    # The loop stand-in ran and the write itself succeeded inside the sandbox.
    results = [entry[1] for entry in _read_log(loop_log) if entry[0] == "result"]
    assert len(results) == 1
    name, arguments, text, is_error = results[0]
    assert name == "write_file"
    assert arguments["path"] == "work/widget.py"
    assert text == "wrote work/widget.py"
    assert is_error is False

    # Then: files is empty, write_files was never called.
    assert field(result, "files") == {}
    assert _read_log(write_log) == []
    assert not (repo_root / "gen" / "widget").exists()

    # And model_call_error's category is <category>.
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == category
    message = field(error, "message")
    assert isinstance(message, str)
    if stop == "error":
        assert error == {"category": "rate_limit", "message": "m"}
    else:
        assert message != ""
        assert stop in message