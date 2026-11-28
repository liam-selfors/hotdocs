# hotdocs-criterion: sha256:a14e075b0e93e3a0b3280f7bb8a9ffcced7281976671056f5ef510c498be9096
import importlib.util
import sys
from pathlib import Path

import spec_reviewer


SENTENCE = (
    "The pipeline fixes the test framework (pytest), the test file's name "
    "and location, and how the test reaches the component's code: never "
    "report any of these as a gap."
)

GAP_REPLY = (
    'Here: {"writable": false, "gaps": [{"kind": "unstated_behavior", '
    '"missing": "negative x", "proposed_text": "MUST raise ValueError", '
    '"target_file": "R-FOO-001.md"}, {"kind": "other", "missing": "m", '
    '"proposed_text": "p", "target_file": "t"}]} done'
)


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


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
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
        "Foo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — `foo(x)` MUST return an `int`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 3\n"
        "When foo(x) is called\n"
        "Then it returns an int\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def assert_lint_clean(repo_root):
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec_linter = load_module(path, "spec_linter")
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def is_judge_prompt(prompt):
    return '"conflicts"' in prompt


def test_ac_review_004(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    assert_lint_clean(repo_root)

    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        if "AC-FOO-001" in prompt:
            text = GAP_REPLY
        else:
            text = "not json"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    report = spec_reviewer.check(["comp-foo"], repo_root, model="mock", llm_backend=backend)

    criterion_prompts = [p for p in prompts if not is_judge_prompt(p)]
    assert len(criterion_prompts) == 2, criterion_prompts

    foo1 = [p for p in criterion_prompts if "AC-FOO-001" in p]
    assert len(foo1) == 1
    assert "AC-FOO-002" not in foo1[0]
    foo2 = [p for p in criterion_prompts if "AC-FOO-002" in p]
    assert len(foo2) == 1
    assert "AC-FOO-001" not in foo2[0]

    for prompt in criterion_prompts:
        assert any(SENTENCE in line for line in prompt.splitlines()), prompt

    assert dict(field(report, "writable")) == {"AC-FOO-001": False, "AC-FOO-002": None}

    gaps = list(field(report, "gaps"))
    assert len(gaps) == 1, gaps
    gap = gaps[0]
    assert field(gap, "kind") == "unstated_behavior"
    assert field(gap, "criterion_id") == "AC-FOO-001"
    assert field(gap, "missing") == "negative x"
    assert field(gap, "proposed_text") == "MUST raise ValueError"
    assert field(gap, "target_file") == "R-FOO-001.md"

    findings = list(field(report, "findings"))
    unparseable = [f for f in findings if field(f, "kind") == "model_unparseable"]
    assert len(unparseable) == 1, findings
    assert field(unparseable[0], "criterion_id") == "AC-FOO-002"

    assert field(report, "degraded") is False