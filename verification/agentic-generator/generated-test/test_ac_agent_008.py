# hotdocs-criterion: sha256:32a1936e89a99ec0bdba879d18c76c5f379abf7c180b6fcd0bdfaf32d49d5652
import json
import os
from pathlib import Path

import agentic_generator


CANARY = "CANARY-7f3a"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATOR_BODY = (
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
    "def write_files(component_id, files, repo_root=None):\n"
    "    with open(WRITE_LOG, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps({'component_id': component_id, 'files': files,\n"
    "                            'repo_root': str(repo_root)}) + '\\n')\n"
)


LOOP_BODY = (
    "import json\n"
    "from dataclasses import dataclass, field\n"
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
    "        return {'text': self.text, 'transcript': self.transcript,\n"
    "                'turns': self.turns, 'tool_calls': self.tool_calls,\n"
    "                'stop': self.stop, 'model_call_error': self.model_call_error}\n"
    "\n"
    "\n"
    "def _call(execute, name, arguments):\n"
    "    out = execute(name, arguments)\n"
    "    text, is_error = out[0], out[1]\n"
    "    with open(RESULTS_PATH, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps([name, arguments, text, bool(is_error)]) + '\\n')\n"
    "    return text, is_error\n"
    "\n"
    "\n"
    "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
    "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
    "                  claude_command='claude'):\n"
    "    with open(ARGS_PATH, 'w', encoding='utf-8') as f:\n"
    "        json.dump({'system': system, 'prompt': prompt, 'model': model,\n"
    "                   'tools': tools, 'max_turns': max_turns,\n"
    "                   'max_tool_calls': max_tool_calls,\n"
    "                   'wall_seconds': wall_seconds,\n"
    "                   'repo_root': str(repo_root),\n"
    "                   'claude_command': claude_command}, f, default=str)\n"
    "    with open(SCRIPT_PATH, encoding='utf-8') as f:\n"
    "        script = json.load(f)\n"
    "    calls = 0\n"
    "    for step in script:\n"
    "        text, is_error = _call(execute, step['name'], step['arguments'])\n"
    "        calls += 1\n"
    "        if step.get('read_listed') and not is_error:\n"
    "            for line in text.split('\\n'):\n"
    "                if line:\n"
    "                    _call(execute, 'read_file', {'path': line})\n"
    "                    calls += 1\n"
    "    return ToolLoopResult(text='done',\n"
    "                          transcript=[{'role': 'user', 'content': prompt}],\n"
    "                          turns=1, tool_calls=calls, stop='end_turn',\n"
    "                          model_call_error=None)\n"
)


def _build(tmp_path):
    repo_root = tmp_path / "repo"
    acc = repo_root / "specs" / "components" / "widget" / "acceptance"
    acc.mkdir(parents=True)
    (acc / "AC-W-1.md").write_text(
        "# AC-W-1\n\nCovers: R-W-1\n\nSecret criterion text " + CANARY + "\n",
        encoding="utf-8",
    )
    ver = repo_root / "verification" / "widget"
    ver.mkdir(parents=True)
    (ver / "test_w.py").write_text(
        "# " + CANARY + "\ndef test_w():\n    assert True\n", encoding="utf-8"
    )

    records = tmp_path / "records"
    records.mkdir()
    args_path = records / "loop_args.json"
    results_path = records / "loop_results.jsonl"
    script_path = records / "script.json"
    write_log = records / "write_files.log"

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    (gen_dir / "generator.py").write_text(
        "WRITE_LOG = " + repr(str(write_log)) + "\n" + GENERATOR_BODY,
        encoding="utf-8",
    )

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    (loop_dir / "llm_tool_endpoint.py").write_text(
        "ARGS_PATH = " + repr(str(args_path)) + "\n"
        + "RESULTS_PATH = " + repr(str(results_path)) + "\n"
        + "SCRIPT_PATH = " + repr(str(script_path)) + "\n"
        + LOOP_BODY,
        encoding="utf-8",
    )

    abs_acc = str(repo_root / "specs" / "components" / "widget" / "acceptance" / "AC-W-1.md")
    script = [
        {"name": "list_files", "arguments": {"path": "bundle"}, "read_listed": True},
        {"name": "list_files", "arguments": {"path": "work"}, "read_listed": True},
        {"name": "list_files", "arguments": {"path": "scratch"}, "read_listed": True},
        {"name": "read_file",
         "arguments": {"path": "../specs/components/widget/acceptance/AC-W-1.md"}},
        {"name": "read_file",
         "arguments": {"path": "bundle/../../verification/widget/test_w.py"}},
        {"name": "read_file", "arguments": {"path": abs_acc}},
        {"name": "finish", "arguments": {"summary": "done"}},
    ]
    script_path.write_text(json.dumps(script), encoding="utf-8")
    return repo_root, args_path, results_path, len(script)


def test_ac_agent_008_no_repository_text_leaks(tmp_path, monkeypatch):
    missing = str(tmp_path / "does-not-exist" / "sandbox")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)

    repo_root, args_path, results_path, n_steps = _build(tmp_path)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }

    agentic_generator.generate_agentic(bundle, "m", repo_root=repo_root)

    # The loop stand-in ran and recorded what it received.
    assert args_path.is_file(), "loop stand-in was never called"
    received = json.loads(args_path.read_text(encoding="utf-8"))
    assert isinstance(received["system"], str)
    assert isinstance(received["prompt"], str)
    assert CANARY not in received["system"]
    assert CANARY not in received["prompt"]

    assert results_path.is_file(), "no tool results were recorded"
    lines = [l for l in results_path.read_text(encoding="utf-8").splitlines() if l]
    results = [json.loads(l) for l in lines]
    assert len(results) >= n_steps

    names = [r[0] for r in results]
    assert "list_files" in names
    assert "finish" in names

    for name, arguments, text, is_error in results:
        assert isinstance(text, str)
        assert CANARY not in text, (
            "repository text leaked through " + repr(name) + " " + repr(arguments)
        )

    # The bundle listing worked, so files were actually read through the tool.
    bundle_listing = results[0]
    assert bundle_listing[0] == "list_files"
    assert bundle_listing[3] is False
    assert any(
        r[0] == "read_file" and r[1].get("path", "").startswith("bundle/")
        for r in results
    )