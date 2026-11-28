# hotdocs-criterion: sha256:76168ae2b1add298ed5f3723b75658cf14e1258947e932500b993efdc245d910
import json
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SOURCE_TEMPLATE_HEAD = (
    "import dataclasses\n"
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "LOG_DIR = "
)

GENERATOR_SOURCE_BODY = (
    "\n"
    "\n"
    "def _log(name, payload):\n"
    "    with open(str(Path(LOG_DIR) / name), 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(payload, sort_keys=True, default=str) + '\\n')\n"
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
    "    return None\n"
    "\n"
    "\n"
    "def render_prompt_sections(bundle, retry_feedback=None):\n"
    "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
    "\n"
    "\n"
    "def write_files(component_id, files, repo_root=None):\n"
    "    _log('write_files.log', [component_id, files, str(repo_root)])\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log('check_assets.log', [component_id, files, str(repo_root)])\n"
    "    for content in files.values():\n"
    "        if 'bad' in content:\n"
    "            return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)

LOOP_SOURCE_HEAD = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "LOG_DIR = "
)

LOOP_SOURCE_MID = "\nSCRIPT_PATH = "

LOOP_SOURCE_BODY = (
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
    "        return dict(text=self.text, transcript=self.transcript, turns=self.turns,\n"
    "                    tool_calls=self.tool_calls, stop=self.stop,\n"
    "                    model_call_error=self.model_call_error)\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    with open(str(Path(LOG_DIR) / 'loop_args.log'), 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps([system, prompt, model, tools, max_turns, max_tool_calls,\n"
    "                             wall_seconds, str(repo_root), claude_command],\n"
    "                            default=str) + '\\n')\n"
    "    with open(SCRIPT_PATH, 'r', encoding='utf-8') as fh:\n"
    "        script = json.load(fh)\n"
    "    count = 0\n"
    "    for step in script:\n"
    "        name = step[0]\n"
    "        arguments = step[1]\n"
    "        text, is_error = execute(name, arguments)\n"
    "        count += 1\n"
    "        with open(str(Path(LOG_DIR) / 'results.log'), 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps([name, arguments, text, is_error]) + '\\n')\n"
    "    return _Result('done', [{'role': 'user', 'content': prompt}], 1, count,\n"
    "                   'end_turn', None)\n"
)


def _write_stand_ins(repo_root, log_dir, script_path):
    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        GENERATOR_SOURCE_TEMPLATE_HEAD + repr(str(log_dir)) + GENERATOR_SOURCE_BODY,
        encoding="utf-8",
    )
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        LOOP_SOURCE_HEAD
        + repr(str(log_dir))
        + LOOP_SOURCE_MID
        + repr(str(script_path))
        + LOOP_SOURCE_BODY,
        encoding="utf-8",
    )


def test_ac_agent_003_tool_results_in_order(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    script_path = tmp_path / "script.json"

    script = [
        ["write_file", {"path": "work/a.py", "content": "x = 1"}],
        ["read_file", {"path": "work/a.py"}],
        ["read_file", {"path": "/etc/hosts"}],
        ["read_file", {"path": "work/../bundle/01-spec.md"}],
        ["read_file", {"path": "secrets/k"}],
        ["write_file", {"path": "work/big.py", "content": "a" * 524289}],
        ["delete_file", {"path": "work/a.py"}],
        ["read_file", {"path": "work/a.py"}],
        ["shell", {}],
        ["read_file", {}],
        ["finish", {"summary": "done"}],
        ["write_file", {"path": "work/b.py"}],
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")
    _write_stand_ins(repo_root, log_dir, script_path)

    missing = str(tmp_path / "no-such-sandbox-binary")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    agentic_generator.generate_agentic(
        bundle, "anthropic:test-model", None, repo_root=repo_root
    )

    results_log = log_dir / "results.log"
    assert results_log.is_file(), "loop stand-in never ran"
    records = [
        json.loads(line)
        for line in results_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == len(script)
    texts = [r[2] for r in records]
    errors = [r[3] for r in records]
    for t in texts:
        assert isinstance(t, str)

    # 1. write_file work/a.py
    assert texts[0] == "wrote work/a.py"
    assert not errors[0]
    # 2. read_file work/a.py
    assert texts[1] == "x = 1"
    assert not errors[1]
    # 3-5. three path rejections
    for i in (2, 3, 4):
        assert texts[i].startswith("path not allowed:"), texts[i]
        assert errors[i]
    # 6. size limit
    assert errors[5]
    assert "524288" in texts[5], texts[5]
    assert texts[5].startswith("too large:"), texts[5]
    # 7. delete
    assert texts[6] == "deleted work/a.py"
    assert not errors[6]
    # 8. read of the deleted file
    assert errors[7]
    # 9. unknown tool
    assert texts[8].startswith("bad call:"), texts[8]
    assert errors[8]
    # 10. missing argument
    assert texts[9].startswith("bad call:"), texts[9]
    assert errors[9]
    # 11. finish
    assert texts[10] == "finished"
    assert not errors[10]
    # 12. any call after finish
    assert texts[11] == "already finished"
    assert errors[11]