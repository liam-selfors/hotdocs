# hotdocs-criterion: sha256:e5e7f939e39f3ae739e713bd43abb4e8ca74ec5286ba491dc2df7c1db168f42b
"""AC-LINT-005: a sealed component with no source_path gets a fail-severity
R-LINT-005 finding."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, extra_frontmatter):
    return (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [test-team]\n"
        + extra_frontmatter
        + "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Matches existing behavior; do not regenerate.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: existing behavior.\n"
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
        "- Initial draft.\n"
    )


def _make_component(repo_root, slug, upper, extra_frontmatter):
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        _component_md("comp-" + slug, slug.capitalize() + " Component", extra_frontmatter),
    )
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The component MUST match existing behavior.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given the existing code\n"
        "When it runs\n"
        "Then it matches existing behavior\n"
        "```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\nNone beyond existing behavior.\n",
    )


def _build_fixture(repo_root):
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing used in tests.\n",
    )
    # The component under test: sealed: true, no source_path.
    _make_component(repo_root, "foo", "FOO", "sealed: true\n")
    # A control: sealed: true with a source_path, which R-LINT-005 accepts.
    _make_component(repo_root, "bar", "BAR", "sealed: true\nsource_path: legacy/bar/\n")


FOO_FILE = "specs/components/foo/component.md"
BAR_FILE = "specs/components/bar/component.md"


def _norm(p):
    return str(p).replace("\\", "/")


def test_lint_reports_fail_for_sealed_without_source_path(tmp_path):
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    r005 = [f for f in findings if field(f, "rule_id") == "R-LINT-005"]
    foo_r005 = [f for f in r005 if _norm(field(f, "file")).endswith(FOO_FILE)]

    assert foo_r005, (
        "expected an R-LINT-005 finding for " + FOO_FILE + ", got: " + repr(findings)
    )
    assert any(field(f, "severity") == "fail" for f in foo_r005), repr(foo_r005)

    # The correctly-sealed control component must not trigger R-LINT-005.
    bar_r005 = [f for f in r005 if _norm(field(f, "file")).endswith(BAR_FILE)]
    assert bar_r005 == [], repr(bar_r005)

    assert field(report, "hard_failures") >= 1


def test_cli_lint_json_reports_fail_for_sealed_without_source_path(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    findings = doc["findings"]
    foo_r005 = [
        f
        for f in findings
        if f["rule_id"] == "R-LINT-005" and _norm(f["file"]).endswith(FOO_FILE)
    ]
    assert foo_r005, repr(findings)
    assert any(f["severity"] == "fail" for f in foo_r005), repr(foo_r005)
    assert doc["summary"]["hard_failures"] >= 1