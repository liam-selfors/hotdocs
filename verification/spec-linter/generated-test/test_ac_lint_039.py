# hotdocs-criterion: sha256:c546d81e6b85449b549167353193021a7b21d5b899c59bfcb0b8d1e94ca1ad9d
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(comp_id, title, extra_lines):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [pipeline-team]",
    ]
    lines.extend(extra_lines)
    lines.extend([
        "sealed: true",
        "source_path: legacy/" + comp_id + "/",
        "---",
        "",
        "# " + title,
        "",
        "## Purpose",
        "",
        "A fixture component.",
        "",
        "## Scope",
        "",
        "- In scope: fixture only.",
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
        "- Initial draft.",
        "",
    ])
    return "\n".join(lines)


def definition_md():
    lines = [
        "---",
        "id: arch-asset-kind-demo",
        "title: Asset Kind demo",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "---",
        "",
        "# Asset Kind demo",
        "",
    ]
    for name in SECTIONS:
        lines.append("## " + name)
        lines.append("")
        lines.append("Text for " + name + ".")
        lines.append("")
    return "\n".join(lines)


def build_corpus(repo_root, assets_line):
    repo_root = Path(repo_root)
    (repo_root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "vars").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "decisions").mkdir(parents=True, exist_ok=True)
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Fixture** — a test fixture.\n")
    write(repo_root / "specs" / "architecture" / "asset-kind-demo.md", definition_md())
    write(
        repo_root / "specs" / "components" / "kind-demo" / "component.md",
        component_md("comp-kind-demo", "Kind demo", ["depends_on: []"]),
    )
    write(
        repo_root / "specs" / "components" / "web" / "component.md",
        component_md("comp-web", "Web", ["depends_on: [comp-kind-demo]", assets_line]),
    )
    return repo_root


def assets_line_number(repo_root):
    text = (Path(repo_root) / WEB_REL).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), start=1):
        if line.startswith("assets:"):
            return i
    raise AssertionError("no assets line")


def lint034(repo_root):
    report = spec_linter.lint(None, repo_root)
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-034"]


def test_valid_assets_have_no_r_lint_034_finding(tmp_path):
    repo_root = build_corpus(tmp_path, "assets: [demo:static/app.js]")
    findings = lint034(repo_root)
    assert findings == [], [field(f, "message") for f in findings]


def test_invalid_entries_reported_in_order(tmp_path):
    line = (
        "assets: [demo, Demo:a.js, demo:/abs.js, demo:a" + "\\" + "b.js, "
        "demo:x/../y.js, demo:static/m.py, python:pkg]"
    )
    repo_root = build_corpus(tmp_path, line)
    findings = lint034(repo_root)
    expected = [
        "asset 'demo' is not <kind>:<path>",
        "asset 'Demo:a.js' is not <kind>:<path>",
        "asset 'demo:/abs.js': path must be relative with / separators",
        "asset 'demo:a" + "\\" + "b.js': path must be relative with / separators",
        "asset 'demo:x/../y.js': path contains ..",
        "asset 'demo:static/m.py': path ends in .py",
        "asset 'python:pkg': python is never declared",
    ]
    assert [field(f, "message") for f in findings] == expected
    expected_line = assets_line_number(repo_root)
    for f in findings:
        assert field(f, "file") == WEB_REL
        assert field(f, "severity") == "fail"
        assert field(f, "line") == expected_line


def test_assets_not_a_list(tmp_path):
    repo_root = build_corpus(tmp_path, "assets: demo:static/app.js")
    findings = lint034(repo_root)
    assert [field(f, "message") for f in findings] == [
        "assets must be a list of <kind>:<path> strings"
    ]
    f = findings[0]
    assert field(f, "file") == WEB_REL
    assert field(f, "severity") == "fail"
    assert field(f, "line") == assets_line_number(repo_root)