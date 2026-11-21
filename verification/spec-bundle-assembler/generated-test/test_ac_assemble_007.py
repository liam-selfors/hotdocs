# hotdocs-criterion: sha256:a659cf1a95c2440913869d21c1015c7575309e0311a642f1e03595611d1b8e1e
import spec_bundle_assembler

import hashlib
import importlib.util
import sys
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


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
    p.write_bytes(text.encode("utf-8"))


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def component_md(comp_id, title, source_path, depends_on, heading, purpose):
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
        "# " + heading + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose + "\n"
    )


def requirement_md(rid, text):
    return "# " + rid + "\n\n**" + rid + "** — " + text + "\n"


def acceptance_md(acid, rid, given, when, then):
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


def library_md(sig):
    return "# Library\n\n```\n" + sig + "\n```\n"


CONSTRAINTS = "# Constraints\n\nNone.\n"


def build_fixture(repo_root):
    write(repo_root, "specs/glossary.md", GLOSSARY)

    foo = "specs/components/foo/"
    write(repo_root, foo + "component.md",
          component_md("comp-foo", "Foo", "legacy/foo/", "[]", "Foo", "Foo doubles a number."))
    write(repo_root, foo + "requirements/R-FOO-001.md",
          requirement_md("R-FOO-001", "`foo(x)` MUST return `2 * x`."))
    write(repo_root, foo + "acceptance/AC-FOO-001.md",
          acceptance_md("AC-FOO-001", "R-FOO-001", "x = 2", "foo(x) is called", "it returns 4"))
    write(repo_root, foo + "interface/library.md", library_md("foo(x: int) -> int"))
    write(repo_root, foo + "constraints.md", CONSTRAINTS)
    write(repo_root, "legacy/foo/foo.py", "def foo(x): return 2 * x\n")

    bar = "specs/components/bar/"
    write(repo_root, bar + "component.md",
          component_md("comp-bar", "Bar", "legacy/bar/", "[comp-foo]", "Bar", "Bar quadruples a number."))
    write(repo_root, bar + "requirements/R-BAR-001.md",
          requirement_md("R-BAR-001", "`bar(x)` MUST return `4 * x`."))
    write(repo_root, bar + "acceptance/AC-BAR-001.md",
          acceptance_md("AC-BAR-001", "R-BAR-001", "x = 2", "bar(x) is called", "it returns 8"))
    write(repo_root, bar + "interface/library.md", library_md("bar(x: int) -> int"))
    write(repo_root, bar + "constraints.md", CONSTRAINTS)
    write(repo_root, "legacy/bar/bar.py", "def bar(x): return 4 * x\n")


def code_dir_files(repo_root, rel_dir):
    root = repo_root / rel_dir
    out = []
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = p.relative_to(root).parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            continue
        out.append(p.relative_to(repo_root).as_posix())
    return out


def md_under(repo_root, rel_dir):
    root = repo_root / rel_dir
    if not root.is_dir():
        return []
    return [p.relative_to(repo_root).as_posix() for p in root.rglob("*.md") if p.is_file()]


def expected_hash(repo_root, mode="cold"):
    paths = set()
    bar = "specs/components/bar/"
    for rel in (bar + "component.md", bar + "constraints.md"):
        if (repo_root / rel).is_file():
            paths.add(rel)
    paths.update(md_under(repo_root, bar + "requirements"))
    paths.update(md_under(repo_root, bar + "interface"))

    foo = "specs/components/foo/"
    if (repo_root / (foo + "component.md")).is_file():
        paths.add(foo + "component.md")
    paths.update(md_under(repo_root, foo + "interface"))
    paths.update(code_dir_files(repo_root, "legacy/foo"))

    if (repo_root / "specs/glossary.md").is_file():
        paths.add("specs/glossary.md")

    stream = mode.encode("utf-8") + b"\0"
    for rel in sorted(paths):
        stream += rel.encode("utf-8") + b"\0" + (repo_root / rel).read_bytes() + b"\0"
    return "sha256:" + hashlib.sha256(stream).hexdigest()


def test_ac_assemble_007_spec_bundle_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    h1 = field(bundle, "spec_bundle_hash")
    assert h1 == expected_hash(repo_root, "cold")

    # A manifest in the dependency's code directory changes no hash.
    (repo_root / "legacy/foo/.provenance.json").write_bytes(b'{"anything": [1, 2, 3]}\n')
    bundle2 = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    h2 = field(bundle2, "spec_bundle_hash")
    assert h2 == h1

    # A change to the dependency's code changes the hash.
    foo_py = repo_root / "legacy/foo/foo.py"
    foo_py.write_bytes(foo_py.read_bytes() + b"# an extra line\n")
    bundle3 = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    h3 = field(bundle3, "spec_bundle_hash")
    assert h3 != h1