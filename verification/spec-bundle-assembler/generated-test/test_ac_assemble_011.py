# hotdocs-criterion: sha256:77bf2b9f0f15c4cc1ebebf415892e6ea3176b19db875650c7bc34cf1cdaf3b56
import importlib.util
import inspect
import sys
from pathlib import Path

import spec_bundle_assembler


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


def component_md(cid, title, slug, depends, purpose):
    return (
        "---\n"
        + "id: " + cid + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "depends_on: [" + depends + "]\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n"
    )


def build_component(repo_root, slug, cid, title, depends, purpose, rid, acid, req_text, signature):
    base = repo_root / "specs" / "components" / slug
    write(base / "component.md", component_md(cid, title, slug, depends, purpose))
    write(
        base / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** — " + req_text + "\n",
    )
    write(
        base / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given an input\n"
        + "When it is called\n"
        + "Then it returns the expected value\n"
        + "```\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n\n```\n" + signature + "\n```\n",
    )
    write(base / "constraints.md", "# Constraints\n\nNone.\n")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    build_component(
        repo_root, "foo", "comp-foo", "Foo", "comp-bar, comp-baz",
        "Foo doubles a number.", "R-FOO-001", "AC-FOO-001",
        "`foo(x)` MUST return `2 * x`.", "foo(x: int) -> int",
    )
    build_component(
        repo_root, "bar", "comp-bar", "Bar", "",
        "Bar looks up values.", "R-BAR-001", "AC-BAR-001",
        "`bar_get(key)` MUST return the stored value.", "bar_get(key: str) -> str",
    )
    build_component(
        repo_root, "baz", "comp-baz", "Baz", "",
        "Baz stores values.", "R-BAZ-001", "AC-BAZ-001",
        "`baz_put(key)` MUST store a value.", "baz_put(key: str) -> None",
    )
    bar_source = (
        "def bar_get(key: str) -> str:\n"
        + "    " + repr("Return the value stored under the given key.\n\n    Further detail that is not the first line.\n    ") + "\n"
        + "    return " + repr("v") + "\n"
    )
    write(repo_root / "legacy" / "bar" / "bar.py", bar_source)
    (repo_root / "legacy" / "foo").mkdir(parents=True, exist_ok=True)
    (repo_root / "legacy" / "baz").mkdir(parents=True, exist_ok=True)


def lint_fixture(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def test_ac_assemble_011_dependency_usage_card(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    lint_fixture(repo_root)

    expected_mod = load_module(
        repo_root / "legacy" / "bar" / "bar.py", "bar_ac_assemble_011_expected"
    )
    bar_get = expected_mod.bar_get
    expected_signature = str(inspect.signature(bar_get))
    expected_doc_first_line = inspect.getdoc(bar_get).splitlines()[0]

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    usage = field(bundle, "dependency_usage")
    assert "comp-bar" in usage
    bar_card = usage["comp-bar"]
    assert isinstance(bar_card, str)
    assert "bar" in bar_card
    assert "legacy/bar/" in bar_card
    assert "bar_get" in bar_card
    assert expected_signature in bar_card
    assert expected_doc_first_line in bar_card
    assert "Further detail that is not the first line." not in bar_card

    assert "comp-baz" in usage
    assert usage["comp-baz"] == ""