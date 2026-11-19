# hotdocs-criterion: sha256:10f1741dd88c7deffcebea2e1442e1935ff75ec89123505580436ca4a76661db
import json
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SOURCE_TEMPLATE_HEAD = (
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "\n"
)

GENERATOR_SOURCE_BODY = (
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
    "def _log(path, record):\n"
    "    with open(path, 'a', encoding='utf-8') as handle:\n"
    "        handle.write(json.dumps(record) + '\\n')\n"
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
    "    _log(WRITE_LOG, {'component_id': component_id, 'files': dict(files),\n"
    "                     'repo_root': None if repo_root is None else str(repo_root)})\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log(ASSETS_LOG, {'component_id': component_id, 'files': dict(files),\n"
    "                      'repo_root': None if repo_root is None else str(repo_root)})\n"
    "    for content in files.values():\n"
    "        if 'bad' in content:\n"
    "            return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    import os\n"
    "    if repo_root is not None and os.path.exists(os.path.join(str(repo_root), 'NO_ENV')):\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)

LOOP_SOURCE_BODY = (
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
    "    with open(ARGS_PATH, 'w', encoding='utf-8') as handle:\n"
    "        json.dump({'system': system, 'prompt': prompt, 'model': model,\n"
    "                   'tools': tools, 'max_turns': max_turns,\n"
    "                   'max_tool_calls': max_tool_calls, 'wall_seconds': wall_seconds,\n"
    "                   'repo_root': None if repo_root is None else str(repo_root),\n"
    "                   'claude_command': claude_command}, handle)\n"
    "    with open(SCRIPT_PATH, encoding='utf-8') as handle:\n"
    "        script = json.load(handle)\n"
    "    count = 0\n"
    "    for step in script:\n"
    "        text, is_error = execute(step['name'], step['arguments'])\n"
    "        count += 1\n"
    "        with open(RESULTS_PATH, 'a', encoding='utf-8') as handle:\n"
    "            handle.write(json.dumps([step['name'], step['arguments'], text, bool(is_error)]) + '\\n')\n"
    "    return ToolLoopResult(text='done', transcript=[], turns=1, tool_calls=count,\n"
    "                          stop='end_turn', model_call_error=None)\n"
)

SCRIPT = [
    {"name": "list_files", "arguments": {"path": "bundle"}},
    {"name": "read_file", "arguments": {"path": "bundle/01-spec.md"}},
    {"name": "read_file", "arguments": {"path": "bundle/02-component-interface.md"}},
    {"name": "write_file", "arguments": {"path": "bundle/x.md", "content": "x"}},
    {"name": "list_files", "arguments": {"path": "work"}},
    {"name": "finish", "arguments": {"summary": "done"}},
]


def _setup(repo_root, logs):
    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    generator_source = (
        GENERATOR_SOURCE_TEMPLATE_HEAD
        + "WRITE_LOG = " + repr(str(logs / "write_files.log")) + "\n"
        + "ASSETS_LOG = " + repr(str(logs / "check_assets.log")) + "\n"
        + GENERATOR_SOURCE_BODY
    )
    (gen_dir / "generator.py").write_text(generator_source, encoding="utf-8")

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    script_path = logs / "script.json"
    script_path.write_text(json.dumps(SCRIPT), encoding="utf-8")
    loop_source = (
        "import json\n"
        + "ARGS_PATH = " + repr(str(logs / "args.json")) + "\n"
        + "RESULTS_PATH = " + repr(str(logs / "results.log")) + "\n"
        + "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        + LOOP_SOURCE_BODY
    )
    (loop_dir / "llm_tool_endpoint.py").write_text(loop_source, encoding="utf-8")


def _run(tmp_path, monkeypatch, with_assets):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    _setup(repo_root, logs)
    if with_assets:
        comp_dir = repo_root / "specs" / "components" / "widget-maker"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(
            "---\n"
            "id: comp-widget-maker\n"
            "title: Widget Maker\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "sealed: true\n"
            "source_path: legacy/widget/\n"
            "assets: [fake:static/app.txt]\n"
            "---\n"
            "\n"
            "# Widget Maker\n"
            "\n"
            "Makes widgets.\n",
            encoding="utf-8",
        )
    bundle = {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }
    agentic_generator.generate_agentic(bundle, "m", repo_root=repo_root, max_turns=7)
    args = json.loads((logs / "args.json").read_text(encoding="utf-8"))
    results = [
        json.loads(line)
        for line in (logs / "results.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return args, results


def test_ac_agent_002_sandbox_tools_and_prompt(tmp_path, monkeypatch):
    args, results = _run(tmp_path, monkeypatch, with_assets=False)

    texts = [r[2] for r in results]
    errors = [r[3] for r in results]
    assert len(results) == 6
    assert texts[0] == "bundle/01-spec.md\nbundle/02-component-interface.md"
    assert texts[1] == "SPEC TEXT"
    assert texts[2] == "IFACE TEXT"
    assert texts[3].startswith("path not allowed:")
    assert errors[3] is True
    assert texts[4] == ""
    assert texts[5] == "finished"
    assert not any(errors[i] for i in (0, 1, 2, 4, 5))

    names = [field(t, "name") for t in args["tools"]]
    assert names == [
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
    assert "work/" in system
    assert "scratch/" in system
    assert "widget_maker.py" in system
    assert "finish" in system

    prompt = args["prompt"]
    assert "bundle/01-spec.md" in prompt
    assert "bundle/02-component-interface.md" in prompt


def test_ac_agent_002_system_text_names_declared_assets(tmp_path, monkeypatch):
    args, results = _run(tmp_path, monkeypatch, with_assets=True)

    texts = [r[2] for r in results]
    assert texts[0] == "bundle/01-spec.md\nbundle/02-component-interface.md"
    assert texts[5] == "finished"
    assert args["max_turns"] == 7

    system = args["system"]
    assert "work/" in system
    assert "scratch/" in system
    assert "widget_maker.py" in system
    assert "finish" in system
    assert "static/app.txt" in system