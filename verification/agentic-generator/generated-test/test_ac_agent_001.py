# hotdocs-criterion: sha256:a3ce6b47e4f1dba87665b95dcfe0aec656ac346ef7ed0d7a41a1a3f22de954da
import os
import tempfile
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generator_source(log_path, refusal):
    return (
        "import json\n"
        "import os\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REFUSAL = " + repr(refusal) + "\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry, default=str) + '\\n')\n"
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
        "    _log(['check_write_allowed', bundle['component_id'], str(repo_root)])\n"
        "    return REFUSAL\n"
        "\n"
        "\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    _log(['render_prompt_sections', bundle['component_id']])\n"
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        "\n"
        "\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    _log(['write_files', component_id, files, str(repo_root)])\n"
        "\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    _log(['check_assets', component_id, files, str(repo_root)])\n"
        "    for content in files.values():\n"
        "        if 'bad' in content:\n"
        "            return ('malformed_layout', ['static/app.txt: bad'])\n"
        "    return (None, [])\n"
        "\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    _log(['check_asset_environment', component_id, str(repo_root)])\n"
        "    if repo_root is not None and os.path.exists(os.path.join(str(repo_root), 'NO_ENV')):\n"
        "        return ('environment', ['fake needs fakeprog >= 2'])\n"
        "    return (None, [])\n"
    )


def _loop_source(log_path, script_path):
    return (
        "import json\n"
        "import os\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class _Result:\n"
        "    text: str = ''\n"
        "    transcript: list = field(default_factory=list)\n"
        "    turns: int = 0\n"
        "    tool_calls: int = 0\n"
        "    stop: str = 'end_turn'\n"
        "    model_call_error: object = None\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry, default=str) + '\\n')\n"
        "\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    _log(['called', system, prompt, model, tools, max_turns, max_tool_calls,\n"
        "          wall_seconds, str(repo_root), claude_command])\n"
        "    steps = []\n"
        "    if os.path.exists(SCRIPT):\n"
        "        with open(SCRIPT, encoding='utf-8') as fh:\n"
        "            steps = json.load(fh)\n"
        "    count = 0\n"
        "    for step in steps:\n"
        "        name = step[0]\n"
        "        arguments = step[1]\n"
        "        text, is_error = execute(name, arguments)\n"
        "        count += 1\n"
        "        _log(['step', name, arguments, text, is_error])\n"
        "    return _Result(text='done', transcript=[], turns=1, tool_calls=count,\n"
        "                   stop='end_turn', model_call_error=None)\n"
    )


def _setup(tmp_path, monkeypatch, refusal, no_env):
    repo_root = tmp_path / "repo"
    gen_dir = repo_root / "gen" / "generator"
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    gen_dir.mkdir(parents=True)
    loop_dir.mkdir(parents=True)
    logs = tmp_path / "logs"
    logs.mkdir()
    gen_log = logs / "generator.log"
    loop_log = logs / "loop.log"
    script = logs / "script.json"
    script.write_text("[]", encoding="utf-8")
    (gen_dir / "generator.py").write_text(_generator_source(gen_log, refusal), encoding="utf-8")
    (loop_dir / "llm_tool_endpoint.py").write_text(_loop_source(loop_log, script), encoding="utf-8")
    if no_env:
        (repo_root / "NO_ENV").write_text("", encoding="utf-8")

    fresh_tmp = tmp_path / "systmp"
    fresh_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(fresh_tmp))
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))
    return repo_root, loop_log


def _bundle():
    return {"component_id": "comp-widget", "spec_bundle_hash": "sha256:x", "hint_code": None}


def _agent_dirs():
    base = tempfile.gettempdir()
    return [n for n in os.listdir(base) if n.startswith("hotdocs-agent-")]


def test_refusal_returns_without_sandbox_or_loop(tmp_path, monkeypatch):
    repo_root, loop_log = _setup(tmp_path, monkeypatch, "sealed-component", False)

    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)

    assert field(result, "refused") == "sealed-component"
    assert field(result, "mode") == "agentic"
    assert field(result, "turns") == 0
    assert field(result, "tool_calls") == 0
    assert not loop_log.exists() or loop_log.read_text(encoding="utf-8").strip() == ""
    assert _agent_dirs() == []


def test_environment_failure_returns_model_call_error(tmp_path, monkeypatch):
    repo_root, loop_log = _setup(tmp_path, monkeypatch, None, True)

    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)

    assert field(result, "model_call_error") == {
        "category": "environment",
        "message": "fake needs fakeprog >= 2",
    }
    assert field(result, "turns") == 0
    assert not loop_log.exists() or loop_log.read_text(encoding="utf-8").strip() == ""