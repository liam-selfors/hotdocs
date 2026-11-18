# hotdocs-criterion: sha256:01a445c3cb51513fee68906229ba1414e124bcb4dc27e37918c3d1d02714e4ae
"""AC-LINT-033: lint folds in citation-checker's and size-checker's findings
as Findings, and load_corpus is corpus-loader's function re-exported."""

import dataclasses
from pathlib import Path

import spec_linter


COMPONENT_REL = "specs/components/foo/component.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _component_md(purpose_text, rationale_text):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose_text
        + "\n"
        "\n"
        "## Rationale\n"
        "\n"
        + rationale_text
        + "\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: returning a widget.\n"
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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, with_problems):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing the foo component returns.\n",
    )
    comp = specs / "components" / "foo"
    if with_problems:
        purpose = " ".join(["word"] * 160)
        rationale = "This design follows `D999`, which was decided earlier."
    else:
        purpose = "Foo returns a widget to its caller."
        rationale = "Kept deliberately small."
    _write(comp / "component.md", _component_md(purpose, rationale))
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST return a widget.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the foo component\n"
        "When it is asked for a widget\n"
        "Then it returns a widget\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n- None beyond defaults; measured by review.\n",
    )


def _norm(p):
    return str(p).replace("\\", "/")


def _is_finding(obj):
    finding_cls = getattr(spec_linter, "Finding", None)
    if finding_cls is not None and isinstance(obj, finding_cls):
        return True
    return type(obj).__name__ == "Finding" and dataclasses.is_dataclass(obj)


def test_clean_base_corpus_lints_clean(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, with_problems=False)
    report = spec_linter.lint(None, repo_root)
    failures = [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in field(report, "findings")
        if field(f, "severity") == "fail"
    ]
    assert field(report, "hard_failures") == 0, failures


def test_lint_includes_citation_and_size_findings(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, with_problems=True)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    cite = [
        f for f in findings
        if field(f, "rule_id") == "R-CITE-001"
        and field(f, "severity") == "fail"
        and _norm(field(f, "file")) == COMPONENT_REL
    ]
    size = [
        f for f in findings
        if field(f, "rule_id") == "R-SIZE-004"
        and field(f, "severity") == "fail"
        and _norm(field(f, "file")) == COMPONENT_REL
    ]
    summary = [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
        for f in findings
    ]
    assert len(cite) == 1, summary
    assert len(size) == 1, summary
    assert _is_finding(cite[0]), type(cite[0])
    assert _is_finding(size[0]), type(size[0])

    # citation-checker's findings come before size-checker's
    assert findings.index(cite[0]) < findings.index(size[0])

    assert field(report, "hard_failures") == 2, summary


def test_load_corpus_returns_corpus_with_component(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, with_problems=True)

    assert callable(spec_linter.load_corpus)
    assert spec_linter.load_corpus.__name__ == "load_corpus"

    corpus = spec_linter.load_corpus(repo_root)
    assert type(corpus).__name__ == "Corpus"
    components = field(corpus, "components")
    assert "foo" in components
    root = field(components["foo"], "root")
    assert root is not None
    assert _norm(field(root, "rel_path")) == COMPONENT_REL