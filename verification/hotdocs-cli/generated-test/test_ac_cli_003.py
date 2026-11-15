import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


COMPONENT_FAKE = '''\
import json

_LOG = {log!r}


def main(argv):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(list(argv)) + "\\n")
    return 7
'''

LLM_ENDPOINT_FAKE = '''\
import json

_BEHAVIOR = {behavior!r}


def load_config(config_path=None):
    with open(_BEHAVIOR, "r", encoding="utf-8") as fh:
        behavior = json.load(fh)
    mode = behavior["mode"]
    if mode == "raise":
        raise ValueError(behavior["message"])
    if mode == "none":
        return None
    return {{
        "provider": behavior["provider"],
        "model": behavior["model"],
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
    }}
'''

ROWS = [
    ("gen/component-gate-runner", "component_gate_runner"),
    ("gen/test-author", "test_author"),
    ("gen/provenance-tracker", "provenance_tracker"),
    ("gen/spec-linter", "spec_linter"),
    ("gen/spec-completeness-assistant", "spec_completeness_assistant"),
]


def _set_behavior(project, mode, message=None):
    data = {"mode": mode, "provider": "claude-cli", "model": "sonnet"}
    if message is not None:
        data["message"] = message
    (project / "llm_behavior.json").write_text(json.dumps(data), encoding="utf-8")


def _make_project(base):
    project = (base / "project")
    project.mkdir(parents=True)
    project = project.resolve()
    tool_root = (base / "tool")
    tool_root.mkdir(parents=True)
    tool_root = tool_root.resolve()

    log = project / "calls.log"
    for rel_dir, module in ROWS:
        d = project / rel_dir
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{module}.py").write_text(
            COMPONENT_FAKE.format(log=str(log)), encoding="utf-8"
        )

    llm_dir = project / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True, exist_ok=True)
    (llm_dir / "llm_endpoint.py").write_text(
        LLM_ENDPOINT_FAKE.format(behavior=str(project / "llm_behavior.json")),
        encoding="utf-8",
    )
    (project / "hotdocs.toml").write_text(
        '[llm]\nprovider = "claude-cli"\nmodel = "sonnet"\n', encoding="utf-8"
    )
    _set_behavior(project, "config")
    return project, tool_root


def _env():
    env = dict(os.environ)
    env.pop("VAR_HOTDOCS_CONFIG", None)
    return env


def _no_input(*args, **kwargs):
    raise AssertionError("input_fn must not be called")


def _run(project, tool_root, argv):
    log = project / "calls.log"
    if log.exists():
        log.unlink()
    code = hotdocs_cli.main(
        list(argv),
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=lambda *a, **k: None,
        env=_env(),
        cwd=project,
    )
    assert log.exists(), f"fake component was not invoked for {argv!r}"
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected exactly one invocation, got {lines!r}"
    return code, json.loads(lines[0])


def _has_model(tokens):
    return any(t == "--model" or t.startswith("--model=") for t in tokens)


def test_model_injected_last_for_required_rows(tmp_path):
    project, tool_root = _make_project(tmp_path)
    repo_token = f"--repo-root={project}"

    for argv in (["generate", "comp-x"], ["author-test", "comp-x", "AC-X-1"]):
        code, forwarded = _run(project, tool_root, argv)
        assert code == 7
        assert forwarded == argv + [repo_token, "--model=claude-cli:sonnet"]
        assert forwarded[-1] == "--model=claude-cli:sonnet"


@pytest.mark.parametrize(
    "argv",
    [
        ["generate", "comp-x", "--model", "m"],
        ["generate", "comp-x", "--model=m"],
    ],
)
def test_explicit_model_passes_unchanged(tmp_path, argv):
    project, tool_root = _make_project(tmp_path)
    repo_token = f"--repo-root={project}"

    code, forwarded = _run(project, tool_root, argv)
    assert code == 7
    assert forwarded == argv + [repo_token]
    model_tokens = [t for t in forwarded if t == "--model" or t.startswith("--model=")]
    assert len(model_tokens) == 1


def test_none_or_invalid_config_injects_nothing(tmp_path, capsys):
    project, tool_root = _make_project(tmp_path)
    repo_token = f"--repo-root={project}"
    expected = ["generate", "comp-x", repo_token]

    _set_behavior(project, "none")
    capsys.readouterr()
    code, forwarded = _run(project, tool_root, ["generate", "comp-x"])
    capsys.readouterr()
    assert code == 7
    assert forwarded == expected

    _set_behavior(project, "raise", message="bad")
    code, forwarded = _run(project, tool_root, ["generate", "comp-x"])
    captured = capsys.readouterr()
    assert code == 7
    assert forwarded == expected
    assert "bad" in captured.err


def test_model_never_injected_for_no_rows(tmp_path):
    project, tool_root = _make_project(tmp_path)
    _set_behavior(project, "config")

    for argv in (["verify"], ["lint"], ["assist"]):
        code, forwarded = _run(project, tool_root, argv)
        assert code == 7
        assert not _has_model(forwarded), f"{argv!r} forwarded {forwarded!r}"