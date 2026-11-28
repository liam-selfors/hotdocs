# hotdocs-criterion: sha256:db7a85d8262fc6ed6151ed57d9e2fabd11736860f4b8977f4923124ee6270fa9
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FENCE = "```"


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** \u2014 a thing under test.\n",
    )
    comp = specs / "components" / "widget"
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
        "A small widget used as a size-checker fixture.\n",
    )
    write(
        comp / "requirements" / "R-WID-001.md",
        "# R-WID-001\n\n**R-WID-001** \u2014 The widget MUST run.\n",
    )
    write(
        comp / "acceptance" / "AC-WID-001.md",
        "# AC-WID-001\n"
        "\n"
        "Covers: R-WID-001\n"
        "Kind: judgment\n"
        "\n"
        "The widget runs.\n",
    )
    # cli.md: three non-blank (logical) lines, one ending in a backslash
    # joining it to a fourth physical line, and one blank line -> 3
    write(
        comp / "interface" / "cli.md",
        "# CLI\n"
        "\n"
        + FENCE + "\n"
        "widget run --fast \\\n"
        "  --verbose\n"
        "\n"
        "widget stop\n"
        "widget status\n"
        + FENCE + "\n",
    )
    # library.md: five signature lines and one prose line -> 5
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        + FENCE + "\n"
        "alpha(x: int) -> int\n"
        "beta(y: str) -> str\n"
        "gamma() -> None\n"
        "delta(a, b) -> list\n"
        "epsilon(path: Path) -> dict\n"
        "This line is prose describing the functions.\n"
        + FENCE + "\n",
    )
    # interface/data/: three files -> 3
    for name in ("Alpha", "Beta", "Gamma"):
        write(
            comp / "interface" / "data" / (name + ".md"),
            "# " + name + "\n\nA data shape.\n",
        )


def test_ac_size_005_interface_surface_counts_cli_library_and_data(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    findings = size_checker.check(repo_root)

    ours = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001"
        and str(field(f, "message")).startswith("widget:")
    ]
    assert len(ours) == 1, findings
    finding = ours[0]
    assert field(finding, "severity") == "warn"
    message = field(finding, "message")
    assert "interface_surface" in message
    assert "11" in message
    assert message == (
        "widget: interface_surface is 11, above the warn threshold of 10 "
        "(specs/architecture/size-caps.md)"
    )