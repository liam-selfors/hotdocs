import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


_LINTER = None


def _load_spec_linter():
    global _LINTER
    if _LINTER is not None:
        return _LINTER
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
    _LINTER = spec_linter
    return _LINTER


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    value = getattr(obj, name, None)
    if value is None and hasattr(obj, "get"):
        try:
            value = obj.get(name)
        except Exception:
            value = None
    return value


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def _component_md(slug, title, depends_on):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "depends_on: [" + ", ".join(depends_on) + "]\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + title + " doubles a number.\n"
    )


def _make_component(repo_root, slug, title, library_text, depends_on=(), data=None):
    upper = slug.upper()
    root = repo_root / "specs" / "components" / slug
    _write(root / "component.md", _component_md(slug, title, list(depends_on)))
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    _write(
        root / "requirements" / (rid + ".md"),
        "# " + rid + "\n\n**" + rid + "** — `" + slug + "(x)` MUST return `2 * x`.\n",
    )
    _write(
        root / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When " + slug + "(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(root / "interface" / "library.md", library_text)
    _write(root / "constraints.md", "# Constraints\n\nNone.\n")
    for name, text in (data or {}).items():
        _write(root / "interface" / "data" / (name + ".md"), text)


FOO_LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"


def _lint_clean(repo_root):
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = getattr(report, "hard_failures", None)
    if hard is None and isinstance(report, dict):
        hard = report.get("summary", {}).get("hard_failures")
    findings = getattr(report, "findings", None)
    assert hard == 0, "fixture is not lint-clean: %r" % (findings,)


def _bar_entry(repo_root):
    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    deps = _field(bundle, "dependency_interfaces")
    assert deps is not None, "dependency_interfaces missing from CriterionBundle"
    entry = _field(deps, "comp-bar")
    if entry is None:
        try:
            entry = deps["comp-bar"]
        except Exception:
            entry = None
    assert isinstance(entry, str), "dependency_interfaces['comp-bar'] missing or not text: %r" % (deps,)
    return entry


def _base_corpus(repo_root, bar_library):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _make_component(repo_root, "foo", "Foo", FOO_LIBRARY, depends_on=["comp-bar"])
    _make_component(repo_root, "bar", "Bar", bar_library)


def test_unowned_type_resolved_from_whole_corpus_with_owner_label(tmp_path):
    repo_root = tmp_path / "repo"
    bar_library = "# Library\n\n```\nbar(w: Widget) -> int\n```\n"
    widget_marker = "counted in sprockets"
    widget_text = "# `Widget`\n\nA record with one field, `size: int`, " + widget_marker + ".\n"
    _base_corpus(repo_root, bar_library)
    _make_component(
        repo_root,
        "baz",
        "Baz",
        "# Library\n\n```\nbaz(x: int) -> int\n```\n",
        data={"Widget": widget_text},
    )
    _lint_clean(repo_root)

    entry = _bar_entry(repo_root)

    assert "bar(w: Widget) -> int" in entry, "comp-bar's own interface content missing: %r" % entry
    assert widget_marker in entry, "Widget's own documented content not appended: %r" % entry
    assert entry.index("bar(w: Widget) -> int") < entry.index(widget_marker), (
        "Widget's content should be appended after comp-bar's own content: %r" % entry
    )
    assert "comp-baz" in entry, "appended type is not labeled with its real owner comp-baz: %r" % entry
    label_lines = [
        line for line in entry.splitlines() if "Widget" in line and "comp-baz" in line
    ]
    assert label_lines, (
        "no heading naming both the type 'Widget' and its owner 'comp-baz': %r" % entry
    )
    first_label = entry.index(label_lines[0])
    assert first_label < entry.index(widget_marker), (
        "owner label must precede Widget's appended content: %r" % entry
    )


def test_unresolved_type_name_is_skipped_silently(tmp_path):
    repo_root = tmp_path / "repo"
    bar_library = "# Library\n\n```\nbar(g: Gadget) -> int\n```\n"
    _base_corpus(repo_root, bar_library)
    _lint_clean(repo_root)

    entry = _bar_entry(repo_root)

    assert entry.strip() == bar_library.strip(), (
        "comp-bar's entry must be its own content unchanged when a name is unresolved: %r" % entry
    )
    assert "owned by" not in entry


def test_ambiguous_type_name_is_skipped_silently(tmp_path):
    repo_root = tmp_path / "repo"
    bar_library = "# Library\n\n```\nbar(z: Gizmo) -> int\n```\n"
    baz_marker = "baz flavoured gizmo"
    qux_marker = "qux flavoured gizmo"
    _base_corpus(repo_root, bar_library)
    _make_component(
        repo_root,
        "baz",
        "Baz",
        "# Library\n\n```\nbaz(x: int) -> int\n```\n",
        data={"Gizmo": "# `Gizmo`\n\nA " + baz_marker + ".\n"},
    )
    _make_component(
        repo_root,
        "qux",
        "Qux",
        "# Library\n\n```\nqux(x: int) -> int\n```\n",
        data={"Gizmo": "# `Gizmo`\n\nA " + qux_marker + ".\n"},
    )
    _lint_clean(repo_root)

    entry = _bar_entry(repo_root)

    assert baz_marker not in entry, "ambiguous type content from comp-baz was guessed in: %r" % entry
    assert qux_marker not in entry, "ambiguous type content from comp-qux was guessed in: %r" % entry
    assert "comp-baz" not in entry and "comp-qux" not in entry, (
        "a section for the ambiguous name was added: %r" % entry
    )
    assert entry.strip() == bar_library.strip(), (
        "comp-bar's entry must be its own content unchanged when a name is ambiguous: %r" % entry
    )