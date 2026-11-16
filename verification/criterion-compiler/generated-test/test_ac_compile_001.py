"""AC-COMPILE-001 (covers R-COMPILE-001).

Given acceptance/ content containing a step that does not match any
recognized template in the step grammar, when compile-criteria runs against
it, the CompileReport marks that criterion status: error, naming the exact
file, line, and the unmatched step text -- not a silent skip.
"""

import os
from pathlib import Path

import pytest

import criterion_compiler


SLUG = "widget"
COMPONENT_ID = "comp-" + SLUG
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"
UNMATCHED_STEP = "When a wizard appears"
UNMATCHED_LINE = 8  # 1-based line of UNMATCHED_STEP in the acceptance file below
ACCEPTANCE_REL = "specs/components/{}/acceptance/{}.md".format(SLUG, CRITERION_ID)


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _acceptance_text() -> str:
    lines = [
        "# {}".format(CRITERION_ID),          # 1
        "",                                    # 2
        "Covers: {}".format(REQUIREMENT_ID),   # 3
        "Kind: compiled",                      # 4
        "",                                    # 5
        "```gherkin",                          # 6
        'Given a payload is "hi"',             # 7
        UNMATCHED_STEP,                        # 8
        "Then value equals 1",                 # 9
        "```",                                 # 10
        "",
    ]
    text = "\n".join(lines)
    assert text.splitlines()[UNMATCHED_LINE - 1] == UNMATCHED_STEP
    return text


def _build_fixture(repo_root: Path) -> Path:
    comp_dir = repo_root / "specs" / "components" / SLUG
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: {}\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A synthetic fixture component for criterion-compiler tests.\n".format(COMPONENT_ID),
    )
    _write(
        comp_dir / "requirements" / "{}.md".format(REQUIREMENT_ID),
        "# {rid}\n\n**{rid}** — The widget MUST do its thing.\n".format(rid=REQUIREMENT_ID),
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\ndo_thing(x)\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp_dir / "acceptance" / "{}.md".format(CRITERION_ID), _acceptance_text())
    return comp_dir


def _same_file(reported, repo_root: Path, expected_rel: str) -> bool:
    if reported is None:
        return False
    reported_path = Path(str(reported))
    if not reported_path.is_absolute():
        reported_path = repo_root / reported_path
    try:
        return os.path.realpath(str(reported_path)) == os.path.realpath(
            str(repo_root / expected_rel)
        )
    except OSError:
        return False


def _assert_located_message(message, line_no: int) -> None:
    assert isinstance(message, str), "error entry must carry a text message, got %r" % (message,)
    assert message.startswith("line {}: ".format(line_no)), (
        "message must begin with the offending step's 1-based line, got %r" % message
    )
    assert "'{}'".format(UNMATCHED_STEP) in message, (
        "message must quote the unmatched step as written, with its keyword: %r" % message
    )
    assert "does not match any recognized template" in message, message


def test_compile_marks_unmatched_step_as_located_error(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    out_dir = tmp_path / "out"

    report = criterion_compiler.compile(COMPONENT_ID, repo_root, out_dir=out_dir)

    outputs = _get(report, "outputs")
    assert outputs is not None, "CompileReport must have outputs"
    outputs = list(outputs)

    entries = [o for o in outputs if _get(o, "criterion_id") == CRITERION_ID]
    assert len(entries) == 1, (
        "the criterion with an unmatched step must appear in outputs exactly once "
        "(never silently skipped); outputs=%r" % (outputs,)
    )
    entry = entries[0]

    assert _get(entry, "status") == "error", entry
    assert _get(entry, "covers") == REQUIREMENT_ID, entry
    assert _same_file(_get(entry, "file"), repo_root, ACCEPTANCE_REL), (
        "error entry must name the acceptance file, got %r" % (_get(entry, "file"),)
    )
    reported_file = str(_get(entry, "file"))
    if not Path(reported_file).is_absolute():
        assert Path(reported_file).as_posix() == ACCEPTANCE_REL, reported_file
    _assert_located_message(_get(entry, "message"), UNMATCHED_LINE)

    summary = _get(report, "summary")
    assert summary is not None
    errors = _get(summary, "errors")
    assert isinstance(errors, int) and errors >= 1, summary
    compiled = _get(summary, "compiled")
    assert compiled == 0, summary

    assert not (out_dir / "test_ac_widget_001.py").exists(), (
        "no compiled test file may be emitted for a criterion that failed to compile"
    )


def test_cli_exits_1_for_unmatched_step(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    out_dir = tmp_path / "out"

    code = criterion_compiler.main(
        [COMPONENT_ID, "--repo-root={}".format(repo_root), "--out={}".format(out_dir)]
    )
    assert code == 1
    assert not (out_dir / "test_ac_widget_001.py").exists()


def test_compile_criterion_reports_unmatched_step_with_gherkin_line():
    gherkin = "\n".join(
        [
            'Given a payload is "hi"',  # 1
            UNMATCHED_STEP,             # 2
            "Then value equals 1",      # 3
        ]
    )
    criterion = criterion_compiler.ParsedCriterion(
        criterion_id=CRITERION_ID,
        covers=REQUIREMENT_ID,
        kind="compiled",
        gherkin=gherkin,
        file=ACCEPTANCE_REL,
    )

    result = criterion_compiler.compile_criterion(criterion)

    assert _get(result, "status") == "error", result
    assert _get(result, "source") is None, (
        "an unmatched step must not produce best-effort compiled source: %r" % (result,)
    )
    _assert_located_message(_get(result, "message"), 2)


def test_compile_criterion_unmatched_step_errors_even_with_surface():
    gherkin = "\n".join(
        [
            'Given a payload is "hi"',
            UNMATCHED_STEP,
            "Then value equals 1",
        ]
    )
    criterion = criterion_compiler.ParsedCriterion(
        criterion_id=CRITERION_ID,
        covers=REQUIREMENT_ID,
        kind="compiled",
        gherkin=gherkin,
        file=ACCEPTANCE_REL,
    )
    surface = criterion_compiler.InterfaceSurface(
        functions={"do_thing": ["x"]},
        types={},
        module_name="widget",
    )

    result = criterion_compiler.compile_criterion(criterion, surface)

    assert _get(result, "status") == "error", result
    _assert_located_message(_get(result, "message"), 2)