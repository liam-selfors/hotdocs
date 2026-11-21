# hotdocs-criterion: sha256:e625b86223ebdadd2f70a8ed6374fc55056d124b81a6a0d077fe4c8ad448300b
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FENCE = "```"


def write_component(repo_root, slug, upper, title, purpose, func, depends_on):
    comp = repo_root / "specs" / "components" / slug
    write(
        comp / "component.md",
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "depends_on: " + depends_on + "\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        comp / "requirements" / (rid + ".md"),
        "# " + rid + "\n"
        + "\n"
        + "**" + rid + "** — `" + func + "(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + FENCE + "gherkin\n"
        + "Given x = 2\n"
        + "When " + func + "(x) is called\n"
        + "Then it returns 4\n"
        + FENCE + "\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + FENCE + "\n"
        + func + "(x: int) -> int\n"
        + FENCE + "\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    write_component(repo_root, "foo", "FOO", "Foo", "Foo doubles a number.", "foo", "[]")
    write_component(repo_root, "bar", "BAR", "Bar", "Bar doubles a number.", "bar", "[comp-foo]")


def break_lint(repo_root, slug, upper):
    ac = repo_root / "specs" / "components" / slug / "acceptance" / ("AC-" + upper + "-001.md")
    lines = ac.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith("Kind:")]
    assert len(kept) == len(lines) - 1
    ac.write_text("".join(kept), encoding="utf-8")


def is_full_bundle(value):
    if value is None:
        return False
    try:
        spec = field(value, "spec")
    except (KeyError, AttributeError, TypeError):
        return False
    return isinstance(spec, str) and spec != ""


@pytest.mark.parametrize(
    "broken_slug,broken_upper,target",
    [
        ("bar", "BAR", "comp-foo"),
        ("bar", "BAR", "comp-bar"),
        ("foo", "FOO", "comp-foo"),
        ("foo", "FOO", "comp-bar"),
    ],
)
def test_assemble_refuses_corpus_with_hard_lint_failure(tmp_path, capsys, broken_slug, broken_upper, target):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    break_lint(repo_root, broken_slug, broken_upper)
    assert spec_linter.lint(None, repo_root).hard_failures > 0

    # Library: no partial bundle is produced.
    raised = None
    result = None
    try:
        result = spec_bundle_assembler.assemble(target, repo_root)
    except Exception as exc:  # precondition failure may be raised
        raised = exc
    if raised is None:
        assert not is_full_bundle(result), "assemble produced a bundle from a corpus that is not lint-clean"

    # CLI: exit code 1 (precondition failure), and no bundle on stdout.
    capsys.readouterr()
    code = spec_bundle_assembler.main([target, "--repo-root=" + str(repo_root), "--format=json"])
    out = capsys.readouterr().out
    assert code == 1
    stripped = out.strip()
    if stripped:
        try:
            parsed = json.loads(stripped)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            assert not parsed.get("spec"), "CLI printed a bundle despite precondition failure"
            assert "spec_bundle_hash" not in parsed