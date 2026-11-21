# hotdocs-criterion: sha256:de620746ab7863a2aea25d4d7826a55ffcca6699d2fdf1649106beadd8be85d7
import json
import os
from pathlib import Path

import agentic_generator


GENERATOR_SOURCE = (
    "import json\n"
    "import os\n"
    "from dataclasses import dataclass, field\n"
    "\n"
    "_HERE = os.path.dirname(os.path.abspath(__file__))\n"
    "\n"
    "\n"
    "def _log(name, payload):\n"
    "    with open(os.path.join(_HERE, name), 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(payload, default=str) + '\\n')\n"
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
    "    _log('write_files.log', {'component_id': component_id, 'files': files,\n"
    "                             'repo_root': repo_root})\n"
    "\n"
    "\n"
    "def check_assets(component_id, files, repo_root=None):\n"
    "    _log('check_assets.log', {'component_id': component_id, 'files': files,\n"
    "                              'repo_root': repo_root})\n"
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


LOOP_SOURCE = (
    "import json\n"
    "import os\n"
    "\n"
    "_HERE = os.path.dirname(os.path.abspath(__file__))\n"
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
    "        return {'text': self.text, 'transcript': self.transcript,\n"
    "                'turns': self.turns, 'tool_calls': self.tool_calls,\n"
    "                'stop': self.stop, 'model_call_error': self.model_call_error}\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    with open(os.path.join(_HERE, 'args.log'), 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
    "                             'tools': tools, 'max_turns': max_turns,\n"
    "                             'max_tool_calls': max_tool_calls,\n"
    "                             'wall_seconds': wall_seconds,\n"
    "                             'repo_root': repo_root,\n"
    "                             'claude_command': claude_command}, default=str) + '\\n')\n"
    "    with open(os.path.join(_HERE, 'script.json'), encoding='utf-8') as fh:\n"
    "        script = json.load(fh)\n"
    "    count = 0\n"
    "    for step in script:\n"
    "        name = step['name']\n"
    "        arguments = step['arguments']\n"
    "        text, is_error = execute(name, arguments)\n"
    "        count += 1\n"
    "        with open(os.path.join(_HERE, 'results.log'), 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps({'name': name, 'arguments': {k: (v if not isinstance(v, str) or len(v) < 100 else '<long>') for k, v in arguments.items()},\n"
    "                                 'text': text, 'is_error': is_error}) + '\\n')\n"
    "    return _Result('Done.', [{'role': 'user', 'content': prompt}], 1, count,\n"
    "                   'end_turn', None)\n"
)


def _script():
    return [
        {"name": "write_file", "arguments": {"path": "work/a.py", "content": "x = 1"}},
        {"name": "read_file", "arguments": {"path": "work/a.py"}},
        {"name": "read_file", "arguments": {"path": "/etc/hosts"}},
        {"name": "read_file", "arguments": {"path": "work/../bundle/01-spec.md"}},
        {"name": "read_file", "arguments": {"path": "secrets/k"}},
        {"name": "write_file", "arguments": {"path": "work/big.py", "content": "a" * 524289}},
        {"name": "delete_file", "arguments": {"path": "work/a.py"}},
        {"name": "read_file", "arguments": {"path": "work/a.py"}},
        {"name": "shell", "arguments": {"command": "ls"}},
        {"name": "read_file", "arguments": {}},
        {"name": "finish", "arguments": {"summary": "done"}},
        {"name": "write_file", "arguments": {"path": "work/b.py"}},
    ]


def test_ac_agent_003_tool_results_in_order(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    gen_dir = repo_root / "gen" / "generator"
    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    gen_dir.mkdir(parents=True)
    loop_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(GENERATOR_SOURCE, encoding="utf-8")
    (loop_dir / "llm_tool_endpoint.py").write_text(LOOP_SOURCE, encoding="utf-8")
    (loop_dir / "script.json").write_text(json.dumps(_script()), encoding="utf-8")

    missing = str(tmp_path / "no-such-sandbox-binary")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    agentic_generator.generate_agentic(
        bundle, "anthropic:claude-sonnet-5", None, repo_root=repo_root
    )

    results_path = loop_dir / "results.log"
    assert results_path.exists(), "loop stand-in never recorded any results"
    results = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(results) == 12, results

    texts = [r["text"] for r in results]
    errors = [r["is_error"] for r in results]

    # 1. write_file work/a.py
    assert texts[0] == "wrote work/a.py"
    assert errors[0] is False
    # 2. read_file work/a.py
    assert texts[1] == "x = 1"
    assert errors[1] is False
    # 3-5. path rules
    for i in (2, 3, 4):
        assert errors[i] is True, (i, results[i])
        assert texts[i].startswith("path not allowed:"), (i, texts[i])
    # 6. size limit
    assert errors[5] is True
    assert "524288" in texts[5], texts[5]
    # 7. delete
    assert texts[6] == "deleted work/a.py"
    assert errors[6] is False
    # 8. read of deleted file
    assert errors[7] is True, results[7]
    # 9. unknown tool
    assert errors[8] is True
    assert texts[8].startswith("bad call:"), texts[8]
    # 10. missing path
    assert errors[9] is True
    assert texts[9].startswith("bad call:"), texts[9]
    # 11. finish
    assert texts[10] == "finished"
    assert errors[10] is False
    # 12. after finish
    assert texts[11] == "already finished"
    assert errors[11] is True