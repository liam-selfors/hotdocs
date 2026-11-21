# hotdocs-criterion: sha256:11bfab248ed1f7ca446c9f70b44bfd1a104f75666cd7f8a78d529ac8e456ea5f
import re
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_gen():
    return next(
        p for p in Path(spec_linter.__file__).resolve().parents if p.name == "gen"
    )


PRODUCT = """---
id: P-FOO
title: Foo works
status: draft
owners: [team-a]
---

# Foo works

## Purpose

A foo can be made.

### CS-FOO-001
Covers: P-FOO
Kind: generated-test

```gherkin
Given nothing
When a foo is made
Then it exists
```
"""


def _component_md(slug, title, upper):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes a " + slug + ".\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** making a " + slug + ". **Out of scope:** everything else.\n"
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


def _write_component(repo_root, slug, title, upper, func, module):
    base = repo_root / "specs" / "components" / slug
    (base / "requirements").mkdir(parents=True)
    (base / "interface").mkdir(parents=True)
    (base / "acceptance").mkdir(parents=True)
    (base / "component.md").write_text(_component_md(slug, title, upper))
    (base / "requirements" / ("R-" + upper + "-001.md")).write_text(
        "# R-" + upper + "-001\n\n"
        "**R-" + upper + "-001** — `" + func + "()` MUST return the string `\"" + slug + "\"`.\n"
    )
    (base / "interface" / "library.md").write_text(
        "# Library\n\n"
        "One module file, `" + module + ".py`.\n\n"
        "```\n" + func + "() -> str\n```\n"
    )
    (base / "acceptance" / ("AC-" + upper + "-001.md")).write_text(
        "# AC-" + upper + "-001\n\n"
        "Covers: R-" + upper + "-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given nothing\n"
        "When " + func + "() is called\n"
        "Then the result is \"" + slug + "\"\n"
        "```\n"
    )
    (base / "constraints.md").write_text(
        "# " + title + " — Non-Functional Constraints\n\n- **Pure.** No I/O.\n"
    )


def _build_project(repo_root):
    (repo_root / "specs" / "product").mkdir(parents=True)
    (repo_root / "specs" / "product" / "foo.md").write_text(PRODUCT)
    _write_component(repo_root, "foo", "Foo", "FOO", "make_foo", "foo")
    _write_component(
        repo_root,
        "cache-manager",
        "Cache Manager",
        "CACHE",
        "make_cache_manager",
        "cache_manager",
    )


def _r032(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-032"]


def _preconditions():
    gen = _tool_gen()
    assert (gen / "cache-manager").is_dir(), "tool gen/ must hold cache-manager"
    assert not (gen / "foo").exists(), "tool gen/ must not hold foo"
    return gen


def test_project_component_shadowing_tool_component_fails(tmp_path):
    _preconditions()
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _build_project(repo_root)

    # Precondition: without the marker, the corpus lints clean.
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    (repo_root / ".hotdocs-tool.json").write_text("{}\n")
    report = spec_linter.lint(None, repo_root)
    findings = _r032(report)

    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "severity") == "fail"
    assert "cache-manager" in field(finding, "message")

    for f in findings:
        assert not str(field(f, "file")).startswith("specs/components/foo/")
        assert not re.search(r"(?<![\w-])foo(?![\w-])", field(f, "message"))

    assert report.hard_failures >= 1


def test_project_without_marker_has_no_r_lint_032(tmp_path):
    _preconditions()
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _build_project(repo_root)
    assert not (repo_root / ".hotdocs-tool.json").exists()

    report = spec_linter.lint(None, repo_root)
    assert _r032(report) == []


def test_tool_own_repository_has_no_r_lint_032():
    gen = _preconditions()
    tool_root = gen.parent
    if not (tool_root / "specs").is_dir():
        pytest.skip("tool repository has no specs/ tree to lint")
    if (tool_root / ".hotdocs-tool.json").exists():
        pytest.skip("tool root unexpectedly carries .hotdocs-tool.json")
    report = spec_linter.lint(None, tool_root)
    assert _r032(report) == []