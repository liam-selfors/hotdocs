# hotdocs-criterion: sha256:cce23d6377f3a4db526a406bce46dffa20ac02417c318473ce6c11b14a384783
import json
from pathlib import Path

import pytest

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_generator_stand_in(repo_root, log_path):
    src = (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(entry, default=str) + '\\n')\n"
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
        "def check_write_allowed(bundle, repo_root=None):\n"
        "    return None\n"
        "\n"
        "def render_prompt_sections(bundle, retry_feedback=None):\n"
        "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        "\n"
        "def write_files(component_id, files, repo_root=None):\n"
        "    _log(['write_files', component_id, files, repo_root])\n"
        "\n"
        "def check_assets(component_id, files, repo_root=None):\n"
        "    _log(['check_assets', component_id, files, repo_root])\n"
        "    for content in files.values():\n"
        "        if 'bad' in content:\n"
        "            return ('malformed_layout', ['static/app.txt: bad'])\n"
        "    return (None, [])\n"
        "\n"
        "def check_asset_environment(component_id, repo_root=None):\n"
        "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():\n"
        "        return ('environment', ['fake needs fakeprog >= 2'])\n"
        "    return (None, [])\n"
    )
    d = repo_root / "gen" / "generator"
    d.mkdir(parents=True, exist_ok=True)
    (d / "generator.py").write_text(src, encoding="utf-8")


def _write_loop_stand_in(repo_root, args_path, script_path, results_path):
    src = (
        "import dataclasses\n"
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "ARGS = " + repr(str(args_path)) + "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "RESULTS = " + repr(str(results_path)) + "\n"
        "\n"
        "class ToolUseUnsupported(Exception):\n"
        "    pass\n"
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
        "def serve_mcp(socket_path, tools_path):\n"
        "    return 0\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    record = {'system': system, 'prompt': prompt, 'model': model,\n"
        "              'tools': tools, 'max_turns': max_turns,\n"
        "              'max_tool_calls': max_tool_calls, 'wall_seconds': wall_seconds,\n"
        "              'repo_root': repo_root, 'claude_command': claude_command}\n"
        "    with open(ARGS, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(record, default=str) + '\\n')\n"
        "    with open(SCRIPT, encoding='utf-8') as f:\n"
        "        steps = json.load(f)\n"
        "    count = 0\n"
        "    for step in steps:\n"
        "        name = step[0]\n"
        "        arguments = step[1]\n"
        "        count += 1\n"
        "        text, is_error = execute(name, arguments)\n"
        "        with open(RESULTS, 'a', encoding='utf-8') as f:\n"
        "            f.write(json.dumps([name, arguments, text, is_error], default=str) + '\\n')\n"
        "    return ToolLoopResult(text='done',\n"
        "                          transcript=[{'role': 'user', 'content': prompt}],\n"
        "                          turns=1, tool_calls=count, stop='end_turn',\n"
        "                          model_call_error=None)\n"
    )
    d = repo_root / "gen" / "llm-tool-endpoint"
    d.mkdir(parents=True, exist_ok=True)
    (d / "llm_tool_endpoint.py").write_text(src, encoding="utf-8")


SCRIPT_STEPS = [
    ["list_files", {"path": "bundle"}],
    ["read_file", {"path": "bundle/01-spec.md"}],
    ["read_file", {"path": "bundle/02-component-interface.md"}],
    ["write_file", {"path": "bundle/x.md", "content": "x"}],
    ["list_files", {"path": "work"}],
    ["finish", {"summary": "done"}],
]


def _setup(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    args_path = logs / "loop_args.jsonl"
    script_path = logs / "script.json"
    results_path = logs / "results.jsonl"
    gen_log = logs / "generator.jsonl"
    script_path.write_text(json.dumps(SCRIPT_STEPS), encoding="utf-8")
    _write_generator_stand_in(repo_root, gen_log)
    _write_loop_stand_in(repo_root, args_path, script_path, results_path)
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))
    return repo_root, args_path, results_path


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def _read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run(repo_root):
    return agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root, max_turns=7)


def test_ac_agent_002_sandbox_tools_and_prompt(tmp_path, monkeypatch):
    repo_root, args_path, results_path = _setup(tmp_path, monkeypatch)

    _run(repo_root)

    results = _read_jsonl(results_path)
    assert len(results) == 6
    texts = [r[2] for r in results]
    errors = [r[3] for r in results]
    assert texts[0] == "bundle/01-spec.md\nbundle/02-component-interface.md"
    assert texts[1] == "SPEC TEXT"
    assert texts[2] == "IFACE TEXT"
    assert texts[3].startswith("path not allowed:")
    assert errors[3]
    assert texts[4] == ""
    assert texts[5] == "finished"
    for i in (0, 1, 2, 4, 5):
        assert not errors[i], (i, texts[i])

    calls = _read_jsonl(args_path)
    assert len(calls) == 1
    call = calls[0]
    names = [t["name"] for t in call["tools"]]
    assert names == [
        "list_files",
        "read_file",
        "write_file",
        "delete_file",
        "check_import",
        "run_scratch_tests",
        "finish",
    ]
    assert call["max_turns"] == 7
    assert call["model"] == "m"
    system = call["system"]
    assert "work/" in system
    assert "scratch/" in system
    assert "widget_maker.py" in system
    assert "finish" in system
    prompt = call["prompt"]
    assert "bundle/01-spec.md" in prompt
    assert "bundle/02-component-interface.md" in prompt


def test_ac_agent_002_system_names_declared_asset(tmp_path, monkeypatch):
    repo_root, args_path, results_path = _setup(tmp_path, monkeypatch)
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-widget-maker\n"
        "title: Widget Maker\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget-maker/\n"
        "assets: [fake:static/app.txt]\n"
        "---\n"
        "\n"
        "# Widget Maker\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes widgets.\n",
        encoding="utf-8",
    )

    _run(repo_root)

    calls = _read_jsonl(args_path)
    assert len(calls) == 1
    system = calls[0]["system"]
    assert "static/app.txt" in system
    assert "work/" in system
    assert "scratch/" in system
    assert "widget_maker.py" in system
    assert "finish" in system