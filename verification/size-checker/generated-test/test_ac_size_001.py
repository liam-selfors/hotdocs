# hotdocs-criterion: sha256:62658c384b0d81e29bde1789ebe40feca12058f202b351fc9d316ae8691ba8c1
"""AC-SIZE-001 (covers R-SIZE-001).

Given a component whose generated-code LOC estimate exceeds 1500
When check(repo_root) runs on it
Then the report contains a fail-severity finding for rule R-SIZE-001 whose
message names the dimension `generated_code_loc`.
"""

from pathlib import Path

import size_checker


BIG = "big-widget"
EDGE = "edge-widget"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str, title: str) -> str:
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Does one small thing for the test fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the one thing.\n"
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
        "- Initial fixture.\n"
    )


def _write_component(repo_root: Path, slug: str, title: str, tag: str) -> None:
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, title))
    _write(
        base / "requirements" / f"R-{tag}-001.md",
        f"# R-{tag}-001\n\n**R-{tag}-001** — The widget MUST do its one thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{tag}-001.md",
        f"# AC-{tag}-001\n\n"
        f"Covers: R-{tag}-001\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it runs\n"
        "Then it does its one thing\n"
        "```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\n- None beyond the defaults.\n",
    )


def _code_lines(prefix: str, count: int) -> list:
    return [f"{prefix}_{i} = {i}" for i in range(count)]


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets exist.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Widgets.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given the system\n"
        "When a widget is used\n"
        "Then it works\n"
        "```\n",
    )

    _write_component(repo_root, BIG, "Big Widget", "BIGW")
    _write_component(repo_root, EDGE, "Edge Widget", "EDGEW")

    # Big component: 1600 counted lines split across two files in a package,
    # one nested deeper, each alone under 1500 — total exceeds 1500.
    big_pkg = repo_root / "gen" / BIG / "big_widget"
    first = ["# a leading comment", ""] + _code_lines("a", 800) + ["", "   # indented comment"]
    second = ["", "# header comment"] + _code_lines("b", 800) + [""]
    _write(big_pkg / "__init__.py", "\n".join(first) + "\n")
    _write(big_pkg / "sub" / "more.py", "\n".join(second) + "\n")

    # Edge component: exactly 1500 counted lines, padded with many blank and
    # comment-only lines that must not count — must not hard-fail.
    edge_lines = []
    for i, line in enumerate(_code_lines("c", 1500)):
        edge_lines.append(line)
        if i % 5 == 0:
            edge_lines.append("")
            edge_lines.append("# a comment line")
            edge_lines.append("    # an indented comment line")
            edge_lines.append("   ")
    _write(repo_root / "gen" / EDGE / "edge_widget.py", "\n".join(edge_lines) + "\n")


def _about(finding, slug: str) -> bool:
    file_value = str(_field(finding, "file") or "")
    message = str(_field(finding, "message") or "")
    return slug in file_value or slug in message


def _loc_findings(findings, slug: str, severity: str) -> list:
    out = []
    for f in findings:
        if _field(f, "rule_id") != "R-SIZE-001":
            continue
        if _field(f, "severity") != severity:
            continue
        if "generated_code_loc" not in str(_field(f, "message") or ""):
            continue
        if not _about(f, slug):
            continue
        out.append(f)
    return out


def test_ac_size_001_generated_code_loc_over_1500_is_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = size_checker.check(repo_root)
    findings = list(findings)

    matching = _loc_findings(findings, BIG, "fail")
    assert matching, (
        "expected a fail-severity R-SIZE-001 finding naming generated_code_loc "
        f"for {BIG}; got: {findings!r}"
    )

    for f in matching:
        assert _field(f, "rule_id") == "R-SIZE-001"
        assert _field(f, "severity") == "fail"
        assert "generated_code_loc" in str(_field(f, "message"))
        line = _field(f, "line")
        assert isinstance(line, int) and not isinstance(line, bool)
        assert line >= 1
        file_value = _field(f, "file")
        assert isinstance(file_value, str)
        assert not Path(file_value).is_absolute()


def test_ac_size_001_findings_have_documented_shape(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = list(size_checker.check(repo_root))
    assert findings
    for f in findings:
        assert _field(f, "severity") in ("fail", "warn")
        assert isinstance(_field(f, "rule_id"), str)
        assert isinstance(_field(f, "message"), str)
        if isinstance(f, dict):
            assert set(f.keys()) == {"rule_id", "severity", "file", "line", "message"}


def test_ac_size_001_exactly_1500_loc_with_padding_is_not_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = list(size_checker.check(repo_root))

    assert not _loc_findings(findings, EDGE, "fail"), (
        f"{EDGE} has exactly 1500 counted lines (blank/comment lines excluded) "
        f"and must not hard-fail generated_code_loc; got: {findings!r}"
    )
    assert _loc_findings(findings, EDGE, "warn"), (
        f"{EDGE} has 1500 counted lines (> 800) and should warn on "
        f"generated_code_loc; got: {findings!r}"
    )