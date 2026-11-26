# hotdocs-criterion: sha256:2aeb2ccc8a43675c80f307efe94b16c20e282c9d329b422f6dc9959043d6176f
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY_TERM = "Widget"
GLOSSARY_DEFINITION = (
    "a reusable unit of configuration shared across the whole corpus "
    "by every tool that reads specification documents."
)
LOCAL_DEFINITION = (
    "here specifically, the cached rendering this component produces "
    "locally during nightly batch export runs, discarded after upload."
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **" + GLOSSARY_TERM + "** \u2014 " + GLOSSARY_DEFINITION + "\n"
        "- **Gadget** \u2014 an unrelated term used only as filler here.\n",
    )
    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo exports things.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: exporting.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "- **" + GLOSSARY_TERM + "** \u2014 " + LOCAL_DEFINITION + "\n"
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
        "See `interface/data/`.\n"
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
        "## Change log\n"
        "\n"
        "- Initial draft.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** \u2014 Foo MUST export a widget.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When foo exports it\n"
        "Then the export exists\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n- None beyond defaults.\n",
    )


def test_low_overlap_definitions_delta_is_not_a_redefinition(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    lint_011 = [f for f in findings if field(f, "rule_id") == "R-LINT-011"]
    assert lint_011 == [], (
        "expected no R-LINT-011 finding for a low-overlap delta, got: "
        + repr([field(f, "message") for f in lint_011])
    )