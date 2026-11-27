# hotdocs-criterion: sha256:71f961433b1185dd27940633925f7f0100dc1ef3c05a14266e9cef746e2a6240
import os
import tempfile
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_generator(repo_root, refusal, log_path):
    d = repo_root / "gen" / "generator"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REFUSAL = " + repr(refusal) + "\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
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
        "    _log(['check_write_allowed'])\n"
        "    return REFUSAL\n"
        "\n"
        "\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        "\n"
        "\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    _log(['write_files', component_id, files])\n"
        "\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    _log(['check_assets', component_id, files])\n"
        "    for content in files.values():\n"
        "        if 'bad' in content:\n"
        "            return ('malformed_layout', ['static/app.txt: bad'])\n"
        "    return (None, [])\n"
        "\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    _log(['check_asset_environment', component_id])\n"
        "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():\n"
        "        return ('environment', ['fake needs fakeprog >= 2'])\n"
        "    return (None, [])\n"
    )
    (d / "generator.py").write_text(src, encoding="utf-8")


def _write_loop(repo_root, log_path, script_path):
    d = repo_root / "gen" / "llm-tool-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
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
        "class ToolUseUnsupported(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(['run_tool_loop', model]) + '\\n')\n"
        "    try:\n"
        "        with open(SCRIPT, encoding='utf-8') as fh:\n"
        "            steps = json.load(fh)\n"
        "    except OSError:\n"
        "        steps = []\n"
        "    count = 0\n"
        "    for step in steps:\n"
        "        text, is_error = execute(step['name'], step['arguments'])\n"
        "        count += 1\n"
        "        with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(json.dumps([step['name'], step['arguments'], text, is_error]) + '\\n')\n"
        "    return ToolLoopResult(text='done', transcript=[], turns=1,\n"
        "                          tool_calls=count, stop='end_turn', model_call_error=None)\n"
    )
    (d / "llm_tool_endpoint.py").write_text(src, encoding="utf-8")


def _agent_dirs():
    base = Path(tempfile.gettempdir())
    return {p.name for p in base.iterdir() if p.name.startswith("hotdocs-agent-")}


def _setup(tmp_path, refusal):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    gen_log = tmp_path / "gen.log"
    loop_log = tmp_path / "loop.log"
    script = tmp_path / "script.json"
    script.write_text("[]", encoding="utf-8")
    _write_generator(repo_root, refusal, gen_log)
    _write_loop(repo_root, loop_log, script)
    return repo_root, loop_log


def _bundle():
    return {"component_id": "comp-widget", "spec_bundle_hash": "sha256:x", "hint_code": None}


def _loop_called(loop_log):
    if not loop_log.exists():
        return False
    return any(
        line.strip() for line in loop_log.read_text(encoding="utf-8").splitlines()
    )


def test_sealed_component_refused_without_sandbox_or_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))
    repo_root, loop_log = _setup(tmp_path, "sealed-component")

    before = _agent_dirs()
    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)
    after = _agent_dirs()

    assert field(result, "refused") == "sealed-component"
    assert field(result, "mode") == "agentic"
    assert field(result, "turns") == 0
    assert field(result, "tool_calls") == 0
    assert not _loop_called(loop_log)
    assert after - before == set()


def test_environment_failure_returns_model_call_error(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))
    repo_root, loop_log = _setup(tmp_path, None)
    (repo_root / "NO_ENV").write_text("", encoding="utf-8")

    before = _agent_dirs()
    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)
    after = _agent_dirs()

    assert field(result, "model_call_error") == {
        "category": "environment",
        "message": "fake needs fakeprog >= 2",
    }
    assert field(result, "turns") == 0
    assert field(result, "tool_calls") == 0
    assert field(result, "mode") == "agentic"
    assert not _loop_called(loop_log)
    assert after - before == set()