import hashlib
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

FOO_COMPONENT = """---
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

BAR_COMPONENT = """---
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

Bar adds one to a doubled number.
"""

FOO_REQ = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

FOO_AC = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

FOO_LIB = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

BAR_REQ = "# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST return `foo(x) + 1`.\n"

BAR_AC = """# AC-BAR-001

Covers: R-BAR-001
Kind: generated-test

```gherkin
Given x = 2
When bar(x) is called
Then it returns 5
```
"""

BAR_LIB = "# Library\n\n```\nbar(x: int) -> int\n```\n"

CONSTRAINTS = "# Constraints\n\nNone.\n"

FOO_PY = "def foo(x): return 2 * x\n"
BAR_PY = "def bar(x): return 2 * x + 1\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root, "specs/glossary.md", GLOSSARY)

    _write(repo_root, "specs/components/foo/component.md", FOO_COMPONENT)
    _write(repo_root, "specs/components/foo/requirements/R-FOO-001.md", FOO_REQ)
    _write(repo_root, "specs/components/foo/acceptance/AC-FOO-001.md", FOO_AC)
    _write(repo_root, "specs/components/foo/interface/library.md", FOO_LIB)
    _write(repo_root, "specs/components/foo/constraints.md", CONSTRAINTS)
    _write(repo_root, "legacy/foo/foo.py", FOO_PY)

    _write(repo_root, "specs/components/bar/component.md", BAR_COMPONENT)
    _write(repo_root, "specs/components/bar/requirements/R-BAR-001.md", BAR_REQ)
    _write(repo_root, "specs/components/bar/acceptance/AC-BAR-001.md", BAR_AC)
    _write(repo_root, "specs/components/bar/interface/library.md", BAR_LIB)
    _write(repo_root, "specs/components/bar/constraints.md", CONSTRAINTS)
    _write(repo_root, "legacy/bar/bar.py", BAR_PY)


def _load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
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
    return module


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0


def _md_files_under(repo_root: Path, rel_dir: str):
    d = repo_root / rel_dir
    if not d.is_dir():
        return []
    return [
        p.relative_to(repo_root).as_posix()
        for p in d.rglob("*")
        if p.is_file() and p.suffix == ".md"
    ]


def _code_files_under(repo_root: Path, rel_dir: str):
    d = repo_root / rel_dir
    if not d.is_dir():
        return []
    out = []
    for p in d.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(d).parts
        if p.name.startswith("."):
            continue
        if "__pycache__" in rel_parts:
            continue
        if any(part.startswith(".") for part in rel_parts):
            continue
        out.append(p.relative_to(repo_root).as_posix())
    return out


def _expected_hash(repo_root: Path, mode: str = "cold") -> str:
    paths = []
    # Target's own spec files.
    for rel in (
        "specs/components/bar/component.md",
        "specs/components/bar/constraints.md",
    ):
        if (repo_root / rel).is_file():
            paths.append(rel)
    paths += _md_files_under(repo_root, "specs/components/bar/requirements")
    paths += _md_files_under(repo_root, "specs/components/bar/interface")
    # Dependency comp-foo: component.md, interface/*.md, code dir (sealed -> source_path).
    if (repo_root / "specs/components/foo/component.md").is_file():
        paths.append("specs/components/foo/component.md")
    paths += _md_files_under(repo_root, "specs/components/foo/interface")
    paths += _code_files_under(repo_root, "legacy/foo")
    # Glossary.
    if (repo_root / "specs/glossary.md").is_file():
        paths.append("specs/glossary.md")

    stream = bytearray()
    stream += mode.encode("utf-8") + b"\x00"
    for rel in sorted(set(paths)):
        stream += rel.encode("utf-8") + b"\x00"
        stream += (repo_root / rel).read_bytes()
        stream += b"\x00"
    return "sha256:" + hashlib.sha256(bytes(stream)).hexdigest()


def _hash_of(repo_root: Path) -> str:
    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    return field(bundle, "spec_bundle_hash")


def test_spec_bundle_hash_matches_defined_stream(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    expected = _expected_hash(repo_root, "cold")
    actual = _hash_of(repo_root)
    assert actual == expected


def test_provenance_manifest_in_code_dir_does_not_change_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    first = _hash_of(repo_root)

    (repo_root / "legacy/foo/.provenance.json").write_bytes(
        b'{"anything": "at all", "n": 42}\n'
    )

    second = _hash_of(repo_root)
    assert second == first


def test_code_change_in_dependency_changes_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    _assert_lint_clean(repo_root)

    first = _hash_of(repo_root)

    foo_py = repo_root / "legacy/foo/foo.py"
    foo_py.write_bytes(foo_py.read_bytes() + b"# an added line\n")

    second = _hash_of(repo_root)
    assert second != first