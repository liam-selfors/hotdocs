# hotdocs-criterion: sha256:508dabc146c2eae46b0e717f3fbe57f47400b35f05dc0862462015d6226acde9
"""AC-COMPILE-002 (covers R-COMPILE-002).

Given an acceptance/ step that references a function name not declared in
the paired component's interface/ contract, when compile-criteria runs,
then the CompileReport marks that criterion status: error, naming the
unresolved reference.
"""

from pathlib import Path

import criterion_compiler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


UNDECLARED = "frobnicate_widget"
DECLARED = "make_widget"
CRITERION_ID = "AC-WIDGET-001"
ACCEPTANCE_REL = "specs/components/widget/acceptance/" + CRITERION_ID + ".md"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "widget"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [widget-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "A tiny fixture component that builds widgets.\n",
    )
    _write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** \u2014 The component MUST build a widget from a name.\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        + DECLARED
        + "(name: str) -> dict\n"
        "```\n"
        "\n"
        "Builds a widget.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    # Line numbers in this file:
    # 1 heading, 2 blank, 3 Covers, 4 Kind, 5 blank, 6 fence,
    # 7 Given, 8 When (the offending step), 9 Then, 10 fence.
    _write(
        repo_root / ACCEPTANCE_REL,
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        'Given a payload is "abc"\n'
        "When " + UNDECLARED + ' is invoked with {"name": payload}\n'
        'Then name equals "abc"\n'
        "```\n",
    )


def _find_entry(report):
    outputs = field(report, "outputs")
    matches = [o for o in outputs if field(o, "criterion_id") == CRITERION_ID]
    assert len(matches) == 1, "expected exactly one output entry for " + CRITERION_ID + ": " + repr(outputs)
    return matches[0]


def test_compile_marks_unresolved_function_reference_as_error(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    out_dir = tmp_path / "out"

    report = criterion_compiler.compile("comp-widget", repo_root, target="pytest", out_dir=out_dir)

    entry = _find_entry(report)
    assert field(entry, "status") == "error"
    message = field(entry, "message")
    assert UNDECLARED in message, message
    assert "does not resolve" in message, message
    assert message.startswith("line 8: "), message

    file_value = field(entry, "file")
    assert Path(file_value).as_posix().endswith(ACCEPTANCE_REL), file_value

    summary = field(report, "summary")
    assert field(summary, "errors") >= 1
    assert field(summary, "compiled") == 0

    # Never silently emitted a test for the failing criterion.
    assert not (out_dir / "test_ac_widget_001.py").exists()


def test_cli_exits_1_for_unresolved_function_reference(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    out_dir = tmp_path / "out"

    code = criterion_compiler.main(
        ["comp-widget", "--target=pytest", "--out=" + str(out_dir), "--repo-root=" + str(repo_root)]
    )
    assert code == 1


def test_compile_criterion_marks_unresolved_function_reference_as_error():
    gherkin = (
        'Given a payload is "abc"\n'
        "When " + UNDECLARED + ' is invoked with {"name": payload}\n'
        'Then name equals "abc"'
    )
    criterion = criterion_compiler.ParsedCriterion(
        criterion_id=CRITERION_ID,
        covers="R-WIDGET-001",
        kind="compiled",
        gherkin=gherkin,
        file=ACCEPTANCE_REL,
    )
    surface = criterion_compiler.InterfaceSurface(
        functions={DECLARED: ["name"]},
        types={},
        module_name="widget",
    )

    result = criterion_compiler.compile_criterion(criterion, surface)

    assert field(result, "status") == "error"
    message = field(result, "message")
    assert UNDECLARED in message, message
    assert "does not resolve" in message, message
    assert message.startswith("line 2: "), message