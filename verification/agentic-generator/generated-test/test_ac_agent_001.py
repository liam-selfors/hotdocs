# hotdocs-criterion: sha256:ee2bbefb74ae16a14f741f25fe184009baf78fe2a4f1a7f2641ffcf6b69e86c8
import os
import tempfile
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generator_source(log_dir, refusal):
    log_dir = str(log_dir)
    lines = [
        "import dataclasses",
        "import json",
        "import os",
        "from pathlib import Path",
        "",
        "LOG_DIR = " + repr(log_dir),
        "REFUSAL = " + repr(refusal),
        "",
        "",
        "def _log(name, payload):",
        "    with open(os.path.join(LOG_DIR, name), 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps(payload, default=str) + '\\n')",
        "",
        "",
        "@dataclasses.dataclass",
        "class GenerationResult:",
        "    component_id: str = ''",
        "    spec_bundle_hash: str = ''",
        "    model: str = ''",
        "    prompt_version: str = ''",
        "    cache_hit: bool = False",
        "    files: dict = dataclasses.field(default_factory=dict)",
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
        "    _log('check_write_allowed.log', [bundle['component_id'], str(repo_root)])",
        "    return REFUSAL",
        "",
        "",
        "def render_prompt_sections(bundle, retry_feedback=None):",
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]",
        "",
        "",
        "def write_files(component_id, files, repo_root=None):",
        "    _log('write_files.log', [component_id, files, str(repo_root)])",
        "",
        "",
        "def check_assets(component_id, files, repo_root=None):",
        "    _log('check_assets.log', [component_id, files, str(repo_root)])",
        "    for content in files.values():",
        "        if 'bad' in content:",
        "            return ('malformed_layout', ['static/app.txt: bad'])",
        "    return (None, [])",
        "",
        "",
        "def check_asset_environment(component_id, repo_root=None):",
        "    _log('check_asset_environment.log', [component_id, str(repo_root)])",
        "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():",
        "        return ('environment', ['fake needs fakeprog >= 2'])",
        "    return (None, [])",
        "",
    ]
    return "\n".join(lines)


def _loop_source(log_dir, script_path):
    lines = [
        "import dataclasses",
        "import json",
        "import os",
        "",
        "LOG_DIR = " + repr(str(log_dir)),
        "SCRIPT = " + repr(str(script_path)),
        "",
        "",
        "@dataclasses.dataclass",
        "class ToolLoopResult:",
        "    text: str = ''",
        "    transcript: list = dataclasses.field(default_factory=list)",
        "    turns: int = 0",
        "    tool_calls: int = 0",
        "    stop: str = 'end_turn'",
        "    model_call_error: object = None",
        "",
        "    def to_dict(self):",
        "        return dataclasses.asdict(self)",
        "",
        "",
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,",
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,",
        "                  claude_command='claude'):",
        "    with open(os.path.join(LOG_DIR, 'loop_calls.log'), 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,",
        "                             'tools': tools, 'max_turns': max_turns,",
        "                             'max_tool_calls': max_tool_calls,",
        "                             'wall_seconds': wall_seconds,",
        "                             'repo_root': str(repo_root),",
        "                             'claude_command': claude_command}, default=str) + '\\n')",
        "    steps = []",
        "    if os.path.exists(SCRIPT):",
        "        with open(SCRIPT, encoding='utf-8') as fh:",
        "            steps = json.load(fh)",
        "    count = 0",
        "    for step in steps:",
        "        text, is_error = execute(step['name'], step['arguments'])",
        "        count += 1",
        "        with open(os.path.join(LOG_DIR, 'loop_results.log'), 'a', encoding='utf-8') as fh:",
        "            fh.write(json.dumps([step['name'], step['arguments'], text, is_error]) + '\\n')",
        "    return ToolLoopResult(text='done', transcript=[], turns=1, tool_calls=count,",
        "                          stop='end_turn', model_call_error=None)",
        "",
    ]
    return "\n".join(lines)


def _setup(tmp_path, monkeypatch, refusal):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    fake_tmp = tmp_path / "systmp"
    fake_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(fake_tmp))
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(_generator_source(log_dir, refusal), encoding="utf-8")

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    script_path = tmp_path / "script.json"
    script_path.write_text("[]", encoding="utf-8")
    (loop_dir / "llm_tool_endpoint.py").write_text(
        _loop_source(log_dir, script_path), encoding="utf-8"
    )
    return repo_root, log_dir


def _bundle():
    return {"component_id": "comp-widget", "spec_bundle_hash": "sha256:x", "hint_code": None}


def _agent_dirs():
    base = tempfile.gettempdir()
    return [n for n in os.listdir(base) if n.startswith("hotdocs-agent-")]


def test_sealed_component_refused_without_sandbox_or_loop(tmp_path, monkeypatch):
    repo_root, log_dir = _setup(tmp_path, monkeypatch, "sealed-component")

    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)

    assert field(result, "refused") == "sealed-component"
    assert field(result, "mode") == "agentic"
    assert field(result, "turns") == 0
    assert field(result, "tool_calls") == 0
    assert (log_dir / "check_write_allowed.log").exists()
    assert not (log_dir / "loop_calls.log").exists()
    assert _agent_dirs() == []


def test_environment_failure_returns_model_call_error(tmp_path, monkeypatch):
    repo_root, log_dir = _setup(tmp_path, monkeypatch, None)
    (repo_root / "NO_ENV").write_text("", encoding="utf-8")

    result = agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root)

    assert field(result, "model_call_error") == {
        "category": "environment",
        "message": "fake needs fakeprog >= 2",
    }
    assert field(result, "turns") == 0
    assert not (log_dir / "loop_calls.log").exists()