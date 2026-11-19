# hotdocs-criterion: sha256:6693e70b6f0079f807a205ba0aefce0a15a3ccfca8dfb65a1b7780e2c6af4fd3
import hashlib
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(repo_root, rel, text):
    p = repo_root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def component_md(comp_id, title, source_path, depends_on, purpose):
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
        "\n"
        + purpose + "\n"
    )


def requirement_md(rid, func):
    return "# " + rid + "\n\n**" + rid + "** — `" + func + "(x)` MUST return `2 * x`.\n"


def acceptance_md(acid, rid, func):
    return (
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When " + func + "(x) is called\n"
        "Then it returns 4\n"
        "```\n"
    )


def library_md(func):
    return "# Library\n\n```\n" + func + "(x: int) -> int\n```\n"


CONSTRAINTS = "# Constraints\n\nNone.\n"


def build_fixture(repo_root):
    write(repo_root, "specs/glossary.md", GLOSSARY)

    foo = "specs/components/foo/"
    write(repo_root, foo + "component.md",
          component_md("comp-foo", "Foo", "legacy/foo/", "[]", "Foo doubles a number."))
    write(repo_root, foo + "requirements/R-FOO-001.md", requirement_md("R-FOO-001", "foo"))
    write(repo_root, foo + "acceptance/AC-FOO-001.md", acceptance_md("AC-FOO-001", "R-FOO-001", "foo"))
    write(repo_root, foo + "interface/library.md", library_md("foo"))
    write(repo_root, foo + "constraints.md", CONSTRAINTS)

    bar = "specs/components/bar/"
    write(repo_root, bar + "component.md",
          component_md("comp-bar", "Bar", "legacy/bar/", "[comp-foo]", "Bar doubles a number."))
    write(repo_root, bar + "requirements/R-BAR-001.md", requirement_md("R-BAR-001", "bar"))
    write(repo_root, bar + "acceptance/AC-BAR-001.md", acceptance_md("AC-BAR-001", "R-BAR-001", "bar"))
    write(repo_root, bar + "interface/library.md", library_md("bar"))
    write(repo_root, bar + "constraints.md", CONSTRAINTS)

    write(repo_root, "legacy/foo/foo.py", "def foo(x): return 2 * x\n")


def md_files_under(repo_root, rel_dir):
    d = repo_root / rel_dir
    if not d.is_dir():
        return []
    return [p for p in d.rglob("*.md") if p.is_file()]


def code_files_under(repo_root, rel_dir):
    d = repo_root / rel_dir
    if not d.is_dir():
        return []
    out = []
    for p in d.rglob("*"):
        if not p.is_file():
            continue
        parts = p.relative_to(d).parts
        if any(part.startswith(".") for part in parts):
            continue
        if "__pycache__" in parts:
            continue
        out.append(p)
    return out


def expected_hash(repo_root, mode="cold"):
    files = []
    bar = repo_root / "specs/components/bar"
    for name in ("component.md", "constraints.md"):
        if (bar / name).is_file():
            files.append(bar / name)
    files += md_files_under(repo_root, "specs/components/bar/requirements")
    files += md_files_under(repo_root, "specs/components/bar/interface")

    foo = repo_root / "specs/components/foo"
    if (foo / "component.md").is_file():
        files.append(foo / "component.md")
    files += md_files_under(repo_root, "specs/components/foo/interface")
    files += code_files_under(repo_root, "legacy/foo")

    glossary = repo_root / "specs/glossary.md"
    if glossary.is_file():
        files.append(glossary)

    rels = sorted(set(p.relative_to(repo_root).as_posix() for p in files))
    h = hashlib.sha256()
    h.update(mode.encode("utf-8") + b"\0")
    for rel in rels:
        h.update(rel.encode("utf-8") + b"\0")
        h.update((repo_root / rel).read_bytes() + b"\0")
    return "sha256:" + h.hexdigest()


def prepare(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0
    return repo_root


def run_hash(repo_root):
    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    return field(bundle, "spec_bundle_hash")


def test_spec_bundle_hash_matches_defined_stream(tmp_path):
    repo_root = prepare(tmp_path)
    got = run_hash(repo_root)
    assert got == expected_hash(repo_root, "cold")


def test_provenance_manifest_in_code_dir_does_not_change_hash(tmp_path):
    repo_root = prepare(tmp_path)
    before = run_hash(repo_root)
    write(repo_root, "legacy/foo/.provenance.json", '{"anything": [1, 2, 3]}\n')
    after = run_hash(repo_root)
    assert after == before


def test_code_change_in_dependency_changes_hash(tmp_path):
    repo_root = prepare(tmp_path)
    before = run_hash(repo_root)
    foo_py = repo_root / "legacy/foo/foo.py"
    foo_py.write_text(foo_py.read_text(encoding="utf-8") + "# an extra line\n", encoding="utf-8")
    after = run_hash(repo_root)
    assert after != before