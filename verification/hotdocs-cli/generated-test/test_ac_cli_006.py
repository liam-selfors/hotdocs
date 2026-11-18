# hotdocs-criterion: sha256:0759c8de0fe59355169b4a938957591d79fc6285fa665fbb0b5f48a570a40422
import sys
from pathlib import Path

import pytest

import hotdocs_cli


def _write_fake(project, body_lines):
    """Write a fake spec-linter component at <project>/gen/spec-linter/spec_linter.py."""
    project = Path(project)
    comp_dir = project / "gen" / "spec-linter"
    comp_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(project / "calls.log")
    source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(log_path) + "\n"
        "\n"
        "\n"
        "def _log(argv):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(argv) + '\\n')\n"
        "\n"
        "\n"
    )
    source += "\n".join(body_lines) + "\n"
    (comp_dir / "spec_linter.py").write_text(source, encoding="utf-8")
    return project


def _returning_fake(project, code):
    return _write_fake(
        project,
        [
            "def main(argv):",
            "    _log(argv)",
            "    return " + repr(code),
        ],
    )


def _empty_tool_root(base):
    root = Path(base)
    root.mkdir(parents=True, exist_ok=True)
    (root / "gen").mkdir(exist_ok=True)
    return root


def _fresh():
    # Defensive only: make sure no stale module named like the fake lingers.
    sys.modules.pop("spec_linter", None)


def _run(argv, project, tool_root):
    _fresh()
    out = []
    return hotdocs_cli.main(
        argv,
        tool_root=tool_root,
        cwd=project,
        output_fn=lambda *a, **k: out.append(a),
    )


def test_routed_verb_returns_component_code(tmp_path):
    tool_root = _empty_tool_root(tmp_path / "toolroot")

    project0 = tmp_path / "project0"
    project0.mkdir()
    _returning_fake(project0, 0)

    project7 = tmp_path / "project7"
    project7.mkdir()
    _returning_fake(project7, 7)

    assert _run(["lint"], project0, tool_root) == 0
    assert (project0 / "calls.log").is_file()

    assert _run(["lint"], project7, tool_root) == 7
    assert (project7 / "calls.log").is_file()


def test_unknown_verb_version_and_missing_component(tmp_path):
    tool_root = _empty_tool_root(tmp_path / "toolroot")
    project = tmp_path / "project"
    project.mkdir()

    assert _run(["frobnicate"], project, tool_root) == 2
    assert _run(["--version"], project, tool_root) == 0
    assert _run(["lint"], project, tool_root) == 2


def test_model_resolution_error_is_usage_error(tmp_path, capsys):
    tool_root = _empty_tool_root(tmp_path / "toolroot")
    project = tmp_path / "project"
    project.mkdir()
    _write_fake(
        project,
        [
            "class ModelResolutionError(Exception):",
            "    pass",
            "",
            "",
            "def main(argv):",
            "    _log(argv)",
            "    raise ModelResolutionError(" + repr("model 'x' names no provider") + ")",
        ],
    )

    capsys.readouterr()
    code = _run(["lint"], project, tool_root)
    captured = capsys.readouterr()

    assert code == 2
    assert captured.err.splitlines() == ["usage error: model 'x' names no provider"]


def test_other_exception_propagates(tmp_path):
    tool_root = _empty_tool_root(tmp_path / "toolroot")
    project = tmp_path / "project"
    project.mkdir()
    _write_fake(
        project,
        [
            "def main(argv):",
            "    _log(argv)",
            "    raise ValueError(" + repr("boom") + ")",
        ],
    )

    with pytest.raises(ValueError, match="boom"):
        _run(["lint"], project, tool_root)