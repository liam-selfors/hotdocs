# hotdocs-criterion: sha256:7ef7da662ed327b138b69bc613b12ae4728d86c2597a437a34db797579c08632
"""AC-LINT-033: lint includes citation-checker's and size-checker's findings
as Findings, and load_corpus is corpus-loader's function re-exported."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_REL = "specs/components/foo/component.md"


def _purpose_text():
    # Exactly 160 whitespace-separated words, no decision citations.
    words = ["word"] * 160
    return " ".join(words) + "."


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **Widget** \u2014 a thing the fixture talks about.\n",
    )

    (specs / "decisions").mkdir(parents=True, exist_ok=True)

    comp = specs / "components" / "foo"
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + _purpose_text()
        + "\n"
        "\n"
        "## Rationale\n"
        "\n"
        "This design follows `D999`.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doing foo.\n"
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
    _write(comp / "component.md", component_md)

    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 Foo MUST return the input unchanged.\n",
    )

    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an input of 1\n"
        "When foo runs\n"
        "Then it returns 1\n"
        "```\n",
    )

    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Latency: foo returns within 10 ms, measured by a timing test.\n",
    )


def test_lint_includes_citation_and_size_findings(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    cite = [
        f
        for f in findings
        if field(f, "rule_id") == "R-CITE-001"
        and field(f, "severity") == "fail"
        and field(f, "file") == COMPONENT_REL
    ]
    size = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-004"
        and field(f, "severity") == "fail"
        and field(f, "file") == COMPONENT_REL
    ]

    summary = [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
        for f in findings
    ]
    assert len(cite) == 1, summary
    assert len(size) == 1, summary

    for f in cite + size:
        assert not isinstance(f, dict), summary
        assert type(f).__name__ == "Finding", type(f)

    assert field(report, "hard_failures") == 2, summary


def test_load_corpus_returns_corpus_with_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    load_corpus = getattr(spec_linter, "load_corpus")
    corpus = load_corpus(repo_root)

    assert type(corpus).__name__ == "Corpus", type(corpus)
    components = field(corpus, "components")
    assert "foo" in components, list(components)
    component = components["foo"]
    root = field(component, "root")
    assert root is not None
    assert field(root, "rel_path") == COMPONENT_REL