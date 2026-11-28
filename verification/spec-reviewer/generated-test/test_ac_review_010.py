# hotdocs-criterion: sha256:91eb9f735288ddbf469315abe39a2a558099c86a71b713ff70aeb5bb309cc4f8
import importlib.util
import json
import sys
from pathlib import Path

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    "Baz increments a number.\n"
)

BAZ_BOLD = "**R-BAZ-001** — `baz(x)` MUST return `x + 1`."

BAZ_REQ = (
    "# R-BAZ-001\n"
    "\n"
    + BAZ_BOLD + "\n"
)

BAZ_THEN = "Then it returns 3"

BAZ_AC = (
    "# AC-BAZ-001\n"
    "\n"
    "Covers: R-BAZ-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When baz(x) is called\n"
    + BAZ_THEN + "\n"
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

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "None.\n"
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


def test_ac_review_010_prompt_holds_criterion_bundle_fields(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    assert_lint_clean(repo_root)

    log_path = tmp_path / "prompts.jsonl"

    def stand_in(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        return {
            "text": json.dumps({"writable": True, "gaps": []}),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    report = spec_reviewer.check(
        ["comp-baz"], repo_root, model="mock", llm_backend=stand_in
    )

    assert "AC-BAZ-001" in field(report, "criteria_checked")

    assert log_path.is_file(), "the model stand-in was never called"
    prompts = [
        json.loads(line)["prompt"]
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    criterion_prompts = [p for p in prompts if "AC-BAZ-001" in p]
    assert len(criterion_prompts) == 1, criterion_prompts
    prompt = criterion_prompts[0]

    expected = [
        "comp-baz",
        "AC-BAZ-001",
        "R-BAZ-001",
        BAZ_THEN,
        BAZ_BOLD,
        "Returns `iface_word`.",
        "a test term",
        "Returns `dep_word`.",
    ]
    for text in expected:
        assert text in prompt, "missing from prompt: " + repr(text)