"""AC-ASSEMBLE-012 — cold-mode SpecBundle.spec excludes the target's own
Rationale, Open questions, and Change log sections, but keeps Purpose and
Scope (R-ASSEMBLE-001)."""

from pathlib import Path

import spec_bundle_assembler


COMPONENT_ID = "comp-fixture-widget"
COMPONENT_SLUG = "fixture-widget"

PURPOSE_TOKEN = "PURPOSE_MARKER_qz81vx"
SCOPE_TOKEN = "SCOPE_MARKER_mt47kd"
RATIONALE_TOKEN = "RATIONALE_MARKER_wb93fj"
OPEN_QUESTIONS_TOKEN = "OPENQUESTIONS_MARKER_hn26pc"
CHANGE_LOG_TOKEN = "CHANGELOG_MARKER_ry58tl"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "---\n"
        "id: glossary\n"
        "title: Glossary\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        "---\n"
        "\n"
        "# Glossary\n"
        "\n"
        "- **Widget** — a fixture-only term used by this test.\n",
    )

    comp_dir = repo_root / "specs" / "components" / COMPONENT_SLUG
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: {COMPONENT_ID}\n"
        "title: Fixture widget\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        "sealed: true\n"
        "source_path: fake/fixture_widget_src\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Fixture widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"The widget exists to demonstrate {PURPOSE_TOKEN} behavior.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"In scope: {SCOPE_TOKEN} handling of widgets.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "No deltas beyond the glossary.\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"We chose this design because of {RATIONALE_TOKEN} considerations.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "None.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        f"- Should we revisit {OPEN_QUESTIONS_TOKEN} later?\n"
        "\n"
        "## Change log\n"
        "\n"
        f"- Initial draft, {CHANGE_LOG_TOKEN}.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FIXTURE-001.md",
        "# R-FIXTURE-001\n"
        "\n"
        "**R-FIXTURE-001** — The widget MUST return the string `ok` when "
        "called.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FIXTURE-001.md",
        "# AC-FIXTURE-001\n"
        "\n"
        "Covers: R-FIXTURE-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is called\n"
        "Then it returns ok\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "widget() -> str\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "- No network access.\n",
    )


def _assert_lint_clean_if_available(repo_root: Path) -> None:
    try:
        from spec_linter import lint  # type: ignore
    except ImportError:
        return
    report = lint(None, repo_root)
    findings = _get(report, "findings", None)
    if findings is None:
        findings = report if isinstance(report, (list, tuple)) else []
    hard = []
    for f in findings:
        severity = _get(f, "severity", None) or _get(f, "level", None)
        if str(severity).lower() in ("hard", "hard-fail", "hard_fail", "error"):
            hard.append(f)
    assert hard == [], f"fixture is not lint-clean: {hard!r}"


def test_ac_assemble_012_cold_spec_excludes_rationale_open_questions_change_log(
    tmp_path,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    _assert_lint_clean_if_available(repo_root)

    bundle = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root, mode="cold")

    spec = _get(bundle, "spec")
    assert isinstance(spec, str), f"spec field missing or not a string: {spec!r}"

    assert PURPOSE_TOKEN in spec, "Purpose text missing from spec"
    assert SCOPE_TOKEN in spec, "Scope text missing from spec"

    assert RATIONALE_TOKEN not in spec, "Rationale text leaked into spec"
    assert OPEN_QUESTIONS_TOKEN not in spec, "Open questions text leaked into spec"
    assert CHANGE_LOG_TOKEN not in spec, "Change log text leaked into spec"