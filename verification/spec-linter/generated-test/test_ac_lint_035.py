# hotdocs-criterion: sha256:e1fd88fd8de647f242c6dab7a5413856706674cb44c839008cdada48760cd5fd
"""AC-LINT-035: lint limits its own and citation-/size-checker findings to `paths`."""

import importlib.util
import sys
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _norm(p):
    return str(p).replace("\\", "/")


def _component_md(slug, missing):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: Component " + slug.upper() + "\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: [" + missing + "]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# Component " + slug.upper() + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used for testing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: testing.\n"
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


def _fake_checker_source(log_path, rule_id):
    findings = [
        {
            "rule_id": rule_id,
            "severity": "warn",
            "file": "specs/components/a/component.md",
            "line": 1,
            "message": "fake finding for a component.md",
        },
        {
            "rule_id": rule_id,
            "severity": "warn",
            "file": "specs/components/b/component.md",
            "line": 1,
            "message": "fake finding for b component.md",
        },
        {
            "rule_id": rule_id,
            "severity": "warn",
            "file": "specs/components/b/constraints.md",
            "line": 1,
            "message": "fake finding for b constraints.md",
        },
        {
            "rule_id": rule_id,
            "severity": "warn",
            "file": "specs/glossary.md",
            "line": 1,
            "message": "fake finding for glossary",
        },
    ]
    return (
        "import copy\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_FINDINGS = " + repr(findings) + "\n"
        "\n"
        "def check(repo_root):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write('called\\n')\n"
        "    return copy.deepcopy(_FINDINGS)\n"
    )


def _build_repo(root):
    specs = root / "specs"
    (specs / "components" / "a").mkdir(parents=True)
    (specs / "components" / "b").mkdir(parents=True)
    (specs / "components" / "a" / "component.md").write_text(
        _component_md("a", "comp-does-not-exist-a")
    )
    (specs / "components" / "b" / "component.md").write_text(
        _component_md("b", "comp-does-not-exist-b")
    )
    (specs / "components" / "b" / "constraints.md").write_text(
        "# Constraints\n\nNone.\n"
    )
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Fixture term** — a term used only in tests.\n"
    )

    cite_log = root / "cite.log"
    size_log = root / "size.log"
    cite_dir = root / "gen" / "citation-checker"
    size_dir = root / "gen" / "size-checker"
    cite_dir.mkdir(parents=True)
    size_dir.mkdir(parents=True)
    (cite_dir / "citation_checker.py").write_text(
        _fake_checker_source(cite_log, "R-CITE-FAKE")
    )
    (size_dir / "size_checker.py").write_text(
        _fake_checker_source(size_log, "R-SIZE-FAKE")
    )
    return cite_log, size_log


def test_ac_lint_035(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cite_log, size_log = _build_repo(repo_root)
    monkeypatch.chdir(repo_root)

    # Directory path: everything under specs/components/a/
    report = spec_linter.lint([Path("specs/components/a")], repo_root)
    findings = list(field(report, "findings"))
    assert findings, "expected findings for component a"
    for f in findings:
        assert _norm(field(f, "file")).startswith("specs/components/a/"), (
            "finding outside specs/components/a/: " + repr(f)
        )
    assert any(
        field(f, "rule_id") == "R-LINT-003"
        and _norm(field(f, "file")) == "specs/components/a/component.md"
        for f in findings
    ), "missing R-LINT-003 finding for a/component.md: " + repr(findings)
    # Checker findings within paths are included
    rule_ids_a = [field(f, "rule_id") for f in findings]
    assert "R-CITE-FAKE" in rule_ids_a
    assert "R-SIZE-FAKE" in rule_ids_a
    assert cite_log.is_file() and "called" in cite_log.read_text()
    assert size_log.is_file() and "called" in size_log.read_text()

    # File path: exactly specs/components/b/component.md
    report_b = spec_linter.lint(
        [Path("specs/components/b/component.md")], repo_root
    )
    findings_b = list(field(report_b, "findings"))
    assert findings_b, "expected findings for component b"
    for f in findings_b:
        assert _norm(field(f, "file")) == "specs/components/b/component.md", (
            "finding outside b/component.md: " + repr(f)
        )
    assert any(field(f, "rule_id") == "R-LINT-003" for f in findings_b), (
        "missing R-LINT-003 finding for b/component.md: " + repr(findings_b)
    )
    rule_ids_b = [field(f, "rule_id") for f in findings_b]
    assert "R-CITE-FAKE" in rule_ids_b
    assert "R-SIZE-FAKE" in rule_ids_b