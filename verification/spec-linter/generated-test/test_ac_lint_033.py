# hotdocs-criterion: sha256:7ef7da662ed327b138b69bc613b12ae4728d86c2597a437a34db797579c08632
"""AC-LINT-033: lint() folds in citation-checker's and size-checker's
findings as Finding objects, and load_corpus is corpus-loader's."""

from pathlib import Path

import spec_linter


COMP_REL = "specs/components/foo/component.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _purpose_160_words():
    words = ["token" + str(i) for i in range(1, 161)]
    return " ".join(words) + "."


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    for sub in ("product", "architecture", "vars", "decisions"):
        (specs / sub).mkdir(parents=True, exist_ok=True)

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — a small thing used in tests.\n",
    )

    comp_dir = specs / "components" / "foo"
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + _purpose_160_words()
        + "\n"
        "\n"
        "## Rationale\n"
        "\n"
        "This design follows D9999.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doing the thing.\n"
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
    _write(comp_dir / "component.md", component_md)

    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `do_thing` MUST return `1`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When do_thing runs\n"
        "Then it returns 1\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "do_thing() -> int\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "- `do_thing` returns within 1 second, measured by a timed test.\n",
    )


def _findings_for(report, rule_id):
    return [f for f in field(report, "findings") if field(f, "rule_id") == rule_id]


def test_lint_includes_citation_and_size_findings(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)

    cite = [
        f for f in _findings_for(report, "R-CITE-001")
        if field(f, "severity") == "fail" and field(f, "file") == COMP_REL
    ]
    assert len(cite) == 1, [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
        for f in field(report, "findings")
    ]

    size = [
        f for f in _findings_for(report, "R-SIZE-004")
        if field(f, "severity") == "fail" and field(f, "file") == COMP_REL
    ]
    assert len(size) == 1, [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
        for f in field(report, "findings")
    ]
    assert "Purpose section has 160 words" in field(size[0], "message")

    for f in (cite[0], size[0]):
        assert not isinstance(f, dict)
        assert isinstance(f, spec_linter.Finding)

    assert field(report, "hard_failures") == 2, [
        (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
        for f in field(report, "findings")
    ]


def test_load_corpus_returns_corpus_with_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    load_corpus = spec_linter.load_corpus
    assert callable(load_corpus)

    corpus = load_corpus(repo_root)
    assert type(corpus).__name__ == "Corpus"

    components = field(corpus, "components")
    assert "foo" in components
    comp = components["foo"]
    root = field(comp, "root")
    assert root is not None
    assert field(root, "rel_path") == COMP_REL
    assert field(root, "doc_id") == "comp-foo"