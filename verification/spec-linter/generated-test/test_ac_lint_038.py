# hotdocs-criterion: sha256:eb9cd5005567637cbaddd1bbeab2323c621f65a4ebef83b211952937959cd5d4
from pathlib import Path

import spec_linter


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
    "\n"
    "## Purpose\n"
    "\n"
    "Makes a foo.\n"
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
    "- Initial draft.\n"
)

REQ_FOO = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIBRARY_FOO = (
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


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_clean_corpus(root):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    write(root, "specs/components/foo/component.md", COMPONENT_FOO)
    write(root, "specs/components/foo/requirements/R-FOO-001.md", REQ_FOO)
    write(root, "specs/components/foo/interface/library.md", LIBRARY_FOO)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", AC_FOO)
    write(root, "specs/components/foo/constraints.md", CONSTRAINTS_FOO)


def arch_doc(doc_id, deps):
    return (
        "---\n"
        "id: " + doc_id + "\n"
        "title: " + doc_id.upper() + " doc\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: [" + ", ".join(deps) + "]\n"
        "---\n"
        "\n"
        "# " + doc_id + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Describes " + doc_id + ".\n"
    )


def norm(path):
    return str(path).replace("\\", "/")


def sev(finding):
    s = field(finding, "severity")
    s = getattr(s, "value", s)
    return str(s)


def test_cycle_among_architecture_docs_reported_once(tmp_path):
    repo_root = tmp_path
    build_clean_corpus(repo_root)
    write(repo_root, "specs/architecture/arch-a.md", arch_doc("arch-a", ["arch-b"]))
    write(repo_root, "specs/architecture/arch-b.md", arch_doc("arch-b", ["arch-a"]))
    write(repo_root, "specs/architecture/arch-c.md", arch_doc("arch-c", ["arch-a"]))

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    cycle = [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-004"
        and sev(f) == "fail"
        and norm(field(f, "file")).startswith("specs/architecture/")
    ]
    assert len(cycle) == 1, [field(f, "message") for f in findings]
    message = field(cycle[0], "message")
    assert "arch-a" in message
    assert "arch-b" in message
    assert "arch-c" not in message


def test_no_cycle_among_architecture_docs_reports_nothing(tmp_path):
    repo_root = tmp_path
    build_clean_corpus(repo_root)
    write(repo_root, "specs/architecture/arch-a.md", arch_doc("arch-a", []))
    write(repo_root, "specs/architecture/arch-c.md", arch_doc("arch-c", ["arch-a"]))

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    cycle = [f for f in findings if field(f, "rule_id") == "R-LINT-004"]
    assert cycle == [], [field(f, "message") for f in cycle]