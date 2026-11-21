# hotdocs-criterion: sha256:e5a98f3234feadadc831c84cd0f4f25e723317dc709919c79c7e9952696c879f
import spec_linter

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRODUCT_FOO = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo works\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Foo works\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A foo can be made.\n"
    "\n"
    "### CS-FOO-001\n"
    "Covers: P-FOO\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When a foo is made\n"
    "Then it exists\n"
    "```\n"
)

COMPONENT_BODY = (
    "\n"
    "## Purpose\n"
    "\n"
    "Makes a thing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "**In scope:** making a thing. **Out of scope:** everything else.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "No deltas from `specs/glossary.md`.\n"
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
    "None.\n"
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
    "None.\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial draft.\n"
)

COMPONENT_FOO = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-FOO]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo\n"
    + COMPONENT_BODY
)

R_FOO = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIB_FOO = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    "```\n"
    "make_foo() -> str\n"
    "```\n"
)

AC_FOO = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When make_foo() is called\n"
    "Then the result is \"foo\"\n"
    "```\n"
)

CONSTRAINTS_FOO = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)

COMPONENT_KIND_DEMO = (
    "---\n"
    "id: comp-kind-demo\n"
    "title: Demo kind adapter\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/kind-demo/\n"
    "---\n"
    "\n"
    "# Demo kind adapter\n"
    + COMPONENT_BODY
)

SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]


def definition_text():
    text = (
        "---\n"
        "id: arch-asset-kind-demo\n"
        "title: Asset Kind demo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Asset Kind demo\n"
    )
    for name in SECTIONS:
        text = text + "\n## " + name + "\n\nOne line of text about " + name.lower() + ".\n"
    return text


def web_component_text(assets_line):
    return (
        "---\n"
        "id: comp-web\n"
        "title: Web\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: [comp-kind-demo]\n"
        + assets_line + "\n"
        "sealed: true\n"
        "source_path: legacy/web/\n"
        "---\n"
        "\n"
        "# Web\n"
        + COMPONENT_BODY
    )


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def build_corpus(root, assets_line):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    write(root, "specs/components/foo/component.md", COMPONENT_FOO)
    write(root, "specs/components/foo/requirements/R-FOO-001.md", R_FOO)
    write(root, "specs/components/foo/interface/library.md", LIB_FOO)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", AC_FOO)
    write(root, "specs/components/foo/constraints.md", CONSTRAINTS_FOO)
    write(root, "specs/components/kind-demo/component.md", COMPONENT_KIND_DEMO)
    write(root, "specs/architecture/asset-kind-demo.md", definition_text())
    web_text = web_component_text(assets_line)
    write(root, "specs/components/web/component.md", web_text)
    assets_line_no = None
    for i, line in enumerate(web_text.splitlines(), start=1):
        if line.startswith("assets:"):
            assets_line_no = i
            break
    return assets_line_no


def r034(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-034"]


def test_valid_asset_has_no_r_lint_034_finding(tmp_path):
    build_corpus(tmp_path, "assets: [demo:static/app.js]")
    report = spec_linter.lint(None, tmp_path)
    found = r034(report)
    assert found == [], [field(f, "message") for f in found]


def test_invalid_asset_entries_each_reported_in_order(tmp_path):
    entries = [
        "demo",
        "Demo:a.js",
        "demo:/abs.js",
        "demo:a\\b.js",
        "demo:x/../y.js",
        "demo:static/m.py",
        "python:pkg",
    ]
    line_no = build_corpus(tmp_path, "assets: [" + ", ".join(entries) + "]")
    report = spec_linter.lint(None, tmp_path)
    found = r034(report)
    web = [f for f in found if field(f, "file") == "specs/components/web/component.md"]
    expected = [
        "asset 'demo' is not <kind>:<path>",
        "asset 'Demo:a.js' is not <kind>:<path>",
        "asset 'demo:/abs.js': path must be relative with / separators",
        "asset 'demo:a\\b.js': path must be relative with / separators",
        "asset 'demo:x/../y.js': path contains ..",
        "asset 'demo:static/m.py': path ends in .py",
        "asset 'python:pkg': python is never declared",
    ]
    fails = [f for f in web if field(f, "severity") == "fail"]
    assert [field(f, "message") for f in fails] == expected
    assert len(web) == len(expected)
    for f in fails:
        assert field(f, "line") == line_no


def test_assets_not_a_list(tmp_path):
    line_no = build_corpus(tmp_path, "assets: demo:static/app.js")
    report = spec_linter.lint(None, tmp_path)
    found = r034(report)
    assert [field(f, "message") for f in found] == [
        "assets must be a list of <kind>:<path> strings"
    ]
    only = found[0]
    assert field(only, "severity") == "fail"
    assert field(only, "file") == "specs/components/web/component.md"
    assert field(only, "line") == line_no