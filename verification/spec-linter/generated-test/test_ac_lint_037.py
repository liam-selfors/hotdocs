# hotdocs-criterion: sha256:0136128c6d5bae609e1a8a54ca94f881d2be21bd7369d088e1247166e3983160
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

ARCH_X = (
    "---\n"
    "id: arch-x\n"
    "title: X\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: [arch-gone, arch-old, arch-ok]\n"
    "---\n"
    "\n"
    "# X\n"
    "\n"
    "## Purpose\n"
    "\n"
    "An architecture document for x.\n"
)

ARCH_OLD = (
    "---\n"
    "id: arch-old\n"
    "title: Old\n"
    "status: deprecated\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Old\n"
    "\n"
    "## Purpose\n"
    "\n"
    "An old architecture document.\n"
)

ARCH_OK = (
    "---\n"
    "id: arch-ok\n"
    "title: Ok\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Ok\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A fine architecture document.\n"
)


def write(repo_root, rel, text):
    p = repo_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(repo_root, "specs/product/foo.md", PRODUCT_FOO)
    write(repo_root, "specs/components/foo/component.md", COMPONENT_FOO)
    write(repo_root, "specs/components/foo/requirements/R-FOO-001.md", REQ_FOO)
    write(repo_root, "specs/components/foo/interface/library.md", LIBRARY_FOO)
    write(repo_root, "specs/components/foo/acceptance/AC-FOO-001.md", AC_FOO)
    write(repo_root, "specs/components/foo/constraints.md", CONSTRAINTS_FOO)
    write(repo_root, "specs/architecture/x.md", ARCH_X)
    write(repo_root, "specs/architecture/old.md", ARCH_OLD)
    write(repo_root, "specs/architecture/ok.md", ARCH_OK)


def test_ac_lint_037_dangling_and_deprecated_depends_on(tmp_path):
    repo_root = Path(tmp_path)
    build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    def norm(f):
        return str(field(f, "file")).replace("\\", "/")

    mine = [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-003"
        and field(f, "severity") == "fail"
        and norm(f) == "specs/architecture/x.md"
    ]
    messages = [str(field(f, "message")) for f in mine]

    assert len(mine) == 2, messages

    gone = [m for m in messages if "arch-gone" in m]
    assert len(gone) == 1, messages
    assert "does not exist" in gone[0], messages

    old = [m for m in messages if "arch-old" in m]
    assert len(old) == 1, messages
    assert gone[0] != old[0], messages

    assert not any("arch-ok" in m for m in messages), messages