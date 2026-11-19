# hotdocs-criterion: sha256:62658c384b0d81e29bde1789ebe40feca12058f202b351fc9d316ae8691ba8c1
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    specs = repo_root / "specs"

    write(
        specs / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Foo capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides foo.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: foo.\n",
    )

    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Does foo things for the test fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: foo.\n"
        "- Out of scope: bar.\n"
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
        "- Initial.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The component MUST do foo.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When foo runs\n"
        "Then foo happens\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )

    # Generated code well above the 1500 LOC hard-fail cap: 1600 non-blank,
    # non-comment lines, plus some blank and comment lines that must not count.
    lines = ["# generated module"]
    for i in range(1600):
        lines.append("value_" + str(i) + " = " + repr(i))
        if i % 100 == 0:
            lines.append("")
            lines.append("# comment " + str(i))
    write(repo_root / "gen" / "foo" / "foo.py", "\n".join(lines) + "\n")


def test_ac_size_001_generated_code_loc_over_1500_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001"
        and field(f, "severity") == "fail"
        and "generated_code_loc" in field(f, "message")
    ]
    assert matching, (
        "expected a fail-severity R-SIZE-001 finding naming generated_code_loc, got: "
        + repr(findings)
    )