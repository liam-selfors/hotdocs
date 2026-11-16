import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


COMPONENT_LOCATIONS = {
    "generate": ("gen/component-gate-runner", "component_gate_runner"),
    "author-test": ("gen/test-author", "test_author"),
    "verify": ("gen/provenance-tracker", "provenance_tracker"),
    "lint": ("gen/spec-linter", "spec_linter"),
    "assist": ("gen/spec-completeness-assistant", "spec_completeness_assistant"),
}

FULL_CONFIG_BODY = (
    "    return {\n"
    "        'provider': 'claude-cli',\n"
    "        'model': 'sonnet',\n"
    "        'base_url': None,\n"
    "        'api_key_env': None,\n"
    "        'timeout_seconds': None,\n"
    "    }\n"
)

NONE_CONFIG_BODY = "    return None\n"

RAISING_CONFIG_BODY = "    raise ValueError('bad')\n"


def _fake_component_source(log_path):
    return (
        "import json\n"
        "\n"
        "def main(argv):\n"
        f"    with open({str(log_path)!r}, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(list(argv)) + '\\n')\n"
        "    return 7\n"
    )


def _fake_llm_endpoint_source(body):
    return (
        "class ModelResolutionError(Exception):\n"
        "    pass\n"
        "\n"
        "def load_config(config_path=None):\n"
        f"{body}"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(base, name, load_config_body):
    """Create a fresh project and a fresh fake tool root, each holding the
    fake components and a fake llm-endpoint. Every fake logs to the
    project's calls.log."""
    project = base / name / "project"
    tool_root = base / name / "tool"
    project.mkdir(parents=True)
    tool_root.mkdir(parents=True)
    log_path = project / "calls.log"
    _write(
        project / "hotdocs.toml",
        '[llm]\nprovider = "claude-cli"\nmodel = "sonnet"\n',
    )
    for root in (project, tool_root):
        for directory, module in COMPONENT_LOCATIONS.values():
            _write(root / directory / f"{module}.py", _fake_component_source(log_path))
        _write(
            root / "gen" / "llm-endpoint" / "llm_endpoint.py",
            _fake_llm_endpoint_source(load_config_body),
        )
    return project, tool_root, log_path


def _env():
    env = dict(os.environ)
    env.pop("VAR_HOTDOCS_CONFIG", None)
    return env


def _run(project, tool_root, argv):
    return hotdocs_cli.main(
        list(argv),
        tool_root=tool_root,
        input_fn=lambda *a, **k: "",
        output_fn=lambda *a, **k: None,
        env=_env(),
        cwd=project,
    )


def _recorded(log_path):
    assert log_path.exists(), "fake component was never invoked"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected exactly one recorded call, got {lines!r}"
    return json.loads(lines[0])


def _normalize(tokens, project):
    out = []
    target = Path(project).resolve()
    for tok in tokens:
        if isinstance(tok, str) and tok.startswith("--repo-root="):
            value = tok[len("--repo-root="):]
            if Path(value).resolve() == target:
                out.append("--repo-root=<project>")
                continue
        out.append(tok)
    return out


def _has_model(tokens):
    return any(t == "--model" or str(t).startswith("--model=") for t in tokens)


@pytest.mark.parametrize(
    "argv",
    [
        ["generate", "comp-x"],
        ["author-test", "comp-x", "AC-X-1"],
    ],
)
def test_configured_model_is_appended_last(tmp_path, argv):
    project, tool_root, log_path = _build(tmp_path, "case", FULL_CONFIG_BODY)
    rc = _run(project, tool_root, argv)
    assert rc == 7
    tokens = _normalize(_recorded(log_path), project)
    assert tokens == list(argv) + [
        "--repo-root=<project>",
        "--model=claude-cli:sonnet",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["generate", "comp-x", "--model", "m"],
        ["generate", "comp-x", "--model=m"],
    ],
)
def test_explicit_model_passes_unchanged(tmp_path, argv):
    project, tool_root, log_path = _build(tmp_path, "case", FULL_CONFIG_BODY)
    rc = _run(project, tool_root, argv)
    assert rc == 7
    tokens = _normalize(_recorded(log_path), project)
    assert tokens == list(argv) + ["--repo-root=<project>"]
    model_tokens = [t for t in tokens if t == "--model" or t.startswith("--model=")]
    assert len(model_tokens) == 1


def test_no_config_or_invalid_config_injects_nothing(tmp_path, capsys):
    # First: load_config returns None.
    project1, tool_root1, log1 = _build(tmp_path, "none", NONE_CONFIG_BODY)
    rc1 = _run(project1, tool_root1, ["generate", "comp-x"])
    assert rc1 == 7
    tokens1 = _normalize(_recorded(log1), project1)
    assert tokens1 == ["generate", "comp-x", "--repo-root=<project>"]
    first = capsys.readouterr()
    assert "bad" not in first.err

    # Second: load_config raises ValueError("bad").
    project2, tool_root2, log2 = _build(tmp_path, "raise", RAISING_CONFIG_BODY)
    rc2 = _run(project2, tool_root2, ["generate", "comp-x"])
    assert rc2 == 7
    tokens2 = _normalize(_recorded(log2), project2)
    assert tokens2 == ["generate", "comp-x", "--repo-root=<project>"]
    second = capsys.readouterr()
    assert "bad" in second.err


@pytest.mark.parametrize(
    "argv",
    [
        ["verify"],
        ["lint"],
        ["assist"],
    ],
)
def test_model_never_injected_for_non_model_rows(tmp_path, argv):
    project, tool_root, log_path = _build(tmp_path, "case", FULL_CONFIG_BODY)
    rc = _run(project, tool_root, argv)
    assert rc == 7
    tokens = _recorded(log_path)
    assert not _has_model(tokens), f"unexpected --model in {tokens!r}"