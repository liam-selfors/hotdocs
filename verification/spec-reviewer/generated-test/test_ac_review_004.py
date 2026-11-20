# hotdocs-criterion: sha256:d8483f7e9bea391c4f8b26bc29f19a5d0cb1cbdf071ca6e3c9c560d185e49b3f
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


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

COMPONENT = (
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

R_FOO_001 = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
R_FOO_002 = "# R-FOO-002\n\n**R-FOO-002** \u2014 `foo(0)` MUST return `0`.\n"

AC_FOO_001 = (
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

AC_FOO_002 = (
    "# AC-FOO-002\n"
    "\n"
    "Covers: R-FOO-002\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 0\n"
    "When foo(x) is called\n"
    "Then it returns 0\n"
    "```\n"
)

LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
CONSTRAINTS = "# Constraints\n\nNone.\n"


def build_corpus(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT)
    write(comp / "requirements" / "R-FOO-001.md", R_FOO_001)
    write(comp / "requirements" / "R-FOO-002.md", R_FOO_002)
    write(comp / "acceptance" / "AC-FOO-001.md", AC_FOO_001)
    write(comp / "acceptance" / "AC-FOO-002.md", AC_FOO_002)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "constraints.md", CONSTRAINTS)


def assert_lint_clean(repo_root):
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


FOO_001_REPLY = (
    'Here: {"writable": false, "gaps": [{"kind": "unstated_behavior", '
    '"missing": "negative x", "proposed_text": "MUST raise ValueError", '
    '"target_file": "R-FOO-001.md"}, {"kind": "other", "missing": "m", '
    '"proposed_text": "p", "target_file": "t"}]} done'
)


def test_ac_review_004(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    assert_lint_clean(repo_root)

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        if "AC-FOO-001" in prompt:
            text = FOO_001_REPLY
        else:
            text = "not json"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    report = spec_reviewer.check(["comp-foo"], repo_root, model="mock", llm_backend=backend)

    # Prompts not for the lint judge: the per-criterion prompts, which ask for "writable".
    criterion_prompts = [p for p in prompts if "writable" in p]
    assert len(criterion_prompts) == 2
    foo1_prompts = [p for p in criterion_prompts if "AC-FOO-001" in p]
    assert len(foo1_prompts) == 1
    assert "AC-FOO-002" not in foo1_prompts[0]
    foo2_prompts = [p for p in criterion_prompts if "AC-FOO-002" in p]
    assert len(foo2_prompts) == 1
    assert "AC-FOO-001" not in foo2_prompts[0]

    writable = dict(field(report, "writable"))
    assert writable == {"AC-FOO-001": False, "AC-FOO-002": None}
    assert writable["AC-FOO-001"] is False

    gaps = list(field(report, "gaps"))
    assert len(gaps) == 1
    gap = gaps[0]
    assert field(gap, "kind") == "unstated_behavior"
    assert field(gap, "criterion_id") == "AC-FOO-001"
    assert field(gap, "missing") == "negative x"
    assert field(gap, "proposed_text") == "MUST raise ValueError"
    assert field(gap, "target_file") == "R-FOO-001.md"

    findings = list(field(report, "findings"))
    unparseable = [f for f in findings if field(f, "kind") == "model_unparseable"]
    assert len(unparseable) == 1
    assert field(unparseable[0], "criterion_id") == "AC-FOO-002"
    assert field(unparseable[0], "token") == ""
    assert field(unparseable[0], "message") == "reply was not the JSON object asked for"

    assert field(report, "degraded") is False