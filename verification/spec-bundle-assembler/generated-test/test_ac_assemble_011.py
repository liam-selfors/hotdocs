import importlib.util
import inspect
import sys
from pathlib import Path

import spec_bundle_assembler


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter) and not hasattr(type(value), key):
        try:
            return getter(key, default)
        except Exception:
            pass
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def _component_md(comp_id: str, title: str, source_path: str, depends_on: str, purpose: str) -> str:
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        f"source_path: {source_path}\n"
        f"depends_on: {depends_on}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose}\n"
    )


def _requirement_md(rid: str, sentence: str) -> str:
    return f"# {rid}\n\n**{rid}** — {sentence}\n"


def _acceptance_md(acid: str, rid: str, given: str, when: str, then: str) -> str:
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


def _library_md(signature: str) -> str:
    return f"# Library\n\n```\n{signature}\n```\n"


CONSTRAINTS = "# Constraints\n\nNone.\n"


BAR_SOURCE = (
    '"""Bar module."""\n'
    "\n"
    "\n"
    "def bar_get(key: str) -> str:\n"
    '    """Return the value stored under key.\n'
    "\n"
    "    A longer explanation that must not be required in the card.\n"
    '    """\n'
    "    return key\n"
)

FOO_SOURCE = (
    '"""Foo module."""\n'
    "\n"
    "\n"
    "def foo(x: int) -> int:\n"
    '    """Double x."""\n'
    "    return 2 * x\n"
)


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(specs / "glossary.md", GLOSSARY)

    # comp-foo: the dependent
    foo = specs / "components" / "foo"
    _write(
        foo / "component.md",
        _component_md("comp-foo", "Foo", "legacy/foo/", "[comp-bar, comp-baz]", "Foo doubles a number."),
    )
    _write(foo / "requirements" / "R-FOO-001.md", _requirement_md("R-FOO-001", "`foo(x)` MUST return `2 * x`."))
    _write(
        foo / "acceptance" / "AC-FOO-001.md",
        _acceptance_md("AC-FOO-001", "R-FOO-001", "x = 2", "foo(x) is called", "it returns 4"),
    )
    _write(foo / "interface" / "library.md", _library_md("foo(x: int) -> int"))
    _write(foo / "constraints.md", CONSTRAINTS)

    # comp-bar: sealed dependency with real code under legacy/bar/
    bar = specs / "components" / "bar"
    _write(
        bar / "component.md",
        _component_md("comp-bar", "Bar", "legacy/bar/", "[]", "Bar looks up a value by key."),
    )
    _write(
        bar / "requirements" / "R-BAR-001.md",
        _requirement_md("R-BAR-001", "`bar_get(key)` MUST return `key`."),
    )
    _write(
        bar / "acceptance" / "AC-BAR-001.md",
        _acceptance_md("AC-BAR-001", "R-BAR-001", 'key = "a"', "bar_get(key) is called", 'it returns "a"'),
    )
    _write(bar / "interface" / "library.md", _library_md("bar_get(key: str) -> str"))
    _write(bar / "constraints.md", CONSTRAINTS)

    # comp-baz: sealed dependency with no real code at all
    baz = specs / "components" / "baz"
    _write(
        baz / "component.md",
        _component_md("comp-baz", "Baz", "legacy/baz/", "[]", "Baz echoes a string."),
    )
    _write(
        baz / "requirements" / "R-BAZ-001.md",
        _requirement_md("R-BAZ-001", "`baz(s)` MUST return `s`."),
    )
    _write(
        baz / "acceptance" / "AC-BAZ-001.md",
        _acceptance_md("AC-BAZ-001", "R-BAZ-001", 's = "a"', "baz(s) is called", 'it returns "a"'),
    )
    _write(baz / "interface" / "library.md", _library_md("baz(s: str) -> str"))
    _write(baz / "constraints.md", CONSTRAINTS)

    # Real code for sealed components lives at source_path, never gen/.
    _write(repo_root / "legacy" / "foo" / "foo.py", FOO_SOURCE)
    _write(repo_root / "legacy" / "bar" / "bar.py", BAR_SOURCE)
    # Deliberately nothing under legacy/baz/.


def _load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _load_bar_probe(repo_root: Path):
    module_name = "_ac_assemble_011_bar_probe"
    module_path = repo_root / "legacy" / "bar" / "bar.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_ac_assemble_011_dependency_usage_cards(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard_failures = _get(report, "hard_failures")
    if hard_failures is None:
        summary = _get(report, "summary") or {}
        hard_failures = _get(summary, "hard_failures")
    assert hard_failures == 0, f"fixture corpus is not lint-clean: {_get(report, 'findings')}"

    probe = _load_bar_probe(repo_root)
    expected_signature = str(inspect.signature(probe.bar_get))
    expected_doc_first_line = inspect.getdoc(probe.bar_get).splitlines()[0].strip()
    assert expected_signature == "(key: str) -> str"
    assert expected_doc_first_line == "Return the value stored under key."

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    usage = _get(bundle, "dependency_usage")
    assert usage is not None, "bundle has no dependency_usage"
    usage_bar = usage.get("comp-bar") if isinstance(usage, dict) else _get(usage, "comp-bar")
    usage_baz_present = ("comp-baz" in usage) if hasattr(usage, "__contains__") else False

    assert isinstance(usage_bar, str), f"dependency_usage['comp-bar'] is not text: {usage_bar!r}"
    assert "bar" in usage_bar
    assert "legacy/bar/" in usage_bar, usage_bar
    assert "bar_get" in usage_bar, usage_bar
    assert expected_signature in usage_bar, usage_bar
    assert expected_doc_first_line in usage_bar, usage_bar
    # Introspection-level facts only: never the function body's source text.
    assert "return key" not in usage_bar, usage_bar
    # A sealed dependency's card is built from source_path, never gen/.
    assert "gen/bar/" not in usage_bar, usage_bar

    assert usage_baz_present, "dependency_usage has no entry for comp-baz"
    usage_baz = usage.get("comp-baz") if isinstance(usage, dict) else _get(usage, "comp-baz")
    assert usage_baz == "", f"dependency_usage['comp-baz'] should be an empty string, got {usage_baz!r}"