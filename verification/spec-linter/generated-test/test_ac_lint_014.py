# hotdocs-criterion: sha256:0e6c3c4e1181610896e82e3a33cad2002408f1ef985f92d77559bdf2f676b598
import spec_linter

from pathlib import Path


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

COMPONENT_MD = (
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

REQUIREMENT = (
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

ACCEPTANCE = (
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

GLOSSARY_MAIN = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for this spec corpus.\n"
    "\n"
    "- **Foo** \u2014 the thing comp-foo makes.\n"
)

GLOSSARY_SECOND = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for this spec corpus.\n"
    "\n"
    "- **Bar** \u2014 another thing, defined in a second glossary.\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_clean_corpus(repo_root):
    specs = repo_root / "specs"
    write(specs / "product" / "foo.md", PRODUCT_FOO)
    comp = specs / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "constraints.md", CONSTRAINTS)


def lint014_fails(report):
    out = []
    for f in field(report, "findings"):
        if field(f, "rule_id") == "R-LINT-014" and field(f, "severity") == "fail":
            out.append(f)
    return out


def test_single_glossary_has_no_r_lint_014_failure(tmp_path):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MAIN)

    report = spec_linter.lint(None, repo_root)

    assert lint014_fails(report) == []


def test_two_glossaries_without_split_decision_fail_r_lint_014(tmp_path):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MAIN)
    write(repo_root / "specs" / "glossary-billing.md", GLOSSARY_SECOND)
    # No specs/architecture/ document records a bounded-context split.
    assert not (repo_root / "specs" / "architecture").exists()

    report = spec_linter.lint(None, repo_root)

    fails = lint014_fails(report)
    assert len(fails) >= 1, [
        (field(f, "rule_id"), field(f, "severity"), field(f, "message"))
        for f in field(report, "findings")
    ]
    assert field(report, "hard_failures") >= 1


def test_two_glossaries_cli_exits_one(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MAIN)
    write(repo_root / "specs" / "glossary-billing.md", GLOSSARY_SECOND)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])

    assert code == 1
    out = capsys.readouterr().out
    assert "R-LINT-014" in out