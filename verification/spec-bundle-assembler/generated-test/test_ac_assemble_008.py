import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _field(bundle, name):
    if isinstance(bundle, dict):
        return bundle.get(name)
    return getattr(bundle, name, None)


def _load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = base / "spec_linter.py"
    if not path.is_file():
        path = base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


_COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""

_REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

_ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

_INTERFACE_LIBRARY_MD = """# Library

```
foo(x: int) -> int
```
"""

_CONSTRAINTS_MD = """# Constraints

None.
"""

_GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""


def _build_fixture_repo(repo_root: Path) -> None:
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(_GLOSSARY_MD)

    comp_root = repo_root / "specs" / "components" / "foo"
    (comp_root / "requirements").mkdir(parents=True)
    (comp_root / "acceptance").mkdir(parents=True)
    (comp_root / "interface").mkdir(parents=True)

    (comp_root / "component.md").write_text(_COMPONENT_MD)
    (comp_root / "requirements" / "R-FOO-001.md").write_text(_REQUIREMENT_MD)
    (comp_root / "acceptance" / "AC-FOO-001.md").write_text(_ACCEPTANCE_MD)
    (comp_root / "interface" / "library.md").write_text(_INTERFACE_LIBRARY_MD)
    (comp_root / "constraints.md").write_text(_CONSTRAINTS_MD)


_GEN_FOO_PY = "def foo(x):\n    return 2 * x\n"
_GEN_NOTES_TXT = "scratch notes\n"
_GEN_SUB_EXTRA_PY = "extra content\n"


def _build_gen_content(repo_root: Path) -> None:
    gen_foo = repo_root / "gen" / "foo"
    (gen_foo / "sub").mkdir(parents=True)
    (gen_foo / "foo.py").write_text(_GEN_FOO_PY)
    (gen_foo / "notes.txt").write_text(_GEN_NOTES_TXT)
    (gen_foo / "sub" / "extra.py").write_text(_GEN_SUB_EXTRA_PY)


def test_hint_mode_adds_hint_code_and_only_changes_hash(tmp_path):
    repo_root = tmp_path / "repo"
    _build_fixture_repo(repo_root)
    _build_gen_content(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    cold_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    hint_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="hint")

    assert _field(cold_bundle, "hint_code") is None

    hint_code = _field(hint_bundle, "hint_code")
    assert isinstance(hint_code, dict)
    assert hint_code.get("foo.py") == _GEN_FOO_PY
    assert hint_code.get("notes.txt") == _GEN_NOTES_TXT
    assert hint_code.get("sub/extra.py") == _GEN_SUB_EXTRA_PY

    shared_fields = [
        "component_id",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
    ]
    for name in shared_fields:
        assert _field(hint_bundle, name) == _field(cold_bundle, name), name

    assert _field(hint_bundle, "spec_bundle_hash") != _field(cold_bundle, "spec_bundle_hash")