# hotdocs-criterion: sha256:e1ac258a21353d6cfbcdd6c0fcd209b1b439afc4a35b8932edec2d3f3b4b117a
import json
import os
import sys

import pytest

import hotdocs_cli


CONFIG_SOURCE = (
    "def load_config(config_path=None):\n"
    "    return {"
    + repr("provider") + ": " + repr("claude-cli") + ", "
    + repr("model") + ": " + repr("sonnet") + ", "
    + repr("base_url") + ": None, "
    + repr("api_key_env") + ": None, "
    + repr("timeout_seconds") + ": None, "
    + repr("auth") + ": None}\n"
)

NONE_SOURCE = (
    "def load_config(config_path=None):\n"
    "    return None\n"
)

RAISE_SOURCE = (
    "def load_config(config_path=None):\n"
    "    raise ValueError(" + repr("bad") + ")\n"
)

FAKE_COMPONENTS = [
    ("gen/component-gate-runner", "component_gate_runner"),
    ("gen/test-author", "test_author"),
    ("gen/spec-completeness-assistant", "spec_completeness_assistant"),
    ("gen/provenance-tracker", "provenance_tracker"),
    ("gen/spec-linter", "spec_linter"),
    ("gen/spec-scaffolder", "spec_scaffolder"),
]

USING_LINE = "hotdocs: using model claude-cli:sonnet from hotdocs.toml (pass --no-model to skip)"


def write_llm_endpoint(project, source):
    directory = project / "gen" / "llm-endpoint"
    directory.mkdir(parents=True, exist_ok=True)
    cache = directory / "__pycache__"
    if cache.is_dir():
        for entry in cache.iterdir():
            entry.unlink()
    (directory / "llm_endpoint.py").write_text(source, encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    project = tmp_path / "project"
    project.mkdir()
    tool_root = tmp_path / "tool"
    (tool_root / "gen").mkdir(parents=True)
    log = project / "calls.log"
    fake_source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "def main(argv=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as handle:\n"
        "        handle.write(json.dumps(argv) + '\\n')\n"
        "    return 7\n"
    )
    for directory, module in FAKE_COMPONENTS:
        target = project / directory
        target.mkdir(parents=True, exist_ok=True)
        (target / (module + ".py")).write_text(fake_source, encoding="utf-8")
    write_llm_endpoint(project, CONFIG_SOURCE)
    return {
        "project": project,
        "tool_root": tool_root,
        "log": log,
        "root": os.path.abspath(str(project)),
    }


def invoke(env, capsys, argv):
    capsys.readouterr()
    if env["log"].exists():
        env["log"].unlink()
    outputs = []
    code = hotdocs_cli.run(
        list(argv),
        tool_root=str(env["tool_root"]),
        output_fn=lambda *a, **k: outputs.append(a),
        env=dict(os.environ),
        cwd=str(env["project"]),
    )
    captured = capsys.readouterr()
    assert env["log"].exists(), "fake component was not called"
    lines = [line for line in env["log"].read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    return code, json.loads(lines[0]), captured.err


def has_model_token(tokens):
    return any(t == "--model" or t.startswith("--model=") for t in tokens)


def test_required_rows_gain_model_last(env, capsys):
    root = env["root"]
    code, forwarded, _ = invoke(env, capsys, ["generate", "comp-x"])
    assert code == 7
    assert forwarded == ["generate", "comp-x", "--repo-root=" + root, "--model=claude-cli:sonnet"]

    code, forwarded, _ = invoke(env, capsys, ["author-test", "comp-x", "AC-X-1"])
    assert code == 7
    assert forwarded == [
        "author-test", "comp-x", "AC-X-1", "--repo-root=" + root, "--model=claude-cli:sonnet",
    ]


def test_explicit_model_passes_unchanged(env, capsys):
    root = env["root"]
    code, forwarded, _ = invoke(env, capsys, ["generate", "comp-x", "--model", "m"])
    assert code == 7
    assert forwarded == ["generate", "comp-x", "--model", "m", "--repo-root=" + root]

    code, forwarded, _ = invoke(env, capsys, ["generate", "comp-x", "--model=m"])
    assert code == 7
    assert forwarded == ["generate", "comp-x", "--model=m", "--repo-root=" + root]


def test_none_then_value_error_injects_nothing(env, capsys):
    root = env["root"]
    write_llm_endpoint(env["project"], NONE_SOURCE)
    code, forwarded, err = invoke(env, capsys, ["generate", "comp-x"])
    assert code == 7
    assert forwarded == ["generate", "comp-x", "--repo-root=" + root]

    write_llm_endpoint(env["project"], RAISE_SOURCE)
    code, forwarded, err = invoke(env, capsys, ["generate", "comp-x"])
    assert code == 7
    assert forwarded == ["generate", "comp-x", "--repo-root=" + root]
    assert "bad" in err.splitlines()


def test_no_rows_never_gain_model(env, capsys):
    root = env["root"]
    code, forwarded, err = invoke(env, capsys, ["lint"])
    assert code == 7
    assert forwarded == ["--repo-root=" + root]
    assert not has_model_token(forwarded)
    assert "using model" not in err

    code, forwarded, err = invoke(env, capsys, ["decision", "new", "x"])
    assert code == 7
    assert forwarded == ["decision", "new", "x", "--repo-root=" + root]
    assert not has_model_token(forwarded)
    assert "using model" not in err


def test_optional_rows_gain_model_and_print_notice(env, capsys):
    root = env["root"]
    code, forwarded, err = invoke(env, capsys, ["assist", "--changed=R-X-1"])
    assert code == 7
    assert forwarded[-2:] == ["--repo-root=" + root, "--model=claude-cli:sonnet"]
    assert forwarded == ["--changed=R-X-1", "--repo-root=" + root, "--model=claude-cli:sonnet"]
    assert err.splitlines().count(USING_LINE) == 1

    code, forwarded, err = invoke(env, capsys, ["verify"])
    assert code == 7
    assert forwarded[-2:] == ["--repo-root=" + root, "--model=claude-cli:sonnet"]
    assert forwarded == ["verify", "--repo-root=" + root, "--model=claude-cli:sonnet"]
    assert err.splitlines().count(USING_LINE) == 1


def test_no_model_removed_for_model_rows(env, capsys):
    root = env["root"]
    code, forwarded, _ = invoke(env, capsys, ["assist", "--changed=R-X-1", "--no-model"])
    assert code == 7
    assert forwarded == ["--changed=R-X-1", "--repo-root=" + root]

    code, forwarded, _ = invoke(env, capsys, ["generate", "comp-x", "--no-model"])
    assert code == 7
    assert forwarded == ["generate", "comp-x", "--repo-root=" + root]


def test_no_model_forwarded_unchanged_for_no_row(env, capsys):
    root = env["root"]
    code, forwarded, _ = invoke(env, capsys, ["lint", "--no-model"])
    assert code == 7
    assert forwarded == ["--no-model", "--repo-root=" + root]