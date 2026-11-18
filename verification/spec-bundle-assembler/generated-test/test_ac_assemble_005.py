# hotdocs-criterion: sha256:800ad8f8fc3f120a2e255c76da72da06e7b927eef3a95cff613860aa945cb17f
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


_SPEC_LINTER = None


def _load_spec_linter():
    global _SPEC_LINTER
    if _SPEC_LINTER is not None:
        return _SPEC_LINTER
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
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    _SPEC_LINTER = module
    return module


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    try:
        return value.get(name)
    except Exception:
        pass
    return getattr(value, name, None)


def _hard_failures(report):
    if isinstance(report, dict):
        summary = report.get("summary") or {}
        if "hard_failures" in report:
            return report["hard_failures"]
        return summary.get("hard_failures")
    return getattr(report, "hard_failures", None)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def _component_md(comp_id, title, source_path, depends_on, purpose):
    return (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: " + source_path + "\n"
        "depends_on: " + depends_on + "\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n" + purpose + "\n"
    )


def _requirement(rid, text):
    return "# " + rid + "\n\n**" + rid + "** — " + text + "\n"


def _acceptance(acid, rid, given, when, then):
    return (
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given " + given + "\n"
        "When " + when + "\n"
        "Then " + then + "\n"
        "```\n"
    )


def _library(sig):
    return "# Library\n\n```\n" + sig + "\n```\n"


CONSTRAINTS = "# Constraints\n\nNone.\n"


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(specs / "glossary.md", GLOSSARY)

    foo = specs / "components" / "foo"
    _write(
        foo / "component.md",
        _component_md("comp-foo", "Foo", "legacy/foo/", "[]", "Foo doubles a number."),
    )
    _write(
        foo / "requirements" / "R-FOO-001.md",
        _requirement("R-FOO-001", "`foo(x)` MUST return `2 * x`."),
    )
    _write(
        foo / "acceptance" / "AC-FOO-001.md",
        _acceptance("AC-FOO-001", "R-FOO-001", "x = 2", "foo(x) is called", "it returns 4"),
    )
    _write(foo / "interface" / "library.md", _library("foo(x: int) -> int"))
    _write(foo / "constraints.md", CONSTRAINTS)

    bar = specs / "components" / "bar"
    _write(
        bar / "component.md",
        _component_md(
            "comp-bar", "Bar", "legacy/bar/", "[comp-foo]", "Bar triples a number."
        ),
    )
    _write(
        bar / "requirements" / "R-BAR-001.md",
        _requirement("R-BAR-001", "`bar(x)` MUST return `3 * x`."),
    )
    _write(
        bar / "acceptance" / "AC-BAR-001.md",
        _acceptance("AC-BAR-001", "R-BAR-001", "x = 2", "bar(x) is called", "it returns 6"),
    )
    _write(bar / "interface" / "library.md", _library("bar(x: int) -> int"))
    _write(bar / "constraints.md", CONSTRAINTS)


def _break_acceptance(repo_root, slug, acid):
    path = repo_root / "specs" / "components" / slug / "acceptance" / (acid + ".md")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [ln for ln in lines if not ln.startswith("Kind:")]
    assert len(kept) == len(lines) - 1
    path.write_text("".join(kept), encoding="utf-8")


_BUG_EXCEPTIONS = (TypeError, AttributeError, NameError, ImportError, SyntaxError)


def _assert_refused(component_id, repo_root):
    try:
        result = spec_bundle_assembler.assemble(component_id, repo_root)
    except _BUG_EXCEPTIONS:
        raise
    except Exception:
        return  # refused with a precondition failure, no bundle produced

    # If it returned instead of raising, it must not be a (partial) bundle.
    if isinstance(result, bool):
        assert result is False
        return
    if isinstance(result, int):
        assert result != 0
        return
    if result is None:
        return
    for name in ("spec", "interface", "constraints", "spec_bundle_hash"):
        assert not _field(result, name), (
            "assemble returned bundle content in field %r despite a "
            "non-lint-clean corpus" % name
        )


@pytest.mark.parametrize(
    "broken_slug,broken_ac,assembled_id",
    [
        ("foo", "AC-FOO-001", "comp-foo"),
        ("foo", "AC-FOO-001", "comp-bar"),
        ("bar", "AC-BAR-001", "comp-foo"),
        ("bar", "AC-BAR-001", "comp-bar"),
    ],
)
def test_assembly_refused_when_corpus_has_hard_lint_failure(
    tmp_path, broken_slug, broken_ac, assembled_id
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    assert _hard_failures(spec_linter.lint(None, repo_root)) == 0

    # Sanity: the clean corpus assembles, so any later failure is lint-driven.
    good = spec_bundle_assembler.assemble(assembled_id, repo_root)
    assert _field(good, "component_id") == assembled_id
    assert _field(good, "spec")

    _break_acceptance(repo_root, broken_slug, broken_ac)
    assert (_hard_failures(spec_linter.lint(None, repo_root)) or 0) > 0

    _assert_refused(assembled_id, repo_root)