# hotdocs-criterion: sha256:cfaf0de97288bc72dee8944710161bce3d0598df6d4dbfc7514964a5c34f17b5
import importlib.util
import sys
from pathlib import Path

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test term, kept in `glossed_word`.\n"
)

FOO_COMPONENT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

FOO_REQ = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
)

FOO_AC = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

FOO_LIBRARY = (
    "# Library\n"
    "\n"
    "```\n"
    "foo(x: int) -> int\n"
    "```\n"
    "\n"
    "Returns `dep_word`.\n"
)

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "None.\n"
)

BAZ_COMPONENT = (
    "---\n"
    "id: comp-baz\n"
    "title: Baz\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/baz/\n"
    "depends_on: [comp-foo]\n"
    "---\n"
    "\n"
    "# Baz\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Baz uses foo.\n"
)

BAZ_REQ = (
    "# R-BAZ-001\n"
    "\n"
    "**R-BAZ-001** — `baz(x)` MUST return `seen` for any `x`.\n"
)

BAZ_AC = (
    "# AC-BAZ-001\n"
    "\n"
    "Covers: R-BAZ-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = `given_word`\n"
    "When baz(x) is called\n"
    "Then it returns `dep_word`, `glossed_word`, `iface_word`, `nowhere_word` and `seen<x>`\n"
    "```\n"
)

BAZ_LIBRARY = (
    "# Library\n"
    "\n"
    "```\n"
    "baz(x: int) -> int\n"
    "```\n"
    "\n"
    "Returns `iface_word`.\n"
)


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", GLOSSARY)

    foo = specs / "components" / "foo"
    write(foo / "component.md", FOO_COMPONENT)
    write(foo / "requirements" / "R-FOO-001.md", FOO_REQ)
    write(foo / "acceptance" / "AC-FOO-001.md", FOO_AC)
    write(foo / "interface" / "library.md", FOO_LIBRARY)
    write(foo / "constraints.md", CONSTRAINTS)

    baz = specs / "components" / "baz"
    write(baz / "component.md", BAZ_COMPONENT)
    write(baz / "requirements" / "R-BAZ-001.md", BAZ_REQ)
    write(baz / "acceptance" / "AC-BAZ-001.md", BAZ_AC)
    write(baz / "interface" / "library.md", BAZ_LIBRARY)
    write(baz / "constraints.md", CONSTRAINTS)


def assert_lint_clean(repo_root):
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def test_ac_review_009_only_nowhere_word_is_invisible(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    assert_lint_clean(repo_root)

    report = spec_reviewer.check(["comp-baz"], repo_root)

    findings = field(report, "findings")
    tokens = [
        field(f, "token")
        for f in findings
        if field(f, "criterion_id") == "AC-BAZ-001"
        and field(f, "kind") == "invisible_reference"
    ]
    assert tokens == ["nowhere_word"], findings