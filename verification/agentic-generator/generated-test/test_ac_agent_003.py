# hotdocs-criterion: sha256:d5f66628c9934a9fbb8435c7b746c6688093b20fbb38d4f48a01a73729822c8c
import json
import os
from pathlib import Path

import agentic_generator


GENERATOR_SOURCE = (
    "import json\n"
    "import os\n"
    "from dataclasses import dataclass, field\n"
    "\n"
    "HERE = os.path.dirname(os.path.abspath(__file__))\n"
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
    "def write_files(component_id, files, repo_root=None):\n"
    "    with open(os.path.join(HERE, 'write_files.jsonl'), 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps({'component_id': component_id, 'files': dict(files),\n"
    "                            'repo_root': None if repo_root is None else str(repo_root)}) + '\\n')\n"
)

LOOP_SOURCE = (
    "import json\n"
    "import os\n"
    "from dataclasses import dataclass, field, asdict\n"
    "\n"
    "HERE = os.path.dirname(os.path.abspath(__file__))\n"
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
    "        return asdict(self)\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    with open(os.path.join(HERE, 'loop_args.jsonl'), 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
    "                            'tools': [t.get('name') for t in tools],\n"
    "                            'max_turns': max_turns, 'max_tool_calls': max_tool_calls,\n"
    "                            'wall_seconds': wall_seconds,\n"
    "                            'repo_root': None if repo_root is None else str(repo_root),\n"
    "                            'claude_command': claude_command}) + '\\n')\n"
    "    with open(os.path.join(HERE, 'script.json'), encoding='utf-8') as f:\n"
    "        script = json.load(f)\n"
    "    count = 0\n"
    "    for step in script:\n"
    "        name = step['name']\n"
    "        arguments = step['arguments']\n"
    "        text, is_error = execute(name, arguments)\n"
    "        count += 1\n"
    "        with open(os.path.join(HERE, 'results.jsonl'), 'a', encoding='utf-8') as f:\n"
    "            f.write(json.dumps([name, arguments, text, is_error]) + '\\n')\n"
    "    return ToolLoopResult(text='done', transcript=[], turns=1, tool_calls=count,\n"
    "                          stop='end_turn', model_call_error=None)\n"
)


def _setup(repo_root):
    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(GENERATOR_SOURCE, encoding="utf-8")
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(LOOP_SOURCE, encoding="utf-8")
    return loop_dir


def test_ac_agent_003_tool_results_in_order(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    loop_dir = _setup(repo_root)

    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", str(tmp_path / "no-sandbox-exec"))
    monkeypatch.setattr(agentic_generator, "BWRAP", str(tmp_path / "no-bwrap"))

    script = [
        {"name": "write_file", "arguments": {"path": "work/a.py", "content": "x = 1"}},
        {"name": "read_file", "arguments": {"path": "work/a.py"}},
        {"name": "read_file", "arguments": {"path": "/etc/hosts"}},
        {"name": "read_file", "arguments": {"path": "work/../bundle/01-spec.md"}},
        {"name": "read_file", "arguments": {"path": "secrets/k"}},
        {"name": "write_file", "arguments": {"path": "work/big.py", "content": "a" * 524289}},
        {"name": "delete_file", "arguments": {"path": "work/a.py"}},
        {"name": "read_file", "arguments": {"path": "work/a.py"}},
        {"name": "shell", "arguments": {}},
        {"name": "read_file", "arguments": {}},
        {"name": "finish", "arguments": {"summary": "done"}},
        {"name": "write_file", "arguments": {"path": "work/b.py"}},
    ]
    (loop_dir / "script.json").write_text(json.dumps(script), encoding="utf-8")

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    agentic_generator.generate_agentic(bundle, "anthropic:claude-test", repo_root=repo_root)

    results_path = loop_dir / "results.jsonl"
    assert results_path.is_file(), "loop stand-in never recorded any execute result"
    lines = [ln for ln in results_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    results = [json.loads(ln) for ln in lines]
    assert len(results) == len(script)
    texts = [r[2] for r in results]
    errs = [r[3] for r in results]

    # 1. write
    assert texts[0] == "wrote work/a.py"
    assert errs[0] is False
    # 2. read back
    assert texts[1] == "x = 1"
    assert errs[1] is False
    # 3-5. path rules
    for i in (2, 3, 4):
        assert errs[i] is True, (i, texts[i])
        assert texts[i].startswith("path not allowed:"), (i, texts[i])
    # 6. size limit
    assert errs[5] is True
    assert texts[5].startswith("too large:"), texts[5]
    assert "524288" in texts[5], texts[5]
    # 7. delete
    assert texts[6] == "deleted work/a.py"
    assert errs[6] is False
    # 8. read of deleted file is an error
    assert errs[7] is True
    # 9. unknown tool
    assert errs[8] is True
    assert texts[8].startswith("bad call:"), texts[8]
    # 10. missing argument
    assert errs[9] is True
    assert texts[9].startswith("bad call:"), texts[9]
    # 11. finish
    assert texts[10] == "finished"
    assert errs[10] is False
    # 12. after finish
    assert texts[11] == "already finished"
    assert errs[11] is True