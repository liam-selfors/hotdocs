import sys
from pathlib import Path

import spec_bundle_assembler


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _assert_lint_clean(repo_root: Path) -> None:
    import importlib.util

    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def _write_glossary(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )


def _write_component(
    repo_root: Path,
    slug: str,
    comp_id: str,
    title: str,
    depends_on: list,
    interface_library_body: str,
    data_files: dict,
    purpose: str,
) -> str:
    comp_dir = repo_root / "specs" / "components" / slug
    depends_str = "[]" if not depends_on else "[" + ", ".join(depends_on) + "]"
    _write(
        comp_dir / "component.md",
        f"""---
id: {comp_id}
title: {title}
status: draft
owners: [team-a]
sealed: true
source_path: legacy/{slug}/
depends_on: {depends_str}
---

# {title}

## Purpose

{purpose}
""",
    )
    req_id = f"R-{slug.upper()}-001"
    ac_id = f"AC-{slug.upper()}-001"
    _write(
        comp_dir / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\n**{req_id}** — `{slug}_op()` MUST succeed.\n",
    )
    _write(
        comp_dir / "acceptance" / f"{ac_id}.md",
        f"""# {ac_id}

Covers: {req_id}
Kind: generated-test

```gherkin
Given nothing
When {slug}_op() is called
Then it succeeds
```
""",
    )
    _write(comp_dir / "interface" / "library.md", interface_library_body)
    for name, body in data_files.items():
        _write(comp_dir / "interface" / "data" / f"{name}.md", body)
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    return ac_id


_BAR_LIBRARY = "# Library\n\n```\nmake_widget() -> Widget\n```\n"
_WIDGET_DATA = "# Widget\n\n```\nWidget(name: str)\n```\n\nA widget has a name.\n"


def test_resolves_unowned_type_from_other_owning_component(tmp_path: Path) -> None:
    repo_root = tmp_path
    _write_glossary(repo_root)

    _write_component(
        repo_root,
        "bar",
        "comp-bar",
        "Bar",
        [],
        _BAR_LIBRARY,
        {},
        "Bar provides widgets.",
    )
    _write_component(
        repo_root,
        "baz",
        "comp-baz",
        "Baz",
        [],
        "# Library\n\n```\nbaz_op() -> None\n```\n",
        {"Widget": _WIDGET_DATA},
        "Baz owns the Widget type.",
    )
    target_ac_id = _write_component(
        repo_root,
        "target",
        "comp-target",
        "Target",
        ["comp-bar"],
        "# Library\n\n```\ntarget_op() -> None\n```\n",
        {},
        "Target uses Bar.",
    )

    _assert_lint_clean(repo_root)

    bar_standalone = spec_bundle_assembler.assemble_criterion("comp-bar", "AC-BAR-001", repo_root)
    bar_own_interface = _get(bar_standalone, "interface")

    bundle = spec_bundle_assembler.assemble_criterion("comp-target", target_ac_id, repo_root)
    dependency_interfaces = _get(bundle, "dependency_interfaces")
    bar_entry = dependency_interfaces["comp-bar"]

    assert bar_own_interface in bar_entry
    assert "A widget has a name." in bar_entry
    assert "comp-baz" in bar_entry
    assert bar_entry != bar_own_interface


def test_unresolved_type_leaves_dependency_interface_unchanged(tmp_path: Path) -> None:
    repo_root = tmp_path
    _write_glossary(repo_root)

    _write_component(
        repo_root,
        "bar",
        "comp-bar",
        "Bar",
        [],
        _BAR_LIBRARY,
        {},
        "Bar provides widgets.",
    )
    target_ac_id = _write_component(
        repo_root,
        "target",
        "comp-target",
        "Target",
        ["comp-bar"],
        "# Library\n\n```\ntarget_op() -> None\n```\n",
        {},
        "Target uses Bar.",
    )

    _assert_lint_clean(repo_root)

    bar_standalone = spec_bundle_assembler.assemble_criterion("comp-bar", "AC-BAR-001", repo_root)
    bar_own_interface = _get(bar_standalone, "interface")

    bundle = spec_bundle_assembler.assemble_criterion("comp-target", target_ac_id, repo_root)
    dependency_interfaces = _get(bundle, "dependency_interfaces")
    bar_entry = dependency_interfaces["comp-bar"]

    assert bar_entry == bar_own_interface


def test_ambiguous_type_leaves_dependency_interface_unchanged(tmp_path: Path) -> None:
    repo_root = tmp_path
    _write_glossary(repo_root)

    _write_component(
        repo_root,
        "bar",
        "comp-bar",
        "Bar",
        [],
        _BAR_LIBRARY,
        {},
        "Bar provides widgets.",
    )
    _write_component(
        repo_root,
        "baz",
        "comp-baz",
        "Baz",
        [],
        "# Library\n\n```\nbaz_op() -> None\n```\n",
        {"Widget": _WIDGET_DATA},
        "Baz owns the Widget type.",
    )
    _write_component(
        repo_root,
        "qux",
        "comp-qux",
        "Qux",
        [],
        "# Library\n\n```\nqux_op() -> None\n```\n",
        {"Widget": "# Widget\n\n```\nWidget(label: str)\n```\n\nA different widget definition.\n"},
        "Qux also claims the Widget type.",
    )
    target_ac_id = _write_component(
        repo_root,
        "target",
        "comp-target",
        "Target",
        ["comp-bar"],
        "# Library\n\n```\ntarget_op() -> None\n```\n",
        {},
        "Target uses Bar.",
    )

    _assert_lint_clean(repo_root)

    bar_standalone = spec_bundle_assembler.assemble_criterion("comp-bar", "AC-BAR-001", repo_root)
    bar_own_interface = _get(bar_standalone, "interface")

    bundle = spec_bundle_assembler.assemble_criterion("comp-target", target_ac_id, repo_root)
    dependency_interfaces = _get(bundle, "dependency_interfaces")
    bar_entry = dependency_interfaces["comp-bar"]

    assert bar_entry == bar_own_interface