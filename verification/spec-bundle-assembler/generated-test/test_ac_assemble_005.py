# hotdocs-criterion: sha256:c7606b563785bc1064b7f408a4c9a88304bd3ddcbcd56735784dbc23fd9c40c9
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_component(repo_root, slug, title, upper, purpose, func):
    comp_dir = repo_root / "specs" / "components" / slug
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose + "\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        comp_dir / "requirements" / (rid + ".md"),
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — `" + func + "(x)` MUST return `2 * x`.\n",
    )
    write(
        comp_dir / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When " + func + "(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        + func + "(x: int) -> int\n"
        "```\n",
    )
    write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )
    return comp_dir / "acceptance" / (acid + ".md")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    build_component(repo_root, "foo", "Foo", "FOO", "Foo doubles a number.", "foo")
    bar_ac = build_component(repo_root, "bar", "Bar", "BAR", "Bar doubles a number.", "bar")
    return bar_ac


def test_assemble_refuses_corpus_with_hard_lint_failure(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bar_ac = build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # Introduce a hard-fail finding in a component other than the one assembled.
    text = bar_ac.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines(True) if not ln.startswith("Kind:")]
    bar_ac.write_text("".join(lines), encoding="utf-8")
    assert spec_linter.lint(None, repo_root).hard_failures > 0

    # Library: must not produce a bundle.
    raised = None
    result = None
    try:
        result = spec_bundle_assembler.assemble("comp-foo", repo_root)
    except Exception as exc:  # precondition failure may be signalled by raising
        raised = exc

    if raised is not None:
        assert not isinstance(
            raised, (TypeError, AttributeError, NameError, ImportError, SyntaxError)
        ), "assemble crashed instead of reporting a precondition failure: " + repr(raised)
    else:
        type_name = type(result).__name__.lower()
        assert type(result).__name__ != "SpecBundle", "assemble produced a bundle for a non-lint-clean corpus"
        assert "precondition" in type_name or "precondition" in repr(result).lower() or "fail" in type_name, (
            "assemble did not return a precondition-failure result: " + repr(result)
        )
        spec_value = None
        try:
            spec_value = field(result, "spec")
        except (KeyError, AttributeError, TypeError):
            spec_value = None
        assert not spec_value, "a partial bundle was returned"

    # CLI: precondition failure is exit code 1.
    code = spec_bundle_assembler.main(["comp-foo", "--repo-root=" + str(repo_root)])
    capsys.readouterr()
    assert code == 1

    code_json = spec_bundle_assembler.main(["comp-foo", "--repo-root=" + str(repo_root), "--format=json"])
    out = capsys.readouterr().out
    assert code_json == 1
    assert "spec_bundle_hash" not in out