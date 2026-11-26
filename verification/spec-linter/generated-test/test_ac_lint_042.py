# hotdocs-criterion: sha256:2ac3f4ebac38fbe1205fb5f840c8d120f599bb8bb4a8fd1c66864fd7dd6bfc15
import pytest
from pathlib import Path

import spec_linter


COMPONENT_REL = "specs/components/foo/component.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root, drivers_value, depends_on="[]"):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — a thing the foo component handles.\n",
    )
    component = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: " + depends_on + "\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "drivers: " + drivers_value + "\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo handles widgets for its callers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
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
        "- Initial draft.\n"
    )
    comp_path = repo_root / COMPONENT_REL
    write(comp_path, component)
    comp_dir = comp_path.parent
    write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST accept a widget.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When foo accepts it\n"
        "Then it is accepted\n"
        "```\n",
    )
    write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )
    return comp_path


def drivers_line(comp_path):
    for index, line in enumerate(comp_path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.startswith("drivers:"):
            return index
    raise AssertionError("no drivers line written")


def findings_on_line(report, line):
    result = []
    for f in field(report, "findings"):
        if field(f, "file") == COMPONENT_REL and field(f, "line") == line:
            result.append(f)
    return result


@pytest.mark.parametrize(
    "drivers_value, plant_definition, expected_message",
    [
        ("[Bad_Name]", False, "driver 'Bad_Name' is not a driver name"),
        ("[nodrv]", False, "test driver 'nodrv' has no definition or adapter"),
        (
            "[mine]",
            True,
            "test driver 'mine' is defined in this repository; "
            "depends_on must list comp-driver-mine",
        ),
    ],
)
def test_bad_driver_items_get_one_fail_finding(tmp_path, drivers_value, plant_definition, expected_message):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp_path = build_corpus(repo_root, drivers_value, depends_on="[]")
    if plant_definition:
        write(
            repo_root / "specs" / "architecture" / "test-driver-mine.md",
            "---\n"
            "id: arch-test-driver-mine\n"
            "title: Test Driver Mine\n"
            "status: draft\n"
            "owners: [team]\n"
            "depends_on: []\n"
            "---\n"
            "\n"
            "# Test Driver Mine\n"
            "\n"
            "## Purpose\n"
            "\n"
            "A test driver defined in this repository.\n",
        )
    line = drivers_line(comp_path)

    report = spec_linter.lint(None, repo_root)

    on_line = findings_on_line(report, line)
    fails = [f for f in on_line if field(f, "severity") == "fail"]
    assert len(fails) == 1, [(field(f, "rule_id"), field(f, "message")) for f in on_line]
    assert field(fails[0], "message") == expected_message
    assert field(fails[0], "file") == COMPONENT_REL
    assert field(fails[0], "line") == line


def test_driver_with_planted_adapter_has_no_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp_path = build_corpus(repo_root, "[fake]", depends_on="[]")
    write(
        repo_root / "gen" / "driver-fake" / "driver_fake.py",
        "# any python\n"
        "VALUE = " + repr(1) + "\n",
    )
    assert not (repo_root / "specs" / "architecture" / "test-driver-fake.md").exists()
    line = drivers_line(comp_path)

    report = spec_linter.lint(None, repo_root)

    on_line = findings_on_line(report, line)
    assert on_line == [], [(field(f, "rule_id"), field(f, "message")) for f in on_line]