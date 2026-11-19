# hotdocs-criterion: sha256:59efc19c7fa012cb10c4216a95ff19ebb0ef46c0b3001cde90b817e2d75f4582
import json
import os
from pathlib import Path

import agentic_generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_SOURCE_TEMPLATE_HEAD = (
    "import json\n"
    "from dataclasses import dataclass, field\n"
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
    "    return None\n"
    "\n"
    "\n"
    "def render_prompt_sections(bundle, retry_feedback=None):\n"
    "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
    "\n"
    "\n"
)


def write_generator_stand_in(repo_root, write_log):
    source = (
        GENERATOR_SOURCE_TEMPLATE_HEAD
        + "WRITE_LOG = " + repr(str(write_log)) + "\n"
        + "\n"
        + "\n"
        + "def write_files(component_id, files, repo_root=None):\n"
        + "    with open(WRITE_LOG, 'a', encoding='utf-8') as f:\n"
        + "        f.write(json.dumps([component_id, dict(files), str(repo_root)]) + '\\n')\n"
    )
    path = Path(repo_root) / "gen" / "generator" / "generator.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def write_loop_stand_in(repo_root, script_path, record_path, args_path):
    source = (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "\n"
        "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        "RECORD_PATH = " + repr(str(record_path)) + "\n"
        "ARGS_PATH = " + repr(str(args_path)) + "\n"
        "\n"
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
        "        return {\n"
        "            'text': self.text,\n"
        "            'transcript': self.transcript,\n"
        "            'turns': self.turns,\n"
        "            'tool_calls': self.tool_calls,\n"
        "            'stop': self.stop,\n"
        "            'model_call_error': self.model_call_error,\n"
        "        }\n"
        "\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(ARGS_PATH, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({\n"
        "            'system': system, 'prompt': prompt, 'model': model,\n"
        "            'tools': tools, 'max_turns': max_turns,\n"
        "            'max_tool_calls': max_tool_calls, 'wall_seconds': wall_seconds,\n"
        "            'repo_root': None if repo_root is None else str(repo_root),\n"
        "            'claude_command': claude_command,\n"
        "        }, default=str) + '\\n')\n"
        "    with open(SCRIPT_PATH, encoding='utf-8') as f:\n"
        "        script = json.load(f)\n"
        "    count = 0\n"
        "    transcript = []\n"
        "    for step in script:\n"
        "        name = step['name']\n"
        "        arguments = step['arguments']\n"
        "        text, is_error = execute(name, arguments)\n"
        "        count += 1\n"
        "        transcript.append({'role': 'user', 'content': name})\n"
        "        with open(RECORD_PATH, 'a', encoding='utf-8') as f:\n"
        "            f.write(json.dumps([name, arguments, text, is_error]) + '\\n')\n"
        "    return ToolLoopResult(text='done', transcript=transcript, turns=1,\n"
        "                          tool_calls=count, stop='end_turn',\n"
        "                          model_call_error=None)\n"
    )
    path = Path(repo_root) / "gen" / "llm-tool-endpoint" / "llm_tool_endpoint.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def setup_repo(tmp_path, script):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    script_path = logs / "script.json"
    record_path = logs / "records.jsonl"
    args_path = logs / "loop_args.jsonl"
    write_log = logs / "write_files.jsonl"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    write_generator_stand_in(repo_root, write_log)
    write_loop_stand_in(repo_root, script_path, record_path, args_path)
    return repo_root, record_path


def read_records(record_path):
    lines = Path(record_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def step(name, **arguments):
    return {"name": name, "arguments": arguments}


def bundle():
    return {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }


def test_ac_agent_009_tools_paths_limits_and_truncation(tmp_path):
    script = [
        step("write_file", path="work/pkg/a.py", content="A = 1"),
        step("write_file", path="work/pkg/b.py", content="B = 2"),
        step("list_files", path="work"),
        step("read_file", path="work/pkg"),
        step("write_file", path="scratch/long.txt", content="y" * 9000),
        step("read_file", path="scratch/long.txt"),
    ]
    for i in range(1, 198):
        script.append(step("write_file", path="scratch/f%03d.py" % i, content="x = 0"))
    script += [
        step("write_file", path="scratch/f198.py", content="x = 0"),
        step("write_file", path="work/pkg/a.py", content="A = 2"),
        step("read_file", path="work/pkg/a.py"),
        step("delete_file", path="work/pkg/b.py"),
        step("write_file", path="scratch/f198.py", content="x = 0"),
        step("finish", summary="done"),
    ]
    repo_root, record_path = setup_repo(tmp_path, script)

    agentic_generator.generate_agentic(bundle(), "m", repo_root=repo_root)

    records = read_records(record_path)
    got = [(r[2], bool(r[3])) for r in records]

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

    assert len(got) == len(expected)
    for index, (g, e) in enumerate(zip(got, expected)):
        assert g == e, "mismatch at step " + repr(index) + ": " + repr(g)[:200]
    for r in records:
        assert isinstance(r[3], bool)


def test_ac_agent_009_unisolated_check_import(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")
    script = [
        step("write_file", path="work/widget.py", content="A = 1"),
        step("check_import"),
        step("finish", summary="done"),
    ]
    repo_root, record_path = setup_repo(tmp_path, script)

    result = agentic_generator.generate_agentic(
        bundle(), "m", repo_root=repo_root, allow_unisolated_exec=True
    )

    records = read_records(record_path)
    check = [r for r in records if r[0] == "check_import"]
    assert len(check) == 1
    assert (check[0][2], bool(check[0][3])) == ("0\n", False)
    assert check[0][3] is False
    assert field(result, "isolation") == "unisolated"