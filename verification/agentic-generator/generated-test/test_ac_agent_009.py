# hotdocs-criterion: sha256:77d11125e56e2f6b8837beaee389e9124e7728c5c4adf86ff10a9b1773cb4767
import json
from pathlib import Path

import agentic_generator


GENERATOR_STANDIN = (
    "import dataclasses\n"
    "import json\n"
    "import os\n"
    "\n"
    "_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"
    "\n"
    "\n"
    "def _log(name, record):\n"
    "    with open(os.path.join(_ROOT, name), 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(record) + '\\n')\n"
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
    "    _log('write_files.jsonl', {'component_id': component_id, 'files': dict(files),\n"
    "                               'repo_root': None if repo_root is None else str(repo_root)})\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log('check_assets.jsonl', {'component_id': component_id, 'files': dict(files),\n"
    "                                'repo_root': None if repo_root is None else str(repo_root)})\n"
    "    if any('bad' in content for content in files.values()):\n"
    "        return ('malformed_layout', ['static/app.txt: bad'])\n"
    "    return (None, [])\n"
    "\n"
    "\n"
    "def check_asset_environment(component_id, repo_root=None):\n"
    "    base = str(repo_root) if repo_root is not None else _ROOT\n"
    "    if os.path.exists(os.path.join(base, 'NO_ENV')):\n"
    "        return ('environment', ['fake needs fakeprog >= 2'])\n"
    "    return (None, [])\n"
)


LOOP_STANDIN = (
    "import json\n"
    "import os\n"
    "\n"
    "_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n"
    "\n"
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
    "    with open(os.path.join(_ROOT, 'loop_args.jsonl'), 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
    "                             'tools': tools, 'max_turns': max_turns,\n"
    "                             'max_tool_calls': max_tool_calls,\n"
    "                             'wall_seconds': wall_seconds,\n"
    "                             'repo_root': None if repo_root is None else str(repo_root),\n"
    "                             'claude_command': claude_command}) + '\\n')\n"
    "    with open(os.path.join(_ROOT, 'script.json'), encoding='utf-8') as fh:\n"
    "        script = json.load(fh)\n"
    "    count = 0\n"
    "    for step in script:\n"
    "        name, arguments = step[0], step[1]\n"
    "        text, is_error = execute(name, arguments)\n"
    "        count += 1\n"
    "        with open(os.path.join(_ROOT, 'results.jsonl'), 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps([name, arguments, text, is_error]) + '\\n')\n"
    "    return ToolLoopResult('done', [], 1, count, 'end_turn', None)\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_repo(tmp_path, script):
    repo_root = tmp_path / "repo"
    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(GENERATOR_STANDIN, encoding="utf-8")
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(LOOP_STANDIN, encoding="utf-8")
    (repo_root / "script.json").write_text(json.dumps(script), encoding="utf-8")
    return repo_root


def read_results(repo_root):
    path = repo_root / "results.jsonl"
    assert path.is_file(), "loop stand-in never recorded a result"
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def make_bundle():
    return {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def test_ac_agent_009_tool_results_follow_rules_and_limits(tmp_path):
    script = [
        ["write_file", {"path": "work/pkg/a.py", "content": "A = 1"}],
        ["write_file", {"path": "work/pkg/b.py", "content": "B = 2"}],
        ["list_files", {"path": "work"}],
        ["read_file", {"path": "work/pkg"}],
        ["write_file", {"path": "scratch/long.txt", "content": "y" * 9000}],
        ["read_file", {"path": "scratch/long.txt"}],
    ]
    for i in range(1, 198):
        script.append(["write_file", {"path": "scratch/f%03d.py" % i, "content": "x = 0"}])
    script += [
        ["write_file", {"path": "scratch/f198.py", "content": "x = 0"}],
        ["write_file", {"path": "work/pkg/a.py", "content": "A = 2"}],
        ["read_file", {"path": "work/pkg/a.py"}],
        ["delete_file", {"path": "work/pkg/b.py"}],
        ["write_file", {"path": "scratch/f198.py", "content": "x = 0"}],
        ["finish", {"summary": "done"}],
    ]
    repo_root = make_repo(tmp_path, script)

    agentic_generator.generate_agentic(make_bundle(), "m", repo_root=repo_root)

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

    records = read_results(repo_root)
    actual = [(r[2], r[3]) for r in records]
    assert len(actual) == len(expected)
    for index, (got, want) in enumerate(zip(actual, expected)):
        assert got[0] == want[0], (index, got[0][:200], want[0][:200])
        assert got[1] == want[1], (index, got, want)
        assert isinstance(got[1], bool), (index, got)


def test_ac_agent_009_unisolated_check_import(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")
    script = [
        ["write_file", {"path": "work/widget.py", "content": "A = 1"}],
        ["check_import", {}],
        ["finish", {"summary": "done"}],
    ]
    repo_root = make_repo(tmp_path, script)

    result = agentic_generator.generate_agentic(
        make_bundle(), "m", repo_root=repo_root, allow_unisolated_exec=True
    )

    records = read_results(repo_root)
    check_records = [r for r in records if r[0] == "check_import"]
    assert len(check_records) == 1
    assert (check_records[0][2], check_records[0][3]) == ("0\n", False)
    assert check_records[0][3] is False
    assert field(result, "isolation") == "unisolated"