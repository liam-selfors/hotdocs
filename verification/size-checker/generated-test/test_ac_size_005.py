# hotdocs-criterion: sha256:2d1813e49625aa4012b2abf101acdb05553972725d4857530022d5fa07f553ab
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FENCE = "```"


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a small fixture thing.\n",
    )
    comp = specs / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: fixtures.\n"
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
        "- Created.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget MUST exist.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n\n"
        "The widget exists.\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    # cli.md: three non-blank logical lines (one physical line ends in a
    # backslash, joining a fourth physical line), plus one blank line.
    write(
        comp / "interface" / "cli.md",
        "# CLI\n\n"
        + FENCE + "\n"
        "widget run --fast \\\n"
        "    --target=x\n"
        "\n"
        "widget list\n"
        "widget show <name>\n"
        + FENCE + "\n",
    )
    # library.md: five signature lines and one prose line.
    write(
        comp / "interface" / "library.md",
        "# Library\n\n"
        + FENCE + "\n"
        "alpha(x: int) -> int\n"
        "beta(name: str) -> str\n"
        "gamma() -> None\n"
        "delta(a: int, b: int) -> list[int]\n"
        "epsilon(path: Path) -> dict\n"
        "This prose line describes the functions above.\n"
        + FENCE + "\n",
    )
    for name in ("Alpha", "Beta", "Gamma"):
        write(
            comp / "interface" / "data" / (name + ".md"),
            "# " + name + "\n\nA fixture type.\n",
        )


def test_ac_size_005_interface_surface_warn_at_eleven(tmp_path):
    repo_root = Path(tmp_path)
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size_findings = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    assert len(size_findings) == 1, size_findings

    finding = size_findings[0]
    assert field(finding, "severity") == "warn"
    message = field(finding, "message")
    assert "interface_surface" in message
    assert "11" in message
    assert isinstance(field(finding, "line"), int)