import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path

import spec_bundle_assembler


def _write_fixture(repo_root: Path) -> None:
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n"
    )

    foo_dir = repo_root / "specs" / "components" / "foo"
    (foo_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (foo_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (foo_dir / "interface").mkdir(parents=True, exist_ok=True)

    (foo_dir / "component.md").write_text(
        """---
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
    )
    (foo_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
    )
    (foo_dir / "acceptance" / "AC-FOO-001.md").write_text(
        """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""
    )
    (foo_dir / "interface" / "library.md").write_text(
        """# Library

```
foo(x: int) -> int
```
"""
    )
    (foo_dir / "constraints.md").write_text("# Constraints\n\nNone.\n")

    bar_dir = repo_root / "specs" / "components" / "bar"
    (bar_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (bar_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (bar_dir / "interface").mkdir(parents=True, exist_ok=True)

    (bar_dir / "component.md").write_text(
        """---
id: comp-bar
title: Bar
status: draft
owners: [team-a]
sealed: true
source_path: legacy/bar/
depends_on: [comp-foo]
---

# Bar

## Purpose

Bar uses Foo.
"""
    )
    (bar_dir / "requirements" / "R-BAR-001.md").write_text(
        "# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST call `foo(x)`.\n"
    )
    (bar_dir / "acceptance" / "AC-BAR-001.md").write_text(
        """# AC-BAR-001

Covers: R-BAR-001
Kind: generated-test

```gherkin
Given x = 2
When bar(x) is called
Then it calls foo(x)
```
"""
    )
    (bar_dir / "interface" / "library.md").write_text(
        """# Library

```
bar(x: int) -> int
```
"""
    )
    (bar_dir / "constraints.md").write_text("# Constraints\n\nNone.\n")

    legacy_foo = repo_root / "legacy" / "foo"
    legacy_foo.mkdir(parents=True, exist_ok=True)
    (legacy_foo / "foo.py").write_text("def foo(x): return 2 * x\n")


_BUNDLE_RELATIVE_PATHS = [
    "legacy/foo/foo.py",
    "specs/components/bar/component.md",
    "specs/components/bar/constraints.md",
    "specs/components/bar/interface/library.md",
    "specs/components/bar/requirements/R-BAR-001.md",
    "specs/components/foo/component.md",
    "specs/components/foo/interface/library.md",
    "specs/glossary.md",
]


def _expected_hash(repo_root: Path, mode: str) -> str:
    stream = mode.encode("utf-8") + b"\x00"
    for rel in sorted(set(_BUNDLE_RELATIVE_PATHS)):
        data = (repo_root / rel).read_bytes()
        stream += rel.encode("utf-8") + b"\x00" + data + b"\x00"
    return "sha256:" + hashlib.sha256(stream).hexdigest()


def _bundle_hash(bundle):
    return (
        bundle.get("spec_bundle_hash")
        if isinstance(bundle, dict)
        else getattr(bundle, "spec_bundle_hash", None)
    )


def test_spec_bundle_hash_matches_defined_stream_and_reacts_to_code_changes():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _write_fixture(repo_root)

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
        assert spec_linter.lint(None, repo_root).hard_failures == 0

        bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
        actual_hash = _bundle_hash(bundle)
        assert actual_hash == _expected_hash(repo_root, "cold")

        (repo_root / "legacy" / "foo" / ".provenance.json").write_text(
            '{"anything": true}'
        )
        bundle_after_provenance = spec_bundle_assembler.assemble(
            "comp-bar", repo_root, mode="cold"
        )
        hash_after_provenance = _bundle_hash(bundle_after_provenance)
        assert hash_after_provenance == actual_hash

        foo_py = repo_root / "legacy" / "foo" / "foo.py"
        with foo_py.open("a") as handle:
            handle.write("# a trailing comment line\n")

        bundle_after_edit = spec_bundle_assembler.assemble(
            "comp-bar", repo_root, mode="cold"
        )
        hash_after_edit = _bundle_hash(bundle_after_edit)
        assert hash_after_edit != actual_hash
        assert hash_after_edit == _expected_hash(repo_root, "cold")