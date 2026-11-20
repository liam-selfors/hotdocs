# hotdocs-criterion: sha256:ac35c7139d5812302dd78e60b5e23083804b75a7c380065e7d9bdbd5ad6292ef
from pathlib import Path

import spec_linter


SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]

WEB_REL = "specs/components/web/component.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _component_md(comp_id, title, extra_lines):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [team]",
        "sealed: true",
        "source_path: legacy/" + comp_id + "/",
    ]
    lines.extend(extra_lines)
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("A small fixture component.")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- In scope: fixtures.")
    lines.append("")
    lines.append("## Definitions")
    lines.append("")
    lines.append("None.")
    lines.append("")
    lines.append("## Open questions")
    lines.append("")
    lines.append("## Change log")
    lines.append("")
    lines.append("- Initial.")
    lines.append("")
    return "\n".join(lines)


def _build(repo_root, assets_line):
    repo_root = Path(repo_root)
    web_dir = repo_root / "specs" / "components" / "web"
    web_dir.mkdir(parents=True)
    web_text = _component_md(
        "comp-web",
        "Web",
        ["depends_on: [comp-kind-demo]", assets_line],
    )
    (web_dir / "component.md").write_text(web_text)

    kd_dir = repo_root / "specs" / "components" / "kind-demo"
    kd_dir.mkdir(parents=True)
    (kd_dir / "component.md").write_text(
        _component_md("comp-kind-demo", "Kind Demo", [])
    )

    arch_dir = repo_root / "specs" / "architecture"
    arch_dir.mkdir(parents=True)
    parts = [
        "---",
        "id: arch-asset-kind-demo",
        "title: Asset Kind Demo",
        "status: draft",
        "owners: [team]",
        "---",
        "",
        "# Asset Kind Demo",
        "",
    ]
    for name in SECTIONS:
        parts.append("## " + name)
        parts.append("")
        parts.append("Some text for " + name + ".")
        parts.append("")
    (arch_dir / "asset-kind-demo.md").write_text("\n".join(parts))

    assets_line_no = None
    for i, line in enumerate(web_text.splitlines(), start=1):
        if line.startswith("assets:"):
            assets_line_no = i
            break
    assert assets_line_no is not None
    return assets_line_no


def _lint034(repo_root):
    report = spec_linter.lint(None, Path(repo_root))
    return [
        f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-034"
    ]


def test_valid_assets_have_no_r_lint_034_finding(tmp_path):
    _build(tmp_path, "assets: [demo:static/app.js]")
    findings = _lint034(tmp_path)
    assert findings == [], [field(f, "message") for f in findings]


def test_invalid_entries_reported_in_order(tmp_path):
    entries = [
        "demo",
        "Demo:a.js",
        "demo:/abs.js",
        "demo:a\\b.js",
        "demo:x/../y.js",
        "demo:static/m.py",
        "python:pkg",
    ]
    line_no = _build(tmp_path, "assets: [" + ", ".join(entries) + "]")
    findings = _lint034(tmp_path)

    expected = [
        "asset 'demo' is not <kind>:<path>",
        "asset 'Demo:a.js' is not <kind>:<path>",
        "asset 'demo:/abs.js': path must be relative with / separators",
        "asset 'demo:a\\b.js': path must be relative with / separators",
        "asset 'demo:x/../y.js': path contains ..",
        "asset 'demo:static/m.py': path ends in .py",
        "asset 'python:pkg': python is never declared",
    ]

    web_findings = [f for f in findings if field(f, "file") == WEB_REL]
    assert [field(f, "message") for f in web_findings] == expected
    for f in web_findings:
        assert field(f, "severity") == "fail"
        assert field(f, "line") == line_no
    # No R-LINT-034 findings elsewhere either
    assert len(findings) == len(web_findings)


def test_assets_not_a_list(tmp_path):
    line_no = _build(tmp_path, "assets: demo:static/app.js")
    findings = _lint034(tmp_path)
    assert [field(f, "message") for f in findings] == [
        "assets must be a list of <kind>:<path> strings"
    ]
    f = findings[0]
    assert field(f, "severity") == "fail"
    assert field(f, "file") == WEB_REL
    assert field(f, "line") == line_no