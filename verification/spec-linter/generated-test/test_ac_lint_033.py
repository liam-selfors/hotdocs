# hotdocs-criterion: sha256:01a445c3cb51513fee68906229ba1414e124bcb4dc27e37918c3d1d02714e4ae
from pathlib import Path

import spec_linter


COMPONENT_REL = "specs/components/foo/component.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "- **Widget** — a small thing this fixture talks about.\n",
    )

    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D1 First decision\n"
        "\n"
        "The foo component exists to format widgets.\n",
    )

    purpose_words = " ".join(["widget"] * 160)
    assert len(purpose_words.split()) == 160

    _write(
        repo_root / COMPONENT_REL,
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
        + purpose_words
        + "\n"
        "\n"
        "## Rationale\n"
        "\n"
        "This design follows `D999`.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: formatting widgets.\n"
        "- Out of scope: storing widgets.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None beyond the glossary.\n"
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
        "- Initial draft.\n",
    )

    comp = specs / "components" / "foo"
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `format_widget` MUST return the widget name "
        "unchanged (`D1`).\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget named \"a\"\n"
        "When format_widget runs\n"
        "Then it returns \"a\"\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "format_widget(name: str) -> str\n"
        "```\n"
        "\n"
        "Returns the widget name unchanged.\n",
    )
    _write(
        comp / "interface" / "data" / "Widget.md",
        "# `Widget`\n"
        "\n"
        "A widget is identified by its name, a `str`.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- `format_widget` returns within 10 ms, measured by timing 100 calls.\n",
    )


def test_lint_includes_citation_and_size_findings_and_load_corpus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    summary = [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
        for f in findings
    ]

    cite = [
        f
        for f in findings
        if field(f, "rule_id") == "R-CITE-001"
        and field(f, "severity") == "fail"
        and field(f, "file") == COMPONENT_REL
    ]
    assert cite, summary

    size = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-004"
        and field(f, "severity") == "fail"
        and field(f, "file") == COMPONENT_REL
    ]
    assert size, summary

    for f in cite + size:
        assert not isinstance(f, dict), summary
        assert type(f).__name__ == "Finding", summary
        if hasattr(spec_linter, "Finding"):
            assert isinstance(f, spec_linter.Finding), summary

    assert field(report, "hard_failures") == 2, summary

    corpus = spec_linter.load_corpus(repo_root)
    assert type(corpus).__name__ == "Corpus"
    components = field(corpus, "components")
    assert "foo" in components