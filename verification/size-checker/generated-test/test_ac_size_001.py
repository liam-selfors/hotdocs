"""AC-SIZE-001 (Covers: R-SIZE-001).

Given a component whose generated-code LOC estimate exceeds 1500
When check(repo_root) runs on it
Then the report contains a fail-severity finding for rule R-SIZE-001 whose
message names the dimension `generated_code_loc`.
"""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path, slug: str, code_lines: int) -> Path:
    upper = slug.upper()

    # Product capability the component realizes.
    _write(
        root / "specs" / "product" / "demo.md",
        "---\n"
        "id: P-demo\n"
        "title: Demo capability\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# Demo capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small demo capability for testing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: demo behavior.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-DEMO-001\n"
        "\n"
        "Covers: P-demo\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a demo\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )

    comp = root / "specs" / "components" / slug
    _write(
        comp / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()}\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-demo]\n"
        "---\n"
        "\n"
        f"# {slug.capitalize()}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Does a small thing for the test.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the small thing.\n"
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
        "- Initial.\n",
    )
    _write(
        comp / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n"
        f"**R-{upper}-001** — The component MUST do the small thing.\n",
    )
    _write(
        comp / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\n"
        f"Covers: R-{upper}-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndo_thing(x: int) -> int\n```\n\nDoes the thing.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n- Fast enough: under 1s, measured by a timer.\n",
    )

    # Generated code: exactly `code_lines` counted lines, plus blanks and
    # comments that must not count.
    lines = ["# header comment, not counted", ""]
    for i in range(code_lines):
        lines.append(f"value_{i} = {i}")
        if i % 100 == 0:
            lines.append("")
            lines.append("    # indented comment, not counted")
    _write(
        root / "gen" / slug / f"{slug.replace('-', '_')}.py",
        "\n".join(lines) + "\n",
    )
    return root


def _fail_loc_findings(findings):
    out = []
    for f in findings:
        if (
            field(f, "rule_id") == "R-SIZE-001"
            and field(f, "severity") == "fail"
            and "generated_code_loc" in str(field(f, "message"))
        ):
            out.append(f)
    return out


def test_generated_code_loc_over_1500_is_fail_finding(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", "widget", 1601)

    findings = size_checker.check(repo_root)
    findings = list(findings)

    matches = _fail_loc_findings(findings)
    assert matches, (
        "expected a fail-severity R-SIZE-001 finding naming "
        f"generated_code_loc, got: {findings!r}"
    )
    for f in matches:
        assert field(f, "severity") == "fail"
        assert field(f, "rule_id") == "R-SIZE-001"
        assert isinstance(field(f, "line"), int)
        assert isinstance(field(f, "file"), str)
        assert not Path(field(f, "file")).is_absolute()


def test_generated_code_loc_at_1500_is_not_fail_finding(tmp_path):
    # Boundary: hard fail is strictly *above* 1500.
    repo_root = _build_repo(tmp_path / "repo", "widget", 1500)

    findings = list(size_checker.check(repo_root))

    assert _fail_loc_findings(findings) == [], (
        "1500 LOC must not produce a fail-severity generated_code_loc "
        f"finding, got: {findings!r}"
    )