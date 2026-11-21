# hotdocs-criterion: sha256:396cd7986ceb8b3ddfe3b7e9297a4818107b172fbffccd77e65614ecc883a69c
import importlib.util
import inspect
import sys
from pathlib import Path

import spec_bundle_assembler


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root, slug, title, upper, purpose, depends_on, signature):
    base = repo_root / "specs" / "components" / slug
    comp_md = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n"
    )
    _write(base / "component.md", comp_md)
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    _write(
        base / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** — `" + signature.split("(")[0]
        + "(x)` MUST return a value.\n",
    )
    _write(
        base / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given x = 2\n"
        + "When it is called\n"
        + "Then it returns a value\n"
        + "```\n",
    )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\n" + signature + "\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _lint(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0, [
        getattr(f, "message", f) for f in getattr(report, "findings", [])
    ]


def _build_corpus(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    _component(repo_root, "foo", "Foo", "FOO", "Foo doubles a number.",
               ["comp-bar", "comp-baz"], "foo(x: int) -> int")
    _component(repo_root, "bar", "Bar", "BAR", "Bar looks up a value.",
               [], "bar_get(key: str) -> str")
    _component(repo_root, "baz", "Baz", "BAZ", "Baz does nothing yet.",
               [], "baz(x: int) -> int")
    bar_src = (
        "def bar_get(key: str) -> str:\n"
        + "    " + repr("Return the value stored for key.\n\n    More detail on a second paragraph.\n    ") + "\n"
        + "    return 'v:' + key\n"
    )
    # Use a real docstring literal (triple-quoted) for clarity.
    bar_src = (
        "def bar_get(key: str) -> str:\n"
        + '    """Return the value stored for key.\n'
        + "\n"
        + "    More detail on a second paragraph.\n"
        + '    """\n'
        + "    return " + repr("v:") + " + key\n"
    )
    bar_path = repo_root / "legacy" / "bar" / "bar.py"
    _write(bar_path, bar_src)
    return bar_path


def test_ac_assemble_011_dependency_usage_card(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bar_path = _build_corpus(repo_root)
    _lint(repo_root)

    bar_module = load_module(bar_path, "bar")
    bar_get = bar_module.bar_get
    sig_text = str(inspect.signature(bar_get))
    doc_first = inspect.getdoc(bar_get).splitlines()[0]
    assert sig_text == "(key: str) -> str"
    assert doc_first == "Return the value stored for key."

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    usage = field(bundle, "dependency_usage")

    assert "comp-bar" in usage
    card = usage["comp-bar"]
    assert isinstance(card, str)
    assert "bar" in card
    assert "legacy/bar/" in card
    assert "bar_get" in card
    assert sig_text in card
    assert doc_first in card
    assert "More detail on a second paragraph." not in card

    assert "comp-baz" in usage
    assert usage["comp-baz"] == ""