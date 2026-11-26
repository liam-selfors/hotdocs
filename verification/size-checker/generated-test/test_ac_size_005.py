# hotdocs-criterion: sha256:6b26721f2bc11025222f7038075749393625c43523a37e6ed3fe018447504b7f
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "widget"

    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget does a small thing for tests.\n",
    )

    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "**R-WIDGET-001** — The widget MUST do the small thing.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it runs\n"
        "Then it does the small thing\n"
        "```\n",
    )

    # cli.md: first fenced block has three non-blank (logical) lines, one of
    # which ends in a backslash joining it to a fourth physical line, plus
    # one blank line.
    backslash = "\\"
    write(
        comp / "interface" / "cli.md",
        "# CLI\n"
        "\n"
        "```\n"
        "widget run --input FILE " + backslash + "\n"
        "    --output FILE\n"
        "\n"
        "widget status\n"
        "widget version\n"
        "```\n"
        "\n"
        "Prose after the block.\n",
    )

    # library.md: first fenced block has five signature lines and one prose line.
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "alpha(x: int) -> int\n"
        "beta(y: str) -> str\n"
        "gamma() -> None\n"
        "delta(a: int, b: int) -> list\n"
        "epsilon(path: Path) -> dict\n"
        "This line is prose and not a signature.\n"
        "```\n"
        "\n"
        "Some explanation.\n",
    )

    # interface/data/: three files.
    for stem in ("Alpha", "Beta", "Gamma"):
        write(
            comp / "interface" / "data" / (stem + ".md"),
            "# " + stem + "\n\nA small data shape.\n",
        )

    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def test_ac_size_005_interface_surface_warn(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size_001 = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001"
        and str(field(f, "message")).startswith("widget: ")
    ]

    assert len(size_001) == 1, size_001
    finding = size_001[0]
    assert field(finding, "severity") == "warn"
    message = field(finding, "message")
    assert "interface_surface" in message
    assert "11" in message
    assert message == (
        "widget: interface_surface is 11, above the warn threshold of 10 "
        "(specs/architecture/size-caps.md)"
    )