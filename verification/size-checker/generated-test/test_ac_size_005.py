# hotdocs-criterion: sha256:2d1813e49625aa4012b2abf101acdb05553972725d4857530022d5fa07f553ab
"""AC-SIZE-005 (covers R-SIZE-001): interface_surface counts joined CLI
lines, library signature lines and interface/data files, and reports a
single warn when the total (11) is above the warn cap (10) and not above
the fail cap (20)."""

import re
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
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a fixture term.\n",
    )
    comp = specs / "components" / "widget"
    write(
        comp / "component.md",
        "\n".join(
            [
                "---",
                "id: comp-widget",
                "title: Widget",
                "status: draft",
                "owners: [alice]",
                "sealed: true",
                "source_path: legacy/widget/",
                "---",
                "",
                "# Widget",
                "",
                "## Purpose",
                "",
                "Does widget things for the fixture.",
                "",
                "## Scope",
                "",
                "- In scope: widgets.",
                "",
                "## Definitions",
                "",
                "None.",
                "",
                "## Behavior",
                "",
                "See `requirements/`.",
                "",
                "## Interfaces",
                "",
                "See `interface/`.",
                "",
                "## Data",
                "",
                "See `interface/data/`.",
                "",
                "## Acceptance criteria",
                "",
                "See `acceptance/`.",
                "",
                "## Non-functional constraints",
                "",
                "See `constraints.md`.",
                "",
                "## Open questions",
                "",
                "## Change log",
                "",
                "- Created.",
                "",
            ]
        ),
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget MUST work.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "\n".join(
            [
                "# AC-WIDGET-001",
                "",
                "Covers: R-WIDGET-001",
                "Kind: compiled",
                "",
                "```gherkin",
                "Given a widget",
                "When it runs",
                "Then it works",
                "```",
                "",
            ]
        ),
    )
    write(
        comp / "constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )
    # cli.md: three non-blank logical lines (one physical line ends in a
    # backslash joining the next), plus one blank line -> 3 elements.
    write(
        comp / "interface" / "cli.md",
        "\n".join(
            [
                "# CLI",
                "",
                "```",
                "widget run --flag \\",
                "  --other value",
                "",
                "widget check",
                "widget help",
                "```",
                "",
            ]
        ),
    )
    # library.md: five signature lines and one prose line -> 5 elements.
    write(
        comp / "interface" / "library.md",
        "\n".join(
            [
                "# Library",
                "",
                "```",
                "alpha(x: int) -> int",
                "beta(y: str) -> str",
                "gamma() -> None",
                "delta(a, b) -> list",
                "epsilon(z: float) -> float",
                "These functions do widget work.",
                "```",
                "",
            ]
        ),
    )
    # interface/data/: three files -> 3 elements. Total = 11.
    for name in ("Alpha", "Beta", "Gamma"):
        write(
            comp / "interface" / "data" / (name + ".md"),
            "# " + name + "\n\nA fixture type.\n",
        )


def test_ac_size_005_interface_surface_warn_11(tmp_path):
    repo_root = Path(tmp_path)
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size_001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    assert len(size_001) == 1, size_001

    finding = size_001[0]
    file_value = str(field(finding, "file")).replace("\\", "/")
    message = str(field(finding, "message"))
    assert "widget" in file_value or "widget" in message, finding
    assert field(finding, "severity") == "warn"
    assert "interface_surface" in message
    assert re.search(r"(?<!\d)11(?!\d)", message), message