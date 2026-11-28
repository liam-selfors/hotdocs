# hotdocs-criterion: sha256:695c597323135b807bde30d26bb16e3d5b805c80b0432fb745488594ffdef45e
import json
import os
import shutil
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

USING_LINE = "hotdocs: using model claude-cli:sonnet from hotdocs.toml (pass --no-model to skip)"

ROWS = [
    ("gen/component-gate-runner", "component_gate_runner"),
    ("gen/test-author", "test_author"),
    ("gen/spec-linter", "spec_linter"),
    ("gen/spec-scaffolder", "spec_scaffolder"),
    ("gen/spec-completeness-assistant", "spec_completeness_assistant"),
    ("gen/provenance-tracker", "provenance_tracker"),
]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    cache = path.parent / "__pycache__"
    if cache.exists():
        shutil.rmtree(str(cache))
    path.write_text(text)


def _fake_component_source(log_path):
    return (
        "import json\n"
        "\n"
        "def main(argv):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "        f.write(json.dumps(argv) + '\\n')\n"
        "    return 7\n"
    )


def _llm_source(mode):
    head = "def load_config(config_path=None):\n"
    if mode == "config":
        return head + "    return " + repr(CONFIG) + "\n"
    if mode == "none":
        return head + "    return None\n"
    if mode == "raise":
        return head + "    raise ValueError(" + repr("bad") + ")\n"
    raise AssertionError(mode)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    project = tmp_path / "project"
    tool_root = tmp_path / "tool"
    project.mkdir()
    tool_root.mkdir()
    log = project / "calls.log"
    for d, m in ROWS:
        _write(project / d / (m + ".py"), _fake_component_source(log))
    return {"project": project, "tool_root": tool_root, "log": log}


def _set_llm(env, mode):
    _write(
        env["project"] / "gen" / "llm-endpoint" / "llm_endpoint.py",
        _llm_source(mode),
    )


def _run(env, capsys, argv):
    capsys.readouterr()
    if env["log"].exists():
        env["log"].unlink()
    out = []
    code = hotdocs_cli.run(
        list(argv),
        tool_root=str(env["tool_root"]),
        output_fn=lambda *a, **k: out.append(a),
        env=dict(os.environ),
        cwd=str(env["project"]),
    )
    captured = capsys.readouterr()
    lines = [l for l in env["log"].read_text().splitlines() if l.strip()]
    assert len(lines) == 1, lines
    return code, json.loads(lines[0]), captured.err


def _root_token(env):
    return "--repo-root=" + os.path.abspath(str(env["project"]))


def test_required_rows_gain_model_last(env, capsys):
    _set_llm(env, "config")
    root = _root_token(env)
    for argv in (["generate", "comp-x"], ["author-test", "comp-x", "AC-X-1"]):
        code, tokens, err = _run(env, capsys, argv)
        assert code == 7
        assert tokens == argv + [root, "--model=claude-cli:sonnet"]
        assert "using model" not in err


def test_explicit_model_passes_unchanged(env, capsys):
    _set_llm(env, "config")
    root = _root_token(env)
    for argv in (["generate", "comp-x", "--model", "m"], ["generate", "comp-x", "--model=m"]):
        code, tokens, err = _run(env, capsys, argv)
        assert code == 7
        assert tokens == argv + [root]
        assert sum(1 for t in tokens if t == "--model" or t.startswith("--model=")) == 1


def test_none_then_value_error(env, capsys):
    root = _root_token(env)
    _set_llm(env, "none")
    code, tokens, err = _run(env, capsys, ["generate", "comp-x"])
    assert code == 7
    assert tokens == ["generate", "comp-x", root]

    _set_llm(env, "raise")
    code, tokens, err = _run(env, capsys, ["generate", "comp-x"])
    assert code == 7
    assert tokens == ["generate", "comp-x", root]
    assert "bad" in err.splitlines()


def test_no_rows_never_gain_model(env, capsys):
    _set_llm(env, "config")
    for argv in (["lint"], ["decision", "new", "x"]):
        code, tokens, err = _run(env, capsys, argv)
        assert code == 7
        assert not any(t == "--model" or t.startswith("--model=") for t in tokens)
        assert "using model" not in err


def test_optional_rows_gain_model_and_print_line(env, capsys):
    _set_llm(env, "config")
    root = _root_token(env)
    for argv in (["assist", "--changed=R-X-1"], ["verify"]):
        code, tokens, err = _run(env, capsys, argv)
        assert code == 7
        assert tokens[-2:] == [root, "--model=claude-cli:sonnet"]
        assert err.splitlines().count(USING_LINE) == 1
    # exact forwarded tokens given each row's strip
    code, tokens, err = _run(env, capsys, ["assist", "--changed=R-X-1"])
    assert tokens == ["--changed=R-X-1", root, "--model=claude-cli:sonnet"]
    code, tokens, err = _run(env, capsys, ["verify"])
    assert tokens == ["verify", root, "--model=claude-cli:sonnet"]


def test_no_model_removed_for_model_rows(env, capsys):
    _set_llm(env, "config")
    root = _root_token(env)
    code, tokens, err = _run(env, capsys, ["assist", "--changed=R-X-1", "--no-model"])
    assert code == 7
    assert tokens == ["--changed=R-X-1", root]
    assert "using model" not in err

    code, tokens, err = _run(env, capsys, ["generate", "comp-x", "--no-model"])
    assert code == 7
    assert tokens == ["generate", "comp-x", root]
    assert "using model" not in err


def test_no_model_forwarded_for_no_row(env, capsys):
    _set_llm(env, "config")
    root = _root_token(env)
    code, tokens, err = _run(env, capsys, ["lint", "--no-model"])
    assert code == 7
    assert tokens == ["--no-model", root]