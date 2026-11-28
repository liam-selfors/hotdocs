# hotdocs-criterion: sha256:72ffb27d859306e2853c6cf9c1ba4a7b9709126626859cb3eba488802dd6ad26
import importlib.util
import sys
from pathlib import Path

import spec_reviewer


FENCE = "```"

GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test term.\n"
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
    + FENCE + "gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    + FENCE + "\n"
)

FOO_LIBRARY = (
    "# Library\n"
    "\n"
    + FENCE + "\n"
    "foo(x: int) -> int\n"
    + FENCE + "\n"
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
    "Baz names a word.\n"
)

BAZ_BOLD_LINE = "**R-BAZ-001** — `baz(x)` MUST return `iface_word`."

BAZ_REQ = (
    "# R-BAZ-001\n"
    "\n"
    + BAZ_BOLD_LINE + "\n"
)

BAZ_THEN_LINE = "Then it returns the word"

BAZ_AC = (
    "# AC-BAZ-001\n"
    "\n"
    "Covers: R-BAZ-001\n"
    "Kind: generated-test\n"
    "\n"
    + FENCE + "gherkin\n"
    "Given x = 2\n"
    "When baz(x) is called\n"
    + BAZ_THEN_LINE + "\n"
    + FENCE + "\n"
)

BAZ_IFACE_LINE = "Returns `iface_word`."

BAZ_LIBRARY = (
    "# Library\n"
    "\n"
    + FENCE + "\n"
    "baz(x: int) -> str\n"
    + FENCE + "\n"
    "\n"
    + BAZ_IFACE_LINE + "\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def test_ac_review_010_prompt_holds_criterion_bundle_fields(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    assert_lint_clean(repo_root)

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        return {
            "text": '{"writable": true, "gaps": []}',
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    spec_reviewer.check(["comp-baz"], repo_root, model="mock", llm_backend=backend)

    baz_prompts = [p for p in prompts if "AC-BAZ-001" in p]
    assert len(baz_prompts) == 1, prompts
    prompt = baz_prompts[0]

    assert "comp-baz" in prompt
    assert "AC-BAZ-001" in prompt
    assert "R-BAZ-001" in prompt
    assert BAZ_THEN_LINE in prompt
    assert BAZ_BOLD_LINE in prompt
    assert BAZ_IFACE_LINE in prompt
    assert "a test term" in prompt
    assert "Returns `dep_word`." in prompt