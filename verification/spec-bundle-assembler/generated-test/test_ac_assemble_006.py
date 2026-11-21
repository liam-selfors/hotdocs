# hotdocs-criterion: sha256:69373e5a8b51a90a9ec262ed4d1b61e198283059aa49aee168622fdc6076cae2
import importlib.util
import json
import sys
from pathlib import Path

import spec_bundle_assembler


FIELDS = [
    "component_id",
    "spec_bundle_hash",
    "spec",
    "interface",
    "constraints",
    "dependency_interfaces",
    "dependency_context",
    "dependency_usage",
    "vars",
    "glossary",
    "hint_code",
]


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
    return load_module(path, "spec_linter")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def library_md(signature):
    return "# Library\n\n```\n" + signature + "\n```\n"


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")

    foo = specs / "components" / "foo"
    write(foo / "component.md", component_md("comp-foo", "Foo", "legacy/foo/", "[]", "Foo doubles a number."))
    write(foo / "requirements" / "R-FOO-001.md", requirement_md("R-FOO-001", "`foo(x)` MUST return `2 * x`."))
    write(foo / "acceptance" / "AC-FOO-001.md",
          acceptance_md("AC-FOO-001", "R-FOO-001", "x = 2", "foo(x) is called", "it returns 4"))
    write(foo / "interface" / "library.md", library_md("foo(x: int) -> int"))
    write(foo / "constraints.md", "# Constraints\n\nNone.\n")

    bar = specs / "components" / "bar"
    write(bar / "component.md",
          component_md("comp-bar", "Bar", "legacy/bar/", "[comp-foo]", "Bar adds one to a doubled number."))
    write(bar / "requirements" / "R-BAR-001.md", requirement_md("R-BAR-001", "`bar(x)` MUST return `2 * x + 1`."))
    write(bar / "acceptance" / "AC-BAR-001.md",
          acceptance_md("AC-BAR-001", "R-BAR-001", "x = 2", "bar(x) is called", "it returns 5"))
    write(bar / "interface" / "library.md", library_md("bar(x: int) -> int"))
    write(bar / "constraints.md", "# Constraints\n\nNone.\n")


def snapshot_files(repo_root):
    return {
        str(p.relative_to(repo_root)): p.read_bytes()
        for p in sorted(repo_root.rglob("*"))
        if p.is_file()
    }


def bundle_bytes(bundle):
    data = {name: field(bundle, name) for name in FIELDS}
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def test_ac_assemble_006_assemble_is_deterministic(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    before = snapshot_files(repo_root)

    for component_id in ("comp-foo", "comp-bar"):
        first = spec_bundle_assembler.assemble(component_id, repo_root)
        second = spec_bundle_assembler.assemble(component_id, repo_root)

        assert field(first, "component_id") == component_id
        assert field(second, "component_id") == component_id

        first_bytes = bundle_bytes(first)
        second_bytes = bundle_bytes(second)
        assert first_bytes == second_bytes

        for name in FIELDS:
            assert field(first, name) == field(second, name), name

        hash_value = field(first, "spec_bundle_hash")
        assert isinstance(hash_value, str) and hash_value.startswith("sha256:")
        assert hash_value == field(second, "spec_bundle_hash")

    # The corpus really was unchanged between and across the runs.
    assert snapshot_files(repo_root) == before

    # Explicit cold mode also yields the same bytes as the default.
    default_bundle = spec_bundle_assembler.assemble("comp-bar", repo_root)
    cold_bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    assert bundle_bytes(default_bundle) == bundle_bytes(cold_bundle)