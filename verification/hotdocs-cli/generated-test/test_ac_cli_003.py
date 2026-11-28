# hotdocs-criterion: sha256:2827d4a24a92450ad33ca6f343ef7d1009b0a93f026998d691d08adfba018557
"""AC-CLI-003: model injection into forwarded tokens (R-CLI-003)."""

import json
import os
import sys

import pytest

import hotdocs_cli


CONFIG = {
    "provider": "claude-cli",
    "model": "sonnet",
    "base_url": None,
    "api_key_env": None,
    "timeout_seconds": None,
    "auth": None,
}

USING_LINE = (
    "hotdocs: using model claude-cli:sonnet from hotdocs.toml "
    "(pass --no-model to skip)"
)

# verb rows used here: (dir, module, strip)
ROWS = {
    "generate": ("gen/component-gate-runner", "component_gate_runner", 0),
    "author-test": ("gen/test-author", "test_author", 1),
    "lint": ("gen/spec-linter", "spec_linter", 1),
    "decision new": ("gen/spec-scaffolder", "spec_scaffolder", 0),
    "assist": ("gen/spec-completeness-assistant", "spec_completeness_assistant", 1),
    "verify": ("gen/provenance-tracker", "provenance_tracker", 0),
}


@pytest.fixture(autouse=True)
def _no_bytecode(monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)


def write_fake_component(project, row):
    dir_, module, _strip = ROWS[row]
    directory = project / dir_
    directory.mkdir(parents=True, exist_ok=True)
    log_path = str(project / "calls.log")
    source = (
        "import json\n"
        "\n"
        "LOG = " + repr(log_path) + "\n"
        "\n"
        "\n"
        "def main(argv):\n"
        "    with open(LOG, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(argv) + '\\n')\n"
        "    return 7\n"
    )
    (directory / (module + ".py")).write_text(source, encoding="utf-8")


def write_fake_llm(project, body):
    directory = project / "gen" / "llm-endpoint"
    directory.mkdir(parents=True, exist_ok=True)
    source = (
        "def load_config(config_path=None):\n"
        "    " + body + "\n"
    )
    (directory / "llm_endpoint.py").write_text(source, encoding="utf-8")


def llm_returns_config(project):
    write_fake_llm(project, "return " + repr(CONFIG))


def llm_returns_none(project):
    write_fake_llm(project, "return None")


def llm_raises_bad(project):
    write_fake_llm(project, "raise ValueError(" + repr("bad") + ")")


def read_calls(project):
    log = project / "calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_project(tmp_path, name, rows):
    project = tmp_path / name
    project.mkdir()
    for row in rows:
        write_fake_component(project, row)
    return project


def invoke(project, tool_root, argv, capsys):
    """Run once; return (forwarded tokens, stderr text)."""
    capsys.readouterr()
    before = len(read_calls(project))
    sink = []
    code = hotdocs_cli.run(
        list(argv),
        tool_root=str(tool_root),
        output_fn=lambda *a, **k: sink.append(a),
        env=dict(os.environ),
        cwd=str(project),
    )
    err = capsys.readouterr().err
    calls = read_calls(project)
    assert len(calls) == before + 1, "fake component did not run exactly once"
    assert code == 7
    return calls[-1], err


@pytest.fixture
def tool_root(tmp_path):
    root = tmp_path / "tool-root"
    root.mkdir()
    return root


def repo_root_token(project):
    return "--repo-root=" + os.path.abspath(str(project))


def test_required_rows_gain_model_last(tmp_path, tool_root, capsys):
    project = make_project(tmp_path, "p1", ["generate", "author-test"])
    llm_returns_config(project)
    rr = repo_root_token(project)

    tokens, _ = invoke(project, tool_root, ["generate", "comp-x"], capsys)
    assert tokens == ["generate", "comp-x", rr, "--model=claude-cli:sonnet"]

    tokens, _ = invoke(project, tool_root, ["author-test", "comp-x", "AC-X-1"], capsys)
    assert tokens == ["comp-x", "AC-X-1", rr, "--model=claude-cli:sonnet"]


def test_explicit_model_passes_unchanged(tmp_path, tool_root, capsys):
    project = make_project(tmp_path, "p2", ["generate"])
    llm_returns_config(project)
    rr = repo_root_token(project)

    tokens, _ = invoke(project, tool_root, ["generate", "comp-x", "--model", "m"], capsys)
    assert tokens == ["generate", "comp-x", "--model", "m", rr]

    tokens, _ = invoke(project, tool_root, ["generate", "comp-x", "--model=m"], capsys)
    assert tokens == ["generate", "comp-x", "--model=m", rr]


def test_none_then_value_error_injects_nothing(tmp_path, tool_root, capsys):
    project = make_project(tmp_path, "p3", ["generate"])
    rr = repo_root_token(project)

    llm_returns_none(project)
    tokens, _ = invoke(project, tool_root, ["generate", "comp-x"], capsys)
    assert tokens == ["generate", "comp-x", rr]

    llm_raises_bad(project)
    tokens, err = invoke(project, tool_root, ["generate", "comp-x"], capsys)
    assert tokens == ["generate", "comp-x", rr]
    assert "bad" in err.splitlines()


def test_no_rows_never_gain_model(tmp_path, tool_root, capsys):
    project = make_project(tmp_path, "p4", ["lint", "decision new"])
    llm_returns_config(project)

    for argv in (["lint"], ["decision", "new", "x"]):
        tokens, err = invoke(project, tool_root, argv, capsys)
        assert not any(t == "--model" or t.startswith("--model=") for t in tokens)
        assert not any("using model" in line for line in err.splitlines())


def test_optional_rows_gain_model_and_print_notice(tmp_path, tool_root, capsys):
    project = make_project(tmp_path, "p5", ["assist", "verify"])
    llm_returns_config(project)
    rr = repo_root_token(project)

    tokens, err = invoke(project, tool_root, ["assist", "--changed=R-X-1"], capsys)
    assert tokens[-2:] == [rr, "--model=claude-cli:sonnet"]
    assert err.splitlines().count(USING_LINE) == 1

    tokens, err = invoke(project, tool_root, ["verify"], capsys)
    assert tokens[-2:] == [rr, "--model=claude-cli:sonnet"]
    assert err.splitlines().count(USING_LINE) == 1


def test_no_model_removed_for_model_rows(tmp_path, tool_root, capsys):
    project = make_project(tmp_path, "p6", ["assist", "generate"])
    llm_returns_config(project)
    rr = repo_root_token(project)

    tokens, _ = invoke(project, tool_root, ["assist", "--changed=R-X-1", "--no-model"], capsys)
    assert tokens == ["--changed=R-X-1", rr]

    tokens, _ = invoke(project, tool_root, ["generate", "comp-x", "--no-model"], capsys)
    assert tokens == ["generate", "comp-x", rr]


def test_no_model_forwarded_for_no_row(tmp_path, tool_root, capsys):
    project = make_project(tmp_path, "p7", ["lint"])
    llm_returns_config(project)
    rr = repo_root_token(project)

    tokens, _ = invoke(project, tool_root, ["lint", "--no-model"], capsys)
    assert tokens == ["--no-model", rr]