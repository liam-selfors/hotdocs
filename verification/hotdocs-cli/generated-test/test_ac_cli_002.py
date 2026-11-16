import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


FAKE_LINT_TEMPLATE = '''\
import json
import os

CALLS_LOG = {calls_log!r}
ENV_LOG = {env_log!r}


def main(argv):
    with open(CALLS_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(argv) + "\\n")
    with open(ENV_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(os.environ.get("VAR_HOTDOCS_CONFIG")) + "\\n")
    return 7
'''


LLM_ENDPOINT_STANDIN = '''\
class ModelResolutionError(Exception):
    pass


def load_config(config_path=None):
    return None
'''


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_project(base):
    project = base / "project"
    project.mkdir(parents=True)
    calls_log = project / "calls.log"
    env_log = project / "env.log"
    _write(
        project / "gen" / "spec-linter" / "spec_linter.py",
        FAKE_LINT_TEMPLATE.format(calls_log=str(calls_log), env_log=str(env_log)),
    )
    _write(project / "gen" / "llm-endpoint" / "llm_endpoint.py", LLM_ENDPOINT_STANDIN)
    return project


def _make_tool_root(base):
    tool_root = base / "toolroot"
    tool_root.mkdir(parents=True)
    _write(tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py", LLM_ENDPOINT_STANDIN)
    return tool_root


def _read_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _same_path(a, b):
    return os.path.realpath(str(a)) == os.path.realpath(str(b))


def test_repo_root_appended_when_absent(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    tool_root = _make_tool_root(tmp_path)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(project)

    code = hotdocs_cli.main(["lint", "a.md"], tool_root=tool_root)

    assert code == 7
    calls = _read_lines(project / "calls.log")
    assert len(calls) == 1
    received = calls[0]
    assert len(received) == 2
    assert received[0] == "a.md"
    token = received[1]
    assert token.startswith("--repo-root=")
    value = token[len("--repo-root="):]
    assert os.path.isabs(value)
    assert _same_path(value, project)


def test_repo_root_present_forwarded_unchanged(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    tool_root = _make_tool_root(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(elsewhere)

    first = ["lint", "--repo-root", str(project), "a.md"]
    second = ["lint", "--repo-root=" + str(project)]

    code1 = hotdocs_cli.main(list(first), tool_root=tool_root)
    code2 = hotdocs_cli.main(list(second), tool_root=tool_root)

    assert code1 == 7
    assert code2 == 7
    calls = _read_lines(project / "calls.log")
    assert calls == [first[1:], second[1:]]
    for received in calls:
        count = sum(
            1 for t in received if t == "--repo-root" or t.startswith("--repo-root=")
        )
        assert count == 1


def test_config_variable_set_during_run_and_restored(tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    tool_root = _make_tool_root(tmp_path)
    (project / "hotdocs.toml").write_text(
        '[llm]\nprovider = "ollama"\nmodel = "llama3.2"\n', encoding="utf-8"
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    argv = ["lint", "--repo-root", str(project)]

    # Variable unset: set to <project>/hotdocs.toml during the run, then restored.
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    code1 = hotdocs_cli.main(list(argv), tool_root=tool_root)
    assert code1 == 7
    assert "VAR_HOTDOCS_CONFIG" not in os.environ

    # Variable set to "/x": left as is.
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", "/x")
    code2 = hotdocs_cli.main(list(argv), tool_root=tool_root)
    assert code2 == 7
    assert os.environ.get("VAR_HOTDOCS_CONFIG") == "/x"

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    assert "VAR_HOTDOCS_CONFIG" not in os.environ

    seen = _read_lines(project / "env.log")
    assert len(seen) == 2
    assert seen[0] is not None
    assert Path(seen[0]).name == "hotdocs.toml"
    assert _same_path(seen[0], project / "hotdocs.toml")
    assert seen[1] == "/x"

    calls = _read_lines(project / "calls.log")
    assert calls == [argv[1:], argv[1:]]