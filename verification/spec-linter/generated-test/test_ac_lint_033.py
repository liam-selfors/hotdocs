# hotdocs-criterion: sha256:fe944dcdf22c53a8ad4629a89268c0ba28c1665040d42ebce95a728cdde93988
import spec_linter

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRODUCT = (
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

PURPOSE_TEXT = "Makes a foo. " + " ".join(["foo"] * 157)


def component_md():
    return (
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
        "\n"
        "## Purpose\n"
        "\n"
        + PURPOSE_TEXT + "\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** making a foo. **Out of scope:** everything else.\n"
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
        "- Initial draft (`D999`).\n"
    )


REQ = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    "```\n"
    "make_foo() -> str\n"
    "```\n"
)

AC = (
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

CONSTRAINTS = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(repo_root, "specs/product/foo.md", PRODUCT)
    write(repo_root, "specs/components/foo/component.md", component_md())
    write(repo_root, "specs/components/foo/requirements/R-FOO-001.md", REQ)
    write(repo_root, "specs/components/foo/interface/library.md", LIBRARY)
    write(repo_root, "specs/components/foo/acceptance/AC-FOO-001.md", AC)
    write(repo_root, "specs/components/foo/constraints.md", CONSTRAINTS)


COMPONENT_FILE = "specs/components/foo/component.md"


def norm(path):
    return str(path).replace("\\", "/")


def test_purpose_word_count_is_160():
    assert len(PURPOSE_TEXT.split()) == 160


def test_lint_includes_citation_and_size_findings(tmp_path):
    repo_root = tmp_path
    build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    cite = [
        f for f in findings
        if field(f, "rule_id") == "R-CITE-001"
        and field(f, "severity") == "fail"
        and norm(field(f, "file")) == COMPONENT_FILE
    ]
    size = [
        f for f in findings
        if field(f, "rule_id") == "R-SIZE-004"
        and field(f, "severity") == "fail"
        and norm(field(f, "file")) == COMPONENT_FILE
    ]
    summary = [
        (field(f, "rule_id"), field(f, "severity"), norm(field(f, "file")))
        for f in findings
    ]
    assert len(cite) == 1, summary
    assert len(size) == 1, summary
    for f in cite + size:
        assert isinstance(f, spec_linter.Finding), type(f)

    assert field(report, "hard_failures") == 2, summary


def test_load_corpus_returns_corpus_with_component(tmp_path):
    repo_root = tmp_path
    build_corpus(repo_root)

    load_corpus = spec_linter.load_corpus
    assert callable(load_corpus)
    corpus = load_corpus(repo_root)

    assert type(corpus).__name__ == "Corpus"
    components = field(corpus, "components")
    assert "foo" in components
    comp = components["foo"]
    root = field(comp, "root")
    assert root is not None
    assert norm(field(root, "rel_path")) == COMPONENT_FILE