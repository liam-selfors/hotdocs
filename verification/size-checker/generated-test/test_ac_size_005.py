# hotdocs-criterion: sha256:65fc3a59049fff0955dd5b840cb4e4fe658eabd60ffcd96cc0876bc0d0a7c7a4
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
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — The widget MUST do a small thing.\n",
    )

    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "Given a widget\n"
        "When it runs\n"
        "Then it does a small thing\n",
    )

    # CLI: three non-blank logical lines (one joined via a trailing
    # backslash onto a fourth physical line) and one blank line -> 3
    cli_lines = [
        "widget run",
        "widget build --fast \\",
        "    --verbose",
        "",
        "widget clean",
    ]
    write(
        comp / "interface" / "cli.md",
        "# CLI\n"
        "\n"
        "```\n" + "\n".join(cli_lines) + "\n```\n"
        "\n"
        "Some prose after the block.\n",
    )

    # Library: five signature lines plus one prose line -> 5
    lib_lines = [
        "alpha(x: int) -> int",
        "beta(name: str) -> str",
        "gamma() -> None",
        "delta(a: int, b: int) -> list[int]",
        "epsilon(path: Path) -> dict",
        "These functions do small things.",
    ]
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n" + "\n".join(lib_lines) + "\n```\n"
        "\n"
        "Some prose after the block.\n",
    )

    # Data: three files -> 3
    for name in ("Alpha", "Beta", "Gamma"):
        write(
            comp / "interface" / "data" / (name + ".md"),
            "# " + name + "\n"
            "\n"
            "A small data shape.\n",
        )


def test_ac_size_005_interface_surface_warn(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size_001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    widget_001 = [
        f
        for f in size_001
        if str(field(f, "message")).startswith("widget:")
        or "components/widget" in str(field(f, "file"))
    ]

    assert len(widget_001) == 1, findings
    finding = widget_001[0]
    assert field(finding, "severity") == "warn"
    message = field(finding, "message")
    assert "interface_surface" in message
    assert "11" in message
    assert message == (
        "widget: interface_surface is 11, above the warn threshold of 10 "
        "(specs/architecture/size-caps.md)"
    )
    assert isinstance(field(finding, "line"), int)