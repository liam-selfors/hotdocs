# hotdocs-criterion: sha256:3afc6eceb8358189c0d08a42196d31ca8ce64712a7cceb4d9b53a2fe531860b6
import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


COMPONENTS = [
    ("gen/component-gate-runner", "component_gate_runner"),
    ("gen/test-author", "test_author"),
    ("gen/provenance-tracker", "provenance_tracker"),
    ("gen/spec-linter", "spec_linter"),
    ("gen/spec-completeness-assistant", "spec_completeness_assistant"),
]


def _write_component(project, dir_, module):
    target_dir = project / dir_
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(project / "calls.log")
    src = (
        "import json\n"
        "\n"
        "LOG = " + repr(log_path) + "\n"
        "\n"
        "def main(argv):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps(argv) + '\\n')\n"
        "    return 7\n"
    )
    (target_dir / (module + ".py")).write_text(src)


def _write_llm_endpoint(project):
    target_dir = project / "gen" / "llm-endpoint"
    target_dir.mkdir(parents=True, exist_ok=True)
    mode_path = str(project / "llm_mode.txt")
    src = (
        "MODE = " + repr(mode_path) + "\n"
        "\n"
        "def load_config(config_path=None):\n"
        "    with open(MODE) as f:\n"
        "        mode = f.read().strip()\n"
        "    if mode == 'none':\n"
        "        return None\n"
        "    if mode == 'raise':\n"
        "        raise ValueError('bad')\n"
        "    return {\n"
        "        'provider': 'claude-cli',\n"
        "        'model': 'sonnet',\n"
        "        'base_url': None,\n"
        "        'api_key_env': None,\n"
        "        'timeout_seconds': None,\n"
        "        'auth': None,\n"
        "    }\n"
    )
    (target_dir / "llm_endpoint.py").write_text(src)


@pytest.fixture
def env_setup(tmp_path):
    project = (tmp_path / "project")
    project.mkdir()
    project = project.resolve()
    tool_root = (tmp_path / "tool_root")
    tool_root.mkdir()
    tool_root = tool_root.resolve()
    (project / "hotdocs.toml").write_text(
        "[llm]\n" + "provider = " + json.dumps("claude-cli") + "\n"
        + "model = " + json.dumps("sonnet") + "\n"
    )
    for dir_, module in COMPONENTS:
        _write_component(project, dir_, module)
    _write_llm_endpoint(project)
    set_mode(project, "config")
    return project, tool_root


def set_mode(project, mode):
    (project / "llm_mode.txt").write_text(mode)


def run(project, tool_root, argv):
    log = project / "calls.log"
    if log.exists():
        log.unlink()
    code = hotdocs_cli.main(
        list(argv),
        tool_root=tool_root,
        input_fn=lambda *a, **k: "",
        output_fn=lambda *a, **k: None,
        env=dict(os.environ),
        cwd=project,
    )
    assert log.is_file(), "fake component was not called for " + repr(argv)
    lines = [ln for ln in log.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    return code, json.loads(lines[0])


def repo_root_token(project):
    return "--repo-root=" + str(project)


def has_model(tokens):
    return any(t == "--model" or t.startswith("--model=") for t in tokens)


def test_model_injected_for_required_rows(env_setup):
    project, tool_root = env_setup
    set_mode(project, "config")

    code, forwarded = run(project, tool_root, ["generate", "comp-x"])
    assert code == 7
    assert forwarded == [
        "generate",
        "comp-x",
        repo_root_token(project),
        "--model=claude-cli:sonnet",
    ]

    code, forwarded = run(project, tool_root, ["author-test", "comp-x", "AC-X-1"])
    assert code == 7
    assert forwarded == [
        "author-test",
        "comp-x",
        "AC-X-1",
        repo_root_token(project),
        "--model=claude-cli:sonnet",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["generate", "comp-x", "--model", "m"],
        ["generate", "comp-x", "--model=m"],
    ],
)
def test_explicit_model_passes_unchanged(env_setup, argv):
    project, tool_root = env_setup
    set_mode(project, "config")
    code, forwarded = run(project, tool_root, argv)
    assert code == 7
    assert forwarded == list(argv) + [repo_root_token(project)]
    model_tokens = [
        t for t in forwarded if t == "--model" or t.startswith("--model=")
    ]
    assert len(model_tokens) == 1


def test_no_injection_when_config_none_or_invalid(env_setup, capsys):
    project, tool_root = env_setup
    expected = ["generate", "comp-x", repo_root_token(project)]

    set_mode(project, "none")
    capsys.readouterr()
    code, forwarded = run(project, tool_root, ["generate", "comp-x"])
    assert code == 7
    assert forwarded == expected

    set_mode(project, "raise")
    capsys.readouterr()
    code, forwarded = run(project, tool_root, ["generate", "comp-x"])
    captured = capsys.readouterr()
    assert code == 7
    assert forwarded == expected
    assert "bad" in captured.err


@pytest.mark.parametrize("argv", [["verify"], ["lint"], ["assist"]])
def test_model_no_rows_never_gain_model(env_setup, argv):
    project, tool_root = env_setup
    set_mode(project, "config")
    code, forwarded = run(project, tool_root, argv)
    assert code == 7
    assert not has_model(forwarded), forwarded