import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

FOO_COMPONENT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

BAR_COMPONENT = (
    "---\n"
    "id: comp-bar\n"
    "title: Bar\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/bar/\n"
    "depends_on: [comp-foo]\n"
    "---\n"
    "\n"
    "# Bar\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Bar adds one to a doubled number.\n"
)

FOO_REQUIREMENT = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
BAR_REQUIREMENT = "# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST return `foo(x) + 1`.\n"

FOO_ACCEPTANCE = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

BAR_ACCEPTANCE = (
    "# AC-BAR-001\n"
    "\n"
    "Covers: R-BAR-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When bar(x) is called\n"
    "Then it returns 5\n"
    "```\n"
)

FOO_LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
BAR_LIBRARY = "# Library\n\n```\nbar(x: int) -> int\n```\n"

CONSTRAINTS = "# Constraints\n\nNone.\n"

FOO_CODE = "def foo(x): return 2 * x\n"
BAR_CODE = "def bar(x): return 2 * x + 1\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)

    foo = repo_root / "specs" / "components" / "foo"
    _write(foo / "component.md", FOO_COMPONENT)
    _write(foo / "requirements" / "R-FOO-001.md", FOO_REQUIREMENT)
    _write(foo / "acceptance" / "AC-FOO-001.md", FOO_ACCEPTANCE)
    _write(foo / "interface" / "library.md", FOO_LIBRARY)
    _write(foo / "constraints.md", CONSTRAINTS)

    bar = repo_root / "specs" / "components" / "bar"
    _write(bar / "component.md", BAR_COMPONENT)
    _write(bar / "requirements" / "R-BAR-001.md", BAR_REQUIREMENT)
    _write(bar / "acceptance" / "AC-BAR-001.md", BAR_ACCEPTANCE)
    _write(bar / "interface" / "library.md", BAR_LIBRARY)
    _write(bar / "constraints.md", CONSTRAINTS)

    _write(repo_root / "legacy" / "foo" / "foo.py", FOO_CODE)
    _write(repo_root / "legacy" / "bar" / "bar.py", BAR_CODE)


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
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _hard_failures(report):
    value = _field(report, "hard_failures")
    if value is None:
        summary = _field(report, "summary")
        if summary is not None:
            value = _field(summary, "hard_failures")
    return value


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert _hard_failures(report) == 0


def _md_files_under(repo_root: Path, directory: Path):
    if not directory.is_dir():
        return []
    return [
        p.relative_to(repo_root).as_posix()
        for p in directory.rglob("*.md")
        if p.is_file()
    ]


def _code_files_under(repo_root: Path, directory: Path):
    if not directory.is_dir():
        return []
    out = []
    for p in directory.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(directory).parts
        if p.name.startswith("."):
            continue
        if "__pycache__" in rel_parts:
            continue
        out.append(p.relative_to(repo_root).as_posix())
    return out


def _expected_hash(repo_root: Path, mode: str = "cold") -> str:
    bar = repo_root / "specs" / "components" / "bar"
    foo = repo_root / "specs" / "components" / "foo"

    paths = set()
    # Target's own documents.
    for f in (bar / "component.md", bar / "constraints.md"):
        if f.is_file():
            paths.add(f.relative_to(repo_root).as_posix())
    paths.update(_md_files_under(repo_root, bar / "requirements"))
    paths.update(_md_files_under(repo_root, bar / "interface"))

    # Dependency comp-foo: component.md, interface/*.md, sealed code at source_path.
    if (foo / "component.md").is_file():
        paths.add((foo / "component.md").relative_to(repo_root).as_posix())
    paths.update(_md_files_under(repo_root, foo / "interface"))
    paths.update(_code_files_under(repo_root, repo_root / "legacy" / "foo"))

    # Glossary.
    glossary = repo_root / "specs" / "glossary.md"
    if glossary.is_file():
        paths.add(glossary.relative_to(repo_root).as_posix())

    stream = bytearray()
    stream += mode.encode("utf-8") + b"\x00"
    for rel in sorted(paths):
        stream += rel.encode("utf-8") + b"\x00"
        stream += (repo_root / rel).read_bytes() + b"\x00"
    return "sha256:" + hashlib.sha256(bytes(stream)).hexdigest()


def _assemble_hash(repo_root: Path) -> str:
    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    value = _field(bundle, "spec_bundle_hash")
    assert isinstance(value, str)
    return value


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    _assert_lint_clean(root)
    return root


def test_spec_bundle_hash_matches_defined_stream(repo_root):
    actual = _assemble_hash(repo_root)
    assert actual.startswith("sha256:")
    assert actual == _expected_hash(repo_root, "cold")


def test_provenance_manifest_in_code_dir_does_not_change_hash(repo_root):
    before = _assemble_hash(repo_root)
    (repo_root / "legacy" / "foo" / ".provenance.json").write_bytes(
        b'{"anything": "at all", "spec_bundle_hash": "sha256:deadbeef"}\n'
    )
    after = _assemble_hash(repo_root)
    assert after == before
    assert after == _expected_hash(repo_root, "cold")


def test_dependency_code_change_changes_hash(repo_root):
    before = _assemble_hash(repo_root)
    foo_py = repo_root / "legacy" / "foo" / "foo.py"
    foo_py.write_bytes(foo_py.read_bytes() + b"# an extra line\n")
    after = _assemble_hash(repo_root)
    assert after != before
    assert after == _expected_hash(repo_root, "cold")