# hotdocs-criterion: sha256:658b50055eb862e1025458ff3bf9cbc2bb3cab3da659dd72ed18b2a2748fc343
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


PURPOSE_TEXT = "Foo doubles a number, marked quixoticpurposemarker."
SCOPE_TEXT = "Foo covers integer input, marked quixoticscopemarker."
RATIONALE_TEXT = "Doubling was chosen long ago, marked quixoticrationalemarker."
OPEN_QUESTIONS_TEXT = "Whether tripling is wanted, marked quixoticopenquestionmarker."
CHANGE_LOG_TEXT = "Initial version written, marked quixoticchangelogmarker."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
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
        + PURPOSE_TEXT + "\n"
        "\n"
        "## Scope\n"
        "\n"
        + SCOPE_TEXT + "\n"
        "\n"
        "## Rationale\n"
        "\n"
        + RATIONALE_TEXT + "\n"
        "\n"
        "## Open questions\n"
        "\n"
        "- " + OPEN_QUESTIONS_TEXT + "\n"
        "\n"
        "## Change log\n"
        "\n"
        "- " + CHANGE_LOG_TEXT + "\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
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
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def test_cold_spec_excludes_rationale_open_questions_and_change_log(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    spec_text = field(bundle, "spec")

    assert isinstance(spec_text, str)
    assert "quixoticpurposemarker" in spec_text
    assert "quixoticscopemarker" in spec_text

    assert "quixoticrationalemarker" not in spec_text
    assert "quixoticopenquestionmarker" not in spec_text
    assert "quixoticchangelogmarker" not in spec_text