# hotdocs-criterion: sha256:0513348de928fd3f41b4696240925be17b6882fa9cd3e1d9646de704ab40999a
from pathlib import Path

import spec_linter


GLOSSARY_DEF = (
    "a reusable unit of foo output that the pipeline stores under the gen "
    "directory and verifies exactly once per generation run"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


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


def _component(definitions_text):
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
        "Makes a foo.\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** making a foo. **Out of scope:** everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        + definitions_text
        + "\n"
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

GLOSSARY = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary.\n"
    "\n"
    "- **Widget** \u2014 " + GLOSSARY_DEF + ".\n"
)


def _build(repo_root, local_text):
    specs = repo_root / "specs"
    _write(specs / "product" / "foo.md", PRODUCT)
    comp = specs / "components" / "foo"
    _write(comp / "component.md", _component("- **Widget** \u2014 " + local_text))
    _write(comp / "requirements" / "R-FOO-001.md", REQ)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(specs / "glossary.md", GLOSSARY)


def _lint011_fails(repo_root):
    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    return [
        f
        for f in findings
        if str(field(f, "rule_id")) == "R-LINT-011"
        and str(field(f, "severity")).split(".")[-1].lower() == "fail"
    ]


def test_verbatim_definition_copy_fails_r_lint_011(tmp_path):
    repo_root = Path(tmp_path)
    _build(repo_root, GLOSSARY_DEF + ".")
    hits = _lint011_fails(repo_root)
    assert len(hits) >= 1


def test_near_verbatim_definition_copy_fails_r_lint_011(tmp_path):
    repo_root = Path(tmp_path)
    # One extra word: token overlap well above 0.8.
    near = GLOSSARY_DEF.replace("reusable unit", "reusable small unit") + "."
    _build(repo_root, near)
    hits = _lint011_fails(repo_root)
    assert len(hits) >= 1


def test_genuine_delta_does_not_fail_r_lint_011(tmp_path):
    repo_root = Path(tmp_path)
    _build(
        repo_root,
        "in this component only, widgets are cached in memory for a "
        "single call rather than persisted.",
    )
    hits = _lint011_fails(repo_root)
    assert hits == []