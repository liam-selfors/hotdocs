"""Hand suite: model-run code and model-chosen paths cannot leave the
agent sandbox (`D309`, specs/architecture/agent-sandbox.md).

Each test plants a scripted llm-tool-endpoint stand-in under a fresh
repo_root, so the real tools of the candidate run exactly as a model's
calls would drive them; generator comes from this tree's own gen/.
macOS only: the OS sandbox under test is sandbox-exec.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "agentic-generator"))
import agentic_generator  # noqa: E402

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").exists(),
    reason="sandbox-exec is the OS sandbox under test",
)

STAND_IN = '''
import json
from types import SimpleNamespace

def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,
                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,
                  claude_command="claude"):
    script = json.load(open({script!r}))
    log = []
    for name, arguments in script:
        text, is_error = execute(name, arguments)
        log.append([name, arguments, text, is_error])
    json.dump(log, open({log!r}, "w"))
    return SimpleNamespace(text="", transcript=[], turns=1, tool_calls=len(log),
                           stop="end_turn", model_call_error=None)
'''


def _run(tmp_path, script):
    repo = tmp_path / "repo"
    (repo / "specs").mkdir(parents=True)
    (repo / "specs" / "secret.md").write_text("REPO-CANARY\n")
    stand_in = repo / "gen" / "llm-tool-endpoint" / "llm_tool_endpoint.py"
    stand_in.parent.mkdir(parents=True)
    script_path, log_path = tmp_path / "script.json", tmp_path / "log.json"
    script_path.write_text(json.dumps(script))
    stand_in.write_text(STAND_IN.format(script=str(script_path), log=str(log_path)))
    for dep in ("generator", "cache-manager", "llm-endpoint"):
        src = REPO_ROOT / "gen" / dep
        if src.is_dir():
            shutil.copytree(src, repo / "gen" / dep, ignore=shutil.ignore_patterns("__pycache__"))
    bundle = {"component_id": "comp-widget", "spec_bundle_hash": "sha256:x", "hint_code": None,
              "spec": "S", "interface": "I", "constraints": "C", "glossary": "G",
              "dependency_interfaces": {}, "dependency_usage": {}, "dependency_context": {}, "vars": {}}
    result = agentic_generator.generate_agentic(bundle, "m", repo_root=repo)
    return repo, json.loads(log_path.read_text()), result


def _scratch(test_body):
    return ["write_file", {"path": "scratch/test_escape.py", "content": test_body}]


def test_model_code_cannot_read_write_or_reach_the_network(tmp_path):
    repo = (tmp_path / "repo").resolve()
    body = f'''
import os, socket, pytest

def test_no_repo_read():
    with pytest.raises(OSError):
        open({str(repo / "specs" / "secret.md")!r}).read()

def test_no_outside_write():
    with pytest.raises(OSError):
        open({str(repo / "escaped.txt")!r}, "w").write("x")

def test_no_network():
    with pytest.raises(OSError):
        socket.create_connection(("1.1.1.1", 80), timeout=3)

def test_no_credentials():
    assert not [k for k in os.environ if "KEY" in k or "TOKEN" in k or "SECRET" in k]
'''
    _, log, result = _run(tmp_path, [
        ["write_file", {"path": "work/widget.py", "content": "X = 1\n"}],
        _scratch(body),
        ["run_scratch_tests", {}],
        ["finish", {"summary": "s"}],
    ])
    run_text = log[2][2]
    assert run_text.startswith("0\n"), run_text
    assert result.isolation == "sandbox-exec"
    assert not (repo / "escaped.txt").exists()


def test_a_symlink_made_by_model_code_is_never_followed(tmp_path):
    repo = (tmp_path / "repo").resolve()
    body = f'''
import os

def test_make_link():
    os.symlink({str(repo / "specs" / "secret.md")!r}, "work/link.md")
'''
    _, log, _ = _run(tmp_path, [
        _scratch(body),
        ["run_scratch_tests", {}],
        ["read_file", {"path": "work/link.md"}],
        ["finish", {"summary": "s"}],
    ])
    text, is_error = log[2][2], log[2][3]
    assert is_error and text.startswith("path not allowed:")
    assert "REPO-CANARY" not in json.dumps(log)


@pytest.mark.parametrize("path", [
    "../repo/specs/secret.md", "work/../../repo/specs/secret.md", "/etc/hosts", "specs/secret.md",
])
def test_traversal_paths_are_refused(tmp_path, path):
    _, log, _ = _run(tmp_path, [["read_file", {"path": path}], ["finish", {"summary": "s"}]])
    assert log[0][3] and log[0][2].startswith("path not allowed:")


def test_the_sandbox_is_removed(tmp_path):
    import tempfile
    before = {p.name for p in Path(tempfile.gettempdir()).iterdir() if p.name.startswith("hotdocs-agent-")}
    _run(tmp_path, [["write_file", {"path": "work/widget.py", "content": "X = 1\n"}], ["finish", {"summary": "s"}]])
    after = {p.name for p in Path(tempfile.gettempdir()).iterdir() if p.name.startswith("hotdocs-agent-")}
    assert after <= before
