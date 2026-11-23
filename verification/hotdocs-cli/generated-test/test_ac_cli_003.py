# hotdocs-criterion: sha256:b025605f950dc436e5ec0e4186cc9a2b8f93918db3270effabf0d10d492fe671
import json
import os
import sys
import time

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

FAKE_COMPONENTS = [
    ("gen/component-gate-runner", "component_gate_runner"),
    ("gen/test-author", "test_author"),
    ("gen/spec-linter", "spec_linter"),
    ("gen/spec-scaffolder", "spec_scaffolder"),
    ("gen/spec-completeness-assistant", "spec_completeness_assistant"),
    ("gen/provenance-tracker", "provenance_tracker"),
]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    # Bump mtime so any source-based cache sees a change.
    now = time.time() + 5
    os.utime(str(path), (now, now))


def _fake_component_source(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def main(argv=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(argv) + '\\n')\n"
        "    return 7\n"
    )


def _write_llm_fake(project, mode):
    path = project / "gen" / "llm-endpoint" / "llm_endpoint.py"
    if mode == "config":
        body = (
            "CONFIG = " + repr(CONFIG) + "\n"
            "def load_config(config_path=None):\n"
            "    return dict(CONFIG)\n"
        )
    elif mode == "none":
        body = (
            "def load_config(config_path=None):\n"
            "    return None\n"
        )
    elif mode == "raise":
        body = (
            "def load_config(config_path=None):\n"
            "    raise ValueError(" + repr("bad") + ")\n"
            "# this fake raises a ValueError on every call\n"
        )
    else:
        raise AssertionError(mode)
    _write(path, body)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    log = project / "calls.log"
    for directory, module in FAKE_COMPONENTS:
        _write(project / directory / (module + ".py"), _fake_component_source(log))
    (project / "hotdocs.toml").write_text(
        "[llm]\nprovider = \"claude-cli\"\nmodel = \"sonnet\"\n", encoding="utf-8"
    )
    _write_llm_fake(project, "config")
    root = os.path.abspath(str(project))
    return project, tool_root, log, root


def _call(setup, capsys, argv):
    project, tool_root, log, _root = setup
    if log.exists():
        log.unlink()
    capsys.readouterr()
    outputs = []
    code = hotdocs_cli.run(
        list(argv),
        tool_root=str(tool_root),
        output_fn=lambda *a, **k: outputs.append(a),
        env=dict(os.environ),
        cwd=str(project),
    )
    captured = capsys.readouterr()
    assert log.exists(), "fake component was not called for " + repr(argv)
    lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    return code, json.loads(lines[0]), captured.err


def _has_model(tokens):
    return any(t == "--model" or t.startswith("--model=") for t in tokens)


def test_required_rows_gain_model_last(setup, capsys):
    root = setup[3]
    code, tokens, _err = _call(setup, capsys, ["generate", "comp-x"])
    assert code == 7
    assert tokens == ["generate", "comp-x", "--repo-root=" + root, "--model=claude-cli:sonnet"]

    code, tokens, _err = _call(setup, capsys, ["author-test", "comp-x", "AC-X-1"])
    assert code == 7
    assert tokens == [
        "author-test", "comp-x", "AC-X-1", "--repo-root=" + root, "--model=claude-cli:sonnet",
    ]


def test_explicit_model_passes_unchanged(setup, capsys):
    root = setup[3]
    code, tokens, _err = _call(setup, capsys, ["generate", "comp-x", "--model", "m"])
    assert code == 7
    assert tokens == ["generate", "comp-x", "--model", "m", "--repo-root=" + root]

    code, tokens, _err = _call(setup, capsys, ["generate", "comp-x", "--model=m"])
    assert code == 7
    assert tokens == ["generate", "comp-x", "--model=m", "--repo-root=" + root]


def test_none_then_value_error_injects_nothing(setup, capsys):
    project, _tool_root, _log, root = setup
    _write_llm_fake(project, "none")
    code, tokens, _err = _call(setup, capsys, ["generate", "comp-x"])
    assert code == 7
    assert tokens == ["generate", "comp-x", "--repo-root=" + root]

    _write_llm_fake(project, "raise")
    code, tokens, err = _call(setup, capsys, ["generate", "comp-x"])
    assert code == 7
    assert tokens == ["generate", "comp-x", "--repo-root=" + root]
    assert "bad" in err.splitlines()


def test_no_rows_never_gain_model(setup, capsys):
    root = setup[3]
    code, tokens, err = _call(setup, capsys, ["lint"])
    assert code == 7
    assert not _has_model(tokens)
    assert tokens == ["--repo-root=" + root]
    assert "using model" not in err

    code, tokens, err = _call(setup, capsys, ["decision", "new", "x"])
    assert code == 7
    assert not _has_model(tokens)
    assert tokens == ["decision", "new", "x", "--repo-root=" + root]
    assert "using model" not in err


def test_optional_rows_gain_model_and_print_line(setup, capsys):
    root = setup[3]
    code, tokens, err = _call(setup, capsys, ["assist", "--changed=R-X-1"])
    assert code == 7
    assert tokens[-2:] == ["--repo-root=" + root, "--model=claude-cli:sonnet"]
    assert tokens == ["--changed=R-X-1", "--repo-root=" + root, "--model=claude-cli:sonnet"]
    assert err.splitlines().count(USING_LINE) == 1

    code, tokens, err = _call(setup, capsys, ["verify"])
    assert code == 7
    assert tokens[-2:] == ["--repo-root=" + root, "--model=claude-cli:sonnet"]
    assert tokens == ["verify", "--repo-root=" + root, "--model=claude-cli:sonnet"]
    assert err.splitlines().count(USING_LINE) == 1


def test_no_model_removed_for_model_rows(setup, capsys):
    root = setup[3]
    code, tokens, _err = _call(setup, capsys, ["assist", "--changed=R-X-1", "--no-model"])
    assert code == 7
    assert tokens == ["--changed=R-X-1", "--repo-root=" + root]

    code, tokens, _err = _call(setup, capsys, ["generate", "comp-x", "--no-model"])
    assert code == 7
    assert tokens == ["generate", "comp-x", "--repo-root=" + root]


def test_no_model_forwarded_for_no_row(setup, capsys):
    root = setup[3]
    code, tokens, _err = _call(setup, capsys, ["lint", "--no-model"])
    assert code == 7
    assert tokens == ["--no-model", "--repo-root=" + root]