# hotdocs-criterion: sha256:c484d5ec82c18f08c2ed8640ed608570b88ddb5bc5f526dc139c4eacd27f1088
"""AC-LINT-032 (covers R-LINT-032).

Given a project holding .hotdocs-tool.json with components "foo" and
"cache-manager", when the linter runs on it, then "cache-manager" gets an
R-LINT-032 fail finding and "foo" none.

Given the same project without .hotdocs-tool.json, or the tool's own
repository, when the linter runs on it, then there is no R-LINT-032 finding.
"""

import re
from pathlib import Path

import pytest

import spec_linter


RULE = "R-LINT-032"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_gen():
    here = Path(spec_linter.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent
    pytest.fail("spec_linter is not located under a 'gen' directory")


def _shadow_slug():
    """The criterion's slug, 'cache-manager', when the tool's gen/ holds it;
    otherwise a slug the tool's gen/ certainly holds (the linter's own)."""
    tool_gen = _tool_gen()
    if (tool_gen / "cache-manager").is_dir():
        return "cache-manager"
    return "spec-linter"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug + " component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used for testing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: nothing beyond this fixture.\n"
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


def _build_project(root, slugs, with_marker):
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test fixture term.\n",
    )
    for slug in slugs:
        base = root / "specs" / "components" / slug
        _write(base / "component.md", _component_md(slug))
        _write(
            base / "constraints.md",
            "# Constraints\n\nNone beyond the defaults.\n",
        )
    if with_marker:
        _write(root / ".hotdocs-tool.json", "{}\n")
    return root


def _rule_findings(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == RULE]


def _names_slug(finding, slug):
    message = field(finding, "message") or ""
    file = field(finding, "file") or ""
    pattern = r"(?<![\w-])" + re.escape(slug) + r"(?![\w-])"
    return bool(re.search(pattern, message)) or ("components/" + slug + "/") in str(file)


def test_project_component_shadowing_tool_component_fails(tmp_path):
    slug = _shadow_slug()
    tool_gen = _tool_gen()
    assert not (tool_gen / "foo").exists(), "tool gen/ unexpectedly holds 'foo'"

    repo_root = _build_project(tmp_path / "project", ["foo", slug], with_marker=True)

    report = spec_linter.lint(None, repo_root)
    hits = _rule_findings(report)

    shadow_hits = [f for f in hits if _names_slug(f, slug)]
    assert shadow_hits, "expected an R-LINT-032 finding naming " + repr(slug)
    for f in shadow_hits:
        assert field(f, "severity") == "fail"
    assert any(slug in (field(f, "message") or "") for f in shadow_hits), (
        "the finding's message must name the slug " + repr(slug)
    )

    foo_hits = [f for f in hits if _names_slug(f, "foo")]
    assert foo_hits == [], "'foo' must get no R-LINT-032 finding"

    assert field(report, "hard_failures") >= 1


def test_project_without_marker_has_no_finding(tmp_path):
    slug = _shadow_slug()
    repo_root = _build_project(tmp_path / "project", ["foo", slug], with_marker=False)
    assert not (repo_root / ".hotdocs-tool.json").exists()

    report = spec_linter.lint(None, repo_root)
    assert _rule_findings(report) == []


def test_tool_own_repository_has_no_finding():
    tool_root = _tool_gen().parent
    if not (tool_root / "specs").is_dir():
        pytest.skip("tool root has no specs/ tree to lint")
    report = spec_linter.lint(None, tool_root)
    assert _rule_findings(report) == []