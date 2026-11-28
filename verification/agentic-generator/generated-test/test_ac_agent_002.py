# hotdocs-criterion: sha256:06bd9950b6dae8d9b97f416ac112ad2b525b29493bde1099d3dd84f499e03ea5
import json
from pathlib import Path

import pytest

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
    "def _log(entry):\n"
    "    with open(GEN_LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
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
    "    _log(['write_files', component_id, dict(files), str(repo_root)])\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log(['check_assets', component_id, dict(files), str(repo_root)])\n"
    "    for content in files.values():\n"
    "        if 'bad' in content:\n"
    "            return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    from pathlib import Path as _P\n"
    "    if repo_root is not None and (_P(repo_root) / 'NO_ENV').exists():\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)

LOOP_SOURCE_BODY = (
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
    "        return dict(text=self.text, transcript=self.transcript, turns=self.turns,\n"
    "                    tool_calls=self.tool_calls, stop=self.stop,\n"
    "                    model_call_error=self.model_call_error)\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    record = dict(\n"
    "        system=system, prompt=prompt, model=model,\n"
    "        tool_names=[t['name'] for t in tools],\n"
    "        max_turns=max_turns, max_tool_calls=max_tool_calls,\n"
    "        wall_seconds=wall_seconds,\n"
    "        repo_root=None if repo_root is None else str(repo_root),\n"
    "        claude_command=claude_command,\n"
    "    )\n"
    "    with open(ARGS_LOG, 'w', encoding='utf-8') as fh:\n"
    "        json.dump(record, fh)\n"
    "    with open(SCRIPT_PATH, encoding='utf-8') as fh:\n"
    "        steps = json.load(fh)\n"
    "    results = []\n"
    "    for step in steps:\n"
    "        text, is_error = execute(step['name'], step['arguments'])\n"
    "        results.append([step['name'], step['arguments'], text, bool(is_error)])\n"
    "        with open(RESULTS_LOG, 'w', encoding='utf-8') as fh:\n"
    "            json.dump(results, fh)\n"
    "    return _Result('done', [], len(steps), len(steps), 'end_turn', None)\n"
)

SCRIPT = [
    {"name": "list_files", "arguments": {"path": "bundle"}},
    {"name": "read_file", "arguments": {"path": "bundle/01-spec.md"}},
    {"name": "read_file", "arguments": {"path": "bundle/02-component-interface.md"}},
    {"name": "write_file", "arguments": {"path": "bundle/x.md", "content": "x"}},
    {"name": "list_files", "arguments": {"path": "work"}},
    {"name": "finish", "arguments": {"summary": "done"}},
]


def _setup(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir(parents=True)
    repo_root.mkdir()

    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-such-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-such-bwrap"))

    gen_log = logs / "generator.log"
    args_log = logs / "loop_args.json"
    results_log = logs / "loop_results.json"
    script_path = logs / "script.json"
    script_path.write_text(json.dumps(SCRIPT), encoding="utf-8")

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        GENERATOR_SOURCE_TEMPLATE_HEAD
        + "GEN_LOG = " + repr(str(gen_log)) + "\n"
        + GENERATOR_SOURCE_BODY,
        encoding="utf-8",
    )

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        "import json\n"
        + "ARGS_LOG = " + repr(str(args_log)) + "\n"
        + "RESULTS_LOG = " + repr(str(results_log)) + "\n"
        + "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        + LOOP_SOURCE_BODY,
        encoding="utf-8",
    )
    return repo_root, args_log, results_log


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def _run(repo_root):
    return agentic_generator.generate_agentic(_bundle(), "m", repo_root=repo_root, max_turns=7)


def test_ac_agent_002_sandbox_tools_and_texts(tmp_path, monkeypatch):
    repo_root, args_log, results_log = _setup(tmp_path, monkeypatch)

    _run(repo_root)

    assert results_log.is_file(), "loop stand-in never ran a tool"
    results = json.loads(results_log.read_text(encoding="utf-8"))
    assert len(results) == 6
    texts = [r[2] for r in results]
    errors = [r[3] for r in results]

    assert texts[0] == "bundle/01-spec.md\nbundle/02-component-interface.md"
    assert errors[0] is False
    assert texts[1] == "SPEC TEXT"
    assert errors[1] is False
    assert texts[2] == "IFACE TEXT"
    assert errors[2] is False
    assert errors[3] is True
    assert texts[3].startswith("path not allowed:")
    assert texts[4] == ""
    assert errors[4] is False
    assert texts[5] == "finished"
    assert errors[5] is False

    args = json.loads(args_log.read_text(encoding="utf-8"))
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
        assert needle in system, needle

    prompt = args["prompt"]
    assert "bundle/01-spec.md" in prompt
    assert "bundle/02-component-interface.md" in prompt


def test_ac_agent_002_system_names_declared_asset(tmp_path, monkeypatch):
    repo_root, args_log, results_log = _setup(tmp_path, monkeypatch)

    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-widget-maker\n"
        "title: Widget Maker\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
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

    args = json.loads(args_log.read_text(encoding="utf-8"))
    system = args["system"]
    assert "static/app.txt" in system
    for needle in ("work/", "scratch/", "widget_maker.py", "finish"):
        assert needle in system, needle