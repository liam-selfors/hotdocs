# hotdocs-criterion: sha256:51eeaaddf2143de058b0c8b4d0180038ee94f4b4b4a84c8f82c8c7403238efc8
import json
import os
import shutil
import sys

import pytest

import hotdocs_cli


COMPONENTS = [
    ("gen/component-gate-runner", "component_gate_runner"),
    ("gen/test-author", "test_author"),
    ("gen/spec-linter", "spec_linter"),
    ("gen/spec-scaffolder", "spec_scaffolder"),
    ("gen/spec-completeness-assistant", "spec_completeness_assistant"),
    ("gen/provenance-tracker", "provenance_tracker"),
]

CONFIG = {
    "provider": "claude-cli",
    "model": "sonnet",
    "base_url": None,
    "api_key_env": None,
    "timeout_seconds": None,
    "auth": None,
}

USING_LINE = "hotdocs: using model claude-cli:sonnet from hotdocs.toml (pass --no-model to skip)"


def _fake_component_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def main(argv=None):\n"
        "    with open(LOG, 'a') as handle:\n"
        "        handle.write(json.dumps(list(argv) if argv is not None else None) + '\\n')\n"
        "    return 7\n"
    )


def _write_llm_endpoint(project, mode):
    directory = project / "gen" / "llm-endpoint"
    directory.mkdir(parents=True, exist_ok=True)
    cache = directory / "__pycache__"
    if cache.exists():
        shutil.rmtree(cache)
    source = (
        "MODE = " + repr(mode) + "\n"
        "CONFIG = " + repr(CONFIG) + "\n"
        "def load_config(config_path=None):\n"
        "    if MODE == 'none':\n"
        "        return None\n"
        "    if MODE == 'error':\n"
        "        raise ValueError(" + repr("bad") + ")\n"
        "    return dict(CONFIG)\n"
    )
    (directory / "llm_endpoint.py").write_text(source)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log_path = project / "calls.log"
    for directory, module in COMPONENTS:
        target = project / directory
        target.mkdir(parents=True, exist_ok=True)
        (target / (module + ".py")).write_text(_fake_component_source(log_path))
    _write_llm_endpoint(project, "config")
    return project, tool_root, log_path


def _invoke(env, argv, capsys):
    project, tool_root, log_path = env
    capsys.readouterr()
    before = log_path.read_text().splitlines() if log_path.exists() else []
    outputs = []
    rc = hotdocs_cli.run(
        list(argv),
        tool_root=str(tool_root),
        output_fn=lambda *a, **k: outputs.append(a),
        env=dict(os.environ),
        cwd=str(project),
    )
    captured = capsys.readouterr()
    after = log_path.read_text().splitlines() if log_path.exists() else []
    new = after[len(before):]
    assert len(new) == 1, "expected exactly one fake call, got " + repr(new)
    return rc, json.loads(new[0]), captured.err


def _root(project):
    return "--repo-root=" + os.path.abspath(str(project))


def _using_count(err):
    return sum(1 for line in err.splitlines() if line.strip() == USING_LINE)


def test_required_rows_gain_model_last(env, capsys):
    project = env[0]
    root = _root(project)
    for argv in (["generate", "comp-x"], ["author-test", "comp-x", "AC-X-1"]):
        rc, tokens, err = _invoke(env, argv, capsys)
        assert rc == 7
        assert tokens == argv + [root, "--model=claude-cli:sonnet"]
        assert "using model" not in err


def test_explicit_model_not_overridden(env, capsys):
    project = env[0]
    root = _root(project)
    for argv in (["generate", "comp-x", "--model", "m"], ["generate", "comp-x", "--model=m"]):
        rc, tokens, err = _invoke(env, argv, capsys)
        assert rc == 7
        assert tokens == argv + [root]


def test_none_and_value_error_inject_nothing(env, capsys):
    project = env[0]
    root = _root(project)

    _write_llm_endpoint(project, "none")
    rc, tokens, err = _invoke(env, ["generate", "comp-x"], capsys)
    assert rc == 7
    assert tokens == ["generate", "comp-x", root]

    _write_llm_endpoint(project, "error")
    rc, tokens, err = _invoke(env, ["generate", "comp-x"], capsys)
    assert rc == 7
    assert tokens == ["generate", "comp-x", root]
    assert "bad" in [line.strip() for line in err.splitlines()]


def test_no_rows_never_gain_model(env, capsys):
    project = env[0]
    root = _root(project)

    rc, tokens, err = _invoke(env, ["lint"], capsys)
    assert rc == 7
    assert not any(t == "--model" or t.startswith("--model=") for t in tokens)
    assert tokens == [root]
    assert "using model" not in err

    rc, tokens, err = _invoke(env, ["decision", "new", "x"], capsys)
    assert rc == 7
    assert not any(t == "--model" or t.startswith("--model=") for t in tokens)
    assert tokens == ["decision", "new", "x", root]
    assert "using model" not in err


def test_optional_rows_gain_model_and_print_notice(env, capsys):
    project = env[0]
    root = _root(project)

    rc, tokens, err = _invoke(env, ["assist", "--changed=R-X-1"], capsys)
    assert rc == 7
    assert tokens[-2:] == [root, "--model=claude-cli:sonnet"]
    assert tokens == ["--changed=R-X-1", root, "--model=claude-cli:sonnet"]
    assert _using_count(err) == 1

    rc, tokens, err = _invoke(env, ["verify"], capsys)
    assert rc == 7
    assert tokens[-2:] == [root, "--model=claude-cli:sonnet"]
    assert tokens == ["verify", root, "--model=claude-cli:sonnet"]
    assert _using_count(err) == 1


def test_no_model_removed_for_model_rows(env, capsys):
    project = env[0]
    root = _root(project)

    rc, tokens, err = _invoke(env, ["assist", "--changed=R-X-1", "--no-model"], capsys)
    assert rc == 7
    assert tokens == ["--changed=R-X-1", root]
    assert "using model" not in err

    rc, tokens, err = _invoke(env, ["generate", "comp-x", "--no-model"], capsys)
    assert rc == 7
    assert tokens == ["generate", "comp-x", root]
    assert "using model" not in err


def test_no_model_forwarded_unchanged_for_no_row(env, capsys):
    project = env[0]
    root = _root(project)
    rc, tokens, err = _invoke(env, ["lint", "--no-model"], capsys)
    assert rc == 7
    assert tokens == ["--no-model", root]
    assert "using model" not in err