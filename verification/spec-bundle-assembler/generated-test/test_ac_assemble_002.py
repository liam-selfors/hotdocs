import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    if hasattr(value, name):
        return getattr(value, name, default)
    try:
        return value[name]
    except Exception:
        pass
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            return getter(name, default)
        except Exception:
            pass
    return default


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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, source_path, depends_on, purpose):
    return "\n".join(
        [
            "---",
            "id: " + comp_id,
            "title: " + title,
            "status: draft",
            "owners: [team-a]",
            "sealed: true",
            "source_path: " + source_path,
            "depends_on: " + depends_on,
            "---",
            "",
            "# " + title,
            "",
            "## Purpose",
            "",
            purpose,
            "",
        ]
    )


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    # Dependency: comp-foo
    foo = repo_root / "specs" / "components" / "foo"
    _write(
        foo / "component.md",
        _component_md("comp-foo", "Foo", "legacy/foo/", "[]", "Foo doubles a number."),
    )
    _write(
        foo / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        foo / "acceptance" / "AC-FOO-001.md",
        "\n".join(
            [
                "# AC-FOO-001",
                "",
                "Covers: R-FOO-001",
                "Kind: generated-test",
                "",
                "```gherkin",
                "Given x = 2",
                "When foo(x) is called",
                "Then it returns 4",
                "```",
                "",
            ]
        ),
    )
    _write(
        foo / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(foo / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x: int) -> int:\n    return 2 * x\n",
    )

    # Dependent: comp-bar
    bar = repo_root / "specs" / "components" / "bar"
    _write(
        bar / "component.md",
        _component_md(
            "comp-bar", "Bar", "legacy/bar/", "[comp-foo]", "Bar triples a number."
        ),
    )
    _write(
        bar / "requirements" / "R-BAR-001.md",
        "# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST return `3 * x`.\n",
    )
    _write(
        bar / "acceptance" / "AC-BAR-001.md",
        "\n".join(
            [
                "# AC-BAR-001",
                "",
                "Covers: R-BAR-001",
                "Kind: generated-test",
                "",
                "```gherkin",
                "Given x = 2",
                "When bar(x) is called",
                "Then it returns 6",
                "```",
                "",
            ]
        ),
    )
    _write(
        bar / "interface" / "library.md",
        "# Library\n\n```\nbar(x: int) -> int\n```\n",
    )
    _write(bar / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "legacy" / "bar" / "bar.py",
        "def bar(x: int) -> int:\n    return 3 * x\n",
    )


def test_dependency_interfaces_contains_only_dependency_interface(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard_failures = _field(report, "hard_failures")
    if hard_failures is None:
        summary = _field(report, "summary", {}) or {}
        hard_failures = _field(summary, "hard_failures")
    assert hard_failures == 0, "fixture corpus must be lint-clean: %r" % (
        _field(report, "findings"),
    )

    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root)

    dep_interfaces = _field(bundle, "dependency_interfaces")
    assert dep_interfaces is not None, "bundle has no dependency_interfaces"
    dep_interfaces = dict(dep_interfaces)

    assert set(dep_interfaces.keys()) == {"comp-foo"}, dep_interfaces.keys()

    foo_iface = dep_interfaces["comp-foo"]
    assert isinstance(foo_iface, str)

    # The dependency's interface/ content is present.
    assert "foo(x: int) -> int" in foo_iface
    assert "# Library" in foo_iface

    # None of the dependency's component.md content.
    for forbidden in (
        "# Foo",
        "## Purpose",
        "Foo doubles a number",
        "sealed:",
        "source_path",
        "legacy/foo",
        "owners:",
        "team-a",
        "status: draft",
        "depends_on",
    ):
        assert forbidden not in foo_iface, (
            "component.md content %r leaked into dependency_interfaces" % forbidden
        )

    # None of the dependency's requirements/ content.
    for forbidden in ("R-FOO-001", "MUST return", "2 * x"):
        assert forbidden not in foo_iface, (
            "requirements/ content %r leaked into dependency_interfaces" % forbidden
        )

    # None of the dependency's constraints.md content.
    for forbidden in ("# Constraints", "None."):
        assert forbidden not in foo_iface, (
            "constraints.md content %r leaked into dependency_interfaces" % forbidden
        )

    # And none of its acceptance/ content either.
    for forbidden in ("AC-FOO-001", "Covers:", "Then it returns 4"):
        assert forbidden not in foo_iface, (
            "acceptance/ content %r leaked into dependency_interfaces" % forbidden
        )