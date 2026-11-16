import spec_bundle_assembler

import importlib.util
import inspect
import sys
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
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


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def _component_md(cid: str, title: str, slug: str, depends_on: str, purpose: str) -> str:
    return (
        "---\n"
        f"id: {cid}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        f"depends_on: {depends_on}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose}\n"
    )


def _requirement(rid: str, text: str) -> str:
    return f"# {rid}\n\n**{rid}** — {text}\n"


def _acceptance(acid: str, rid: str, given: str, when: str, then: str) -> str:
    return (
        f"# {acid}\n"
        "\n"
        f"Covers: {rid}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        f"Given {given}\n"
        f"When {when}\n"
        f"Then {then}\n"
        "```\n"
    )


def _library(signature: str) -> str:
    return f"# Library\n\n```\n{signature}\n```\n"


CONSTRAINTS = "# Constraints\n\nNone.\n"


BAR_SOURCE = (
    "def bar_get(key: str) -> str:\n"
    "    \"\"\"Look up the stored value for key.\n"
    "\n"
    "    Returns an empty string when key is unknown.\n"
    "    \"\"\"\n"
    "    return \"\"\n"
)

FOO_SOURCE = (
    "def foo(x: int) -> int:\n"
    "    \"\"\"Double x.\"\"\"\n"
    "    return 2 * x\n"
)


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(specs / "glossary.md", GLOSSARY)

    # comp-foo: the dependent
    foo = specs / "components" / "foo"
    _write(
        foo / "component.md",
        _component_md("comp-foo", "Foo", "foo", "[comp-bar, comp-baz]", "Foo doubles a number."),
    )
    _write(foo / "requirements" / "R-FOO-001.md",
           _requirement("R-FOO-001", "`foo(x)` MUST return `2 * x`."))
    _write(foo / "acceptance" / "AC-FOO-001.md",
           _acceptance("AC-FOO-001", "R-FOO-001", "x = 2", "foo(x) is called", "it returns 4"))
    _write(foo / "interface" / "library.md", _library("foo(x: int) -> int"))
    _write(foo / "constraints.md", CONSTRAINTS)

    # comp-bar: a sealed dependency with real code
    bar = specs / "components" / "bar"
    _write(
        bar / "component.md",
        _component_md("comp-bar", "Bar", "bar", "[]", "Bar looks up stored values."),
    )
    _write(bar / "requirements" / "R-BAR-001.md",
           _requirement("R-BAR-001", "`bar_get(key)` MUST return a string."))
    _write(bar / "acceptance" / "AC-BAR-001.md",
           _acceptance("AC-BAR-001", "R-BAR-001", "key = \"a\"", "bar_get(key) is called",
                       "it returns a string"))
    _write(bar / "interface" / "library.md", _library("bar_get(key: str) -> str"))
    _write(bar / "constraints.md", CONSTRAINTS)

    # comp-baz: a sealed dependency with no real code at all
    baz = specs / "components" / "baz"
    _write(
        baz / "component.md",
        _component_md("comp-baz", "Baz", "baz", "[]", "Baz stores values."),
    )
    _write(baz / "requirements" / "R-BAZ-001.md",
           _requirement("R-BAZ-001", "`baz_put(key)` MUST return None."))
    _write(baz / "acceptance" / "AC-BAZ-001.md",
           _acceptance("AC-BAZ-001", "R-BAZ-001", "key = \"a\"", "baz_put(key) is called",
                       "it returns None"))
    _write(baz / "interface" / "library.md", _library("baz_put(key: str) -> None"))
    _write(baz / "constraints.md", CONSTRAINTS)

    # Real code: foo and bar under their source_path; nothing under legacy/baz/.
    _write(repo_root / "legacy" / "foo" / "foo.py", FOO_SOURCE)
    _write(repo_root / "legacy" / "bar" / "bar.py", BAR_SOURCE)
    (repo_root / "legacy" / "baz").mkdir(parents=True, exist_ok=True)


def _expected_bar_facts(repo_root: Path):
    path = repo_root / "legacy" / "bar" / "bar.py"
    module_name = "_ac_assemble_011_bar_probe"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        fn = module.bar_get
        sig_text = str(inspect.signature(fn))
        doc_first_line = inspect.getdoc(fn).splitlines()[0].strip()
    finally:
        sys.modules.pop(module_name, None)
    return sig_text, doc_first_line


def test_ac_assemble_011_dependency_usage_cards(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    sig_text, doc_first_line = _expected_bar_facts(repo_root)
    assert sig_text == "(key: str) -> str"
    assert doc_first_line == "Look up the stored value for key."

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    usage = field(bundle, "dependency_usage")
    assert "comp-bar" in usage
    assert "comp-baz" in usage

    bar_card = usage["comp-bar"]
    assert isinstance(bar_card, str)
    assert "bar" in bar_card
    assert "legacy/bar/" in bar_card
    assert "gen/bar/" not in bar_card
    assert "bar_get" in bar_card
    assert sig_text in bar_card
    assert doc_first_line in bar_card

    baz_card = usage["comp-baz"]
    assert baz_card == ""