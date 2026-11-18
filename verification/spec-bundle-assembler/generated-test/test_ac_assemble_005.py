# hotdocs-criterion: sha256:800ad8f8fc3f120a2e255c76da72da06e7b927eef3a95cff613860aa945cb17f
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(comp_id, title, source_path, purpose):
    return (
        "---\n"
        + "id: " + comp_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: " + source_path + "\n"
        + "depends_on: []\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n"
    )


def acceptance_md(ac_id, r_id, given, when, then, with_kind=True):
    text = "# " + ac_id + "\n\n" + "Covers: " + r_id + "\n"
    if with_kind:
        text += "Kind: generated-test\n"
    text += (
        "\n"
        + "```gherkin\n"
        + "Given " + given + "\n"
        + "When " + when + "\n"
        + "Then " + then + "\n"
        + "```\n"
    )
    return text


def build_component(root, slug, comp_id, title, upper, func_sig, req_body, purpose, ac_parts):
    cdir = root / "specs" / "components" / slug
    write(cdir / "component.md", component_md(comp_id, title, "legacy/" + slug + "/", purpose))
    r_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    write(
        cdir / "requirements" / (r_id + ".md"),
        "# " + r_id + "\n\n" + "**" + r_id + "** — " + req_body + "\n",
    )
    write(
        cdir / "acceptance" / (ac_id + ".md"),
        acceptance_md(ac_id, r_id, ac_parts[0], ac_parts[1], ac_parts[2]),
    )
    write(
        cdir / "interface" / "library.md",
        "# Library\n\n```\n" + func_sig + "\n```\n",
    )
    write(cdir / "constraints.md", "# Constraints\n\nNone.\n")
    return cdir / "acceptance" / (ac_id + ".md"), ac_id, r_id, ac_parts


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write(root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    build_component(
        root, "foo", "comp-foo", "Foo", "FOO",
        "foo(x: int) -> int",
        "`foo(x)` MUST return `2 * x`.",
        "Foo doubles a number.",
        ("x = 2", "foo(x) is called", "it returns 4"),
    )
    bar_ac = build_component(
        root, "bar", "comp-bar", "Bar", "BAR",
        "bar(x: int) -> int",
        "`bar(x)` MUST return `x + 1`.",
        "Bar increments a number.",
        ("x = 2", "bar(x) is called", "it returns 3"),
    )
    return root, bar_ac


def break_corpus(bar_ac):
    path, ac_id, r_id, parts = bar_ac
    # Deleting the Kind: line is a hard lint failure.
    write(path, acceptance_md(ac_id, r_id, parts[0], parts[1], parts[2], with_kind=False))


def test_assemble_refuses_corpus_with_hard_lint_failure(corpus, capsys):
    root, bar_ac = corpus
    spec_linter = load_spec_linter()

    # Baseline: the clean corpus lints clean and assembles.
    assert spec_linter.lint(None, root).hard_failures == 0
    baseline = spec_bundle_assembler.assemble("comp-foo", root)
    assert field(baseline, "component_id") == "comp-foo"

    # Introduce a hard-fail finding in a *different* component.
    break_corpus(bar_ac)
    assert spec_linter.lint(None, root).hard_failures > 0

    # Library: assembling any component must fail, not yield a partial bundle.
    for comp_id in ("comp-foo", "comp-bar"):
        produced = None
        raised = False
        try:
            produced = spec_bundle_assembler.assemble(comp_id, root)
        except Exception:
            raised = True
        if not raised:
            spec_text = None
            try:
                spec_text = field(produced, "spec")
            except (KeyError, AttributeError, TypeError):
                spec_text = None
            assert not spec_text, (
                "assemble produced a bundle for " + comp_id + " despite a hard lint failure"
            )
            hash_value = None
            try:
                hash_value = field(produced, "spec_bundle_hash")
            except (KeyError, AttributeError, TypeError):
                hash_value = None
            assert not hash_value, (
                "assemble produced a hashed bundle for " + comp_id + " despite a hard lint failure"
            )


def test_cli_exits_1_on_hard_lint_failure(corpus, capsys):
    root, bar_ac = corpus
    break_corpus(bar_ac)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, root).hard_failures > 0
    capsys.readouterr()

    for comp_id in ("comp-foo", "comp-bar"):
        code = spec_bundle_assembler.main(
            [comp_id, "--repo-root=" + str(root), "--format=json"]
        )
        out = capsys.readouterr().out
        assert code == 1
        stripped = out.strip()
        if stripped:
            try:
                doc = json.loads(stripped)
            except ValueError:
                doc = None
            if isinstance(doc, dict):
                assert "spec_bundle_hash" not in doc
                assert "spec" not in doc