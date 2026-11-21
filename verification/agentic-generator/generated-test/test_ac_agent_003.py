# hotdocs-criterion: sha256:6ccbf440218276100699c285085abecbfb8d4b3385c244bb30b0ba3cc3aa4644
import json
from pathlib import Path

import agentic_generator


GENERATOR_SOURCE_TEMPLATE = '''
import dataclasses
import json
from dataclasses import dataclass, field

LOG_PATH = __LOG__


def _log(entry):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\\n")


@dataclass
class GenerationResult:
    component_id: str = ""
    spec_bundle_hash: str = ""
    model: str = ""
    prompt_version: str = ""
    cache_hit: bool = False
    files: dict = field(default_factory=dict)
    model_call_error: object = None
    refused: object = None
    retry_feedback: object = None
    mode: str = "single"
    transcript_sha256: object = None
    turns: int = 1
    tool_calls: int = 0
    isolation: object = None


def check_write_allowed(bundle, repo_root=None):
    return None


def render_prompt_sections(bundle, retry_feedback=None):
    return [("Spec", "SPEC TEXT"), ("Component interface", "IFACE TEXT")]


def write_files(component_id, files, repo_root=None):
    _log({"call": "write_files", "component_id": component_id, "files": files})


def check_assets(component_id, files, repo_root=None):
    _log({"call": "check_assets", "component_id": component_id, "files": files})
    for content in files.values():
        if "bad" in content:
            return ("malformed_layout", ["static/app.txt: bad"])
    return (None, [])


def check_asset_environment(component_id, repo_root=None):
    import pathlib
    if repo_root is not None and (pathlib.Path(repo_root) / "NO_ENV").exists():
        return ("environment", ["fake needs fakeprog >= 2"])
    return (None, [])
'''


LOOP_SOURCE_TEMPLATE = '''
import json
from dataclasses import dataclass, field

SCRIPT_PATH = __SCRIPT__
ARGS_LOG = __ARGS__
RESULTS_LOG = __RESULTS__


@dataclass
class ToolLoopResult:
    text: str = ""
    transcript: list = field(default_factory=list)
    turns: int = 0
    tool_calls: int = 0
    stop: str = "end_turn"
    model_call_error: object = None

    def to_dict(self):
        return {
            "text": self.text,
            "transcript": self.transcript,
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "stop": self.stop,
            "model_call_error": self.model_call_error,
        }


def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,
                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,
                  claude_command="claude"):
    with open(ARGS_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "system": system, "prompt": prompt, "model": model,
            "tools": tools, "max_turns": max_turns,
            "max_tool_calls": max_tool_calls, "wall_seconds": wall_seconds,
            "repo_root": repo_root, "claude_command": claude_command,
        }, default=str) + "\\n")
    with open(SCRIPT_PATH, "r", encoding="utf-8") as fh:
        script = json.load(fh)
    count = 0
    for step in script:
        name = step["name"]
        arguments = step["arguments"]
        count += 1
        text, is_error = execute(name, arguments)
        with open(RESULTS_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps([name, arguments, text, is_error]) + "\\n")
    return ToolLoopResult(text="done", transcript=[], turns=1,
                          tool_calls=count, stop="end_turn",
                          model_call_error=None)
'''


def _write_stand_ins(repo_root, script):
    logs = repo_root / "logs"
    logs.mkdir()
    gen_log = logs / "generator.log"
    args_log = logs / "loop_args.log"
    results_log = logs / "loop_results.log"
    script_path = logs / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")

    gen_dir = repo_root / "gen" / "generator"
    gen_dir.mkdir(parents=True)
    gen_src = GENERATOR_SOURCE_TEMPLATE.replace("__LOG__", repr(str(gen_log)))
    (gen_dir / "generator.py").write_text(gen_src, encoding="utf-8")

    loop_dir = repo_root / "gen" / "llm-tool-endpoint"
    loop_dir.mkdir(parents=True)
    loop_src = (
        LOOP_SOURCE_TEMPLATE
        .replace("__SCRIPT__", repr(str(script_path)))
        .replace("__ARGS__", repr(str(args_log)))
        .replace("__RESULTS__", repr(str(results_log)))
    )
    (loop_dir / "llm_tool_endpoint.py").write_text(loop_src, encoding="utf-8")
    return results_log


def _read_results(results_log):
    lines = results_log.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_ac_agent_003_tool_results_in_order(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
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
    results_log = _write_stand_ins(repo_root, script)

    missing = str(tmp_path / "does-not-exist-sandbox")
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", missing)
    monkeypatch.setattr(agentic_generator, "BWRAP", missing)

    bundle = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "hint_code": None,
    }
    agentic_generator.generate_agentic(
        bundle, "anthropic:claude-sonnet-5", repo_root=repo_root
    )

    results = _read_results(results_log)
    assert len(results) == 12, results
    texts = [r[2] for r in results]
    errors = [r[3] for r in results]

    assert (texts[0], errors[0]) == ("wrote work/a.py", False)
    assert (texts[1], errors[1]) == ("x = 1", False)
    for i in (2, 3, 4):
        assert errors[i] is True, (i, texts[i])
        assert texts[i].startswith("path not allowed:"), (i, texts[i])
    assert errors[5] is True, texts[5]
    assert "524288" in texts[5], texts[5]
    assert (texts[6], errors[6]) == ("deleted work/a.py", False)
    assert errors[7] is True, texts[7]
    for i in (8, 9):
        assert errors[i] is True, (i, texts[i])
        assert texts[i].startswith("bad call:"), (i, texts[i])
    assert (texts[10], errors[10]) == ("finished", False)
    assert (texts[11], errors[11]) == ("already finished", True)