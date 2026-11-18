# hotdocs-criterion: sha256:cb069d3f9c798b47763721da9a5e185849326dd53eb3cbbcfe63e7ca5507ec38
import hashlib
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
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


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

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
    "Bar quadruples a number.\n"
)

FOO_REQ = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
BAR_REQ = "# R-BAR-001\n\n**R-BAR-001** \u2014 `bar(x)` MUST return `4 * x`.\n"

FOO_AC = (
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

BAR_AC = (
    "# AC-BAR-001\n"
    "\n"
    "Covers: R-BAR-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When bar(x) is called\n"
    "Then it returns 8\n"
    "```\n"
)

FOO_LIB = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
BAR_LIB = "# Library\n\n```\nbar(x: int) -> int\n```\n"
CONSTRAINTS = "# Constraints\n\nNone.\n"

FOO_PY = "def foo(x): return 2 * x\n"
BAR_PY = "def bar(x): return 4 * x\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)

    foo = repo_root / "specs" / "components" / "foo"
    write(foo / "component.md", FOO_COMPONENT)
    write(foo / "requirements" / "R-FOO-001.md", FOO_REQ)
    write(foo / "acceptance" / "AC-FOO-001.md", FOO_AC)
    write(foo / "interface" / "library.md", FOO_LIB)
    write(foo / "constraints.md", CONSTRAINTS)

    bar = repo_root / "specs" / "components" / "bar"
    write(bar / "component.md", BAR_COMPONENT)
    write(bar / "requirements" / "R-BAR-001.md", BAR_REQ)
    write(bar / "acceptance" / "AC-BAR-001.md", BAR_AC)
    write(bar / "interface" / "library.md", BAR_LIB)
    write(bar / "constraints.md", CONSTRAINTS)

    write(repo_root / "legacy" / "foo" / "foo.py", FOO_PY)
    write(repo_root / "legacy" / "bar" / "bar.py", BAR_PY)


def md_files_under(repo_root, directory):
    if not directory.is_dir():
        return []
    return [
        p.relative_to(repo_root).as_posix()
        for p in directory.rglob("*.md")
        if p.is_file()
    ]


def code_files_under(repo_root, directory):
    if not directory.is_dir():
        return []
    out = []
    for p in directory.rglob("*"):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(directory).parts
        if "__pycache__" in rel_parts:
            continue
        if any(part.startswith(".") for part in rel_parts):
            continue
        out.append(p.relative_to(repo_root).as_posix())
    return out


def expected_hash(repo_root, mode="cold"):
    bar = repo_root / "specs" / "components" / "bar"
    foo = repo_root / "specs" / "components" / "foo"
    paths = set()
    # Target's own spec files.
    for p in (bar / "component.md", bar / "constraints.md"):
        if p.is_file():
            paths.add(p.relative_to(repo_root).as_posix())
    paths.update(md_files_under(repo_root, bar / "requirements"))
    paths.update(md_files_under(repo_root, bar / "interface"))
    # Dependency comp-foo: component.md, interface/*.md, sealed code dir.
    if (foo / "component.md").is_file():
        paths.add((foo / "component.md").relative_to(repo_root).as_posix())
    paths.update(md_files_under(repo_root, foo / "interface"))
    paths.update(code_files_under(repo_root, repo_root / "legacy" / "foo"))
    # Glossary.
    glossary = repo_root / "specs" / "glossary.md"
    if glossary.is_file():
        paths.add("specs/glossary.md")

    stream = mode.encode("utf-8") + b"\x00"
    for rel in sorted(paths):
        stream += rel.encode("utf-8") + b"\x00"
        stream += (repo_root / rel).read_bytes() + b"\x00"
    return "sha256:" + hashlib.sha256(stream).hexdigest()


def test_spec_bundle_hash_is_defined_stream_digest(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # Scenario 1: the hash equals the digest of the defined stream.
    expected = expected_hash(repo_root, "cold")
    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    first = field(bundle, "spec_bundle_hash")
    assert first == expected

    # Scenario 2: writing a .provenance.json in the code dir changes nothing.
    (repo_root / "legacy" / "foo" / ".provenance.json").write_text(
        '{"anything": "at all", "n": 1}\n', encoding="utf-8"
    )
    bundle2 = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    second = field(bundle2, "spec_bundle_hash")
    assert second == first

    # Scenario 3: adding a line to legacy/foo/foo.py changes the hash.
    foo_py = repo_root / "legacy" / "foo" / "foo.py"
    foo_py.write_text(FOO_PY + "# an extra line\n", encoding="utf-8")
    bundle3 = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    third = field(bundle3, "spec_bundle_hash")
    assert third != first