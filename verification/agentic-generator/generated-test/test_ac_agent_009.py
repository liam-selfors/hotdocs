# hotdocs-criterion: sha256:25ff4cf9b45cdc6a38001f231ec2af14ef5dd58567bb9506a76b5e79af12a6ab
import json
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_TEMPLATE_HEAD = (
    "import json\n"
    "import os\n"
    "from dataclasses import dataclass, field\n"
    "\n"
)

GENERATOR_TEMPLATE_BODY = (
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
    "    with open(path, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps(record, default=str) + '\\n')\n"
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
    "    _log(WRITE_LOG, [component_id, files, str(repo_root)])\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log(ASSETS_LOG, [component_id, files, str(repo_root)])\n"
    "    for content in files.values():\n"
    "        if 'bad' in content:\n"
    "            return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    if repo_root is not None and os.path.exists(os.path.join(str(repo_root), 'NO_ENV')):\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)

LOOP_TEMPLATE_HEAD = "import json\n\n"

LOOP_TEMPLATE_BODY = (
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
    "        return dict(text=self.text, transcript=self.transcript, turns=self.turns,\n"
    "                    tool_calls=self.tool_calls, stop=self.stop,\n"
    "                    model_call_error=self.model_call_error)\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    with open(ARGS_LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps([system, prompt, model, tools, max_turns, max_tool_calls,\n"
    "                            wall_seconds, str(repo_root), claude_command], default=str) + '\\n')\n"
    "    with open(SCRIPT, encoding='utf-8') as f:\n"
    "        steps = json.load(f)\n"
    "    count = 0\n"
    "    for step in steps:\n"
    "        name = step[0]\n"
    "        arguments = step[1]\n"
    "        text, is_error = execute(name, arguments)\n"
    "        count += 1\n"
    "        with open(CALL_LOG, 'a', encoding='utf-8') as f:\n"
    "            f.write(json.dumps([name, arguments, text, is_error]) + '\\n')\n"
    "    return ToolLoopResult('done', [], 1, count, 'end_turn', None)\n"
)


def setup_repo(repo_root, steps):
    repo_root = Path(repo_root)
    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)

    script = repo_root / "script.json"
    call_log = repo_root / "calls.jsonl"
    args_log = repo_root / "loop_args.jsonl"
    write_log = repo_root / "write_files.jsonl"
    assets_log = repo_root / "check_assets.jsonl"

    script.write_text(json.dumps(steps), encoding="utf-8")

    gen_src = (
        GENERATOR_TEMPLATE_HEAD
        + "WRITE_LOG = " + repr(str(write_log)) + "\n"
        + "ASSETS_LOG = " + repr(str(assets_log)) + "\n"
        + GENERATOR_TEMPLATE_BODY
    )
    (gen_dir / "generator.py").write_text(gen_src, encoding="utf-8")

    loop_src = (
        LOOP_TEMPLATE_HEAD
        + "SCRIPT = " + repr(str(script)) + "\n"
        + "CALL_LOG = " + repr(str(call_log)) + "\n"
        + "ARGS_LOG = " + repr(str(args_log)) + "\n"
        + LOOP_TEMPLATE_BODY
    )
    (loop_dir / "llm_tool_endpoint.py").write_text(loop_src, encoding="utf-8")
    return call_log


def read_calls(call_log):
    records = []
    for line in Path(call_log).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def make_bundle():
    return {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def test_ac_agent_009_tool_results_paths_limits_and_truncation(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    steps = [
        ["write_file", {"path": "work/pkg/a.py", "content": "A = 1"}],
        ["write_file", {"path": "work/pkg/b.py", "content": "B = 2"}],
        ["list_files", {"path": "work"}],
        ["read_file", {"path": "work/pkg"}],
        ["write_file", {"path": "scratch/long.txt", "content": "y" * 9000}],
        ["read_file", {"path": "scratch/long.txt"}],
    ]
    for i in range(1, 198):
        steps.append(["write_file", {"path": "scratch/f%03d.py" % i, "content": "x = 0"}])
    steps += [
        ["write_file", {"path": "scratch/f198.py", "content": "x = 0"}],
        ["write_file", {"path": "work/pkg/a.py", "content": "A = 2"}],
        ["read_file", {"path": "work/pkg/a.py"}],
        ["delete_file", {"path": "work/pkg/b.py"}],
        ["write_file", {"path": "scratch/f198.py", "content": "x = 0"}],
        ["finish", {"summary": "done"}],
    ]

    call_log = setup_repo(repo_root, steps)

    agentic_generator.generate_agentic(make_bundle(), "m", repo_root=repo_root)

    records = read_calls(call_log)
    actual = [(r[2], bool(r[3])) for r in records]
    for r in records:
        assert isinstance(r[2], str)
        assert isinstance(r[3], bool)

    expected = [
        ("wrote work/pkg/a.py", False),
        ("wrote work/pkg/b.py", False),
        ("work/pkg/a.py\nwork/pkg/b.py", False),
        ("not found: work/pkg", True),
        ("wrote scratch/long.txt", False),
        ("y" * 8192 + "\n[truncated]", False),
    ]
    for i in range(1, 198):
        expected.append(("wrote scratch/f%03d.py" % i, False))
    expected += [
        ("too many files: limit 200", True),
        ("wrote work/pkg/a.py", False),
        ("A = 2", False),
        ("deleted work/pkg/b.py", False),
        ("wrote scratch/f198.py", False),
        ("finished", False),
    ]

    assert len(actual) == len(expected)
    for index, (got, want) in enumerate(zip(actual, expected)):
        assert got == want, "call %d: %r != %r" % (index, got[0][:100], want[0][:100])


def test_ac_agent_009_check_import_unisolated(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")

    steps = [
        ["write_file", {"path": "work/widget.py", "content": "A = 1"}],
        ["check_import", {}],
        ["finish", {"summary": "done"}],
    ]
    call_log = setup_repo(repo_root, steps)

    result = agentic_generator.generate_agentic(
        make_bundle(), "m", repo_root=repo_root, allow_unisolated_exec=True
    )

    records = read_calls(call_log)
    check = [r for r in records if r[0] == "check_import"]
    assert len(check) == 1
    assert (check[0][2], check[0][3]) == ("0\n", False)
    assert check[0][3] is False

    assert field(result, "isolation") == "unisolated"