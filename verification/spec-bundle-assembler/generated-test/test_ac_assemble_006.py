# hotdocs-criterion: sha256:3ce1427643cdd075e9ec6ce15ceeb478c92121a66598b1405bd56dabe50ae23b
import dataclasses
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
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    if (base / "spec_linter.py").is_file():
        path = base / "spec_linter.py"
    else:
        path = base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_component(repo_root, slug, upper, title, purpose, depends_on, req_text):
    comp_dir = repo_root / "specs" / "components" / slug
    write(
        comp_dir / "component.md",
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "depends_on: " + depends_on + "\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    write(
        comp_dir / "requirements" / (rid + ".md"),
        "# " + rid + "\n"
        + "\n"
        + "**" + rid + "** \u2014 " + req_text + "\n",
    )
    write(
        comp_dir / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given x = 2\n"
        + "When " + slug + "(x) is called\n"
        + "Then it returns 4\n"
        + "```\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + "```\n"
        + slug + "(x: int) -> int\n"
        + "```\n",
    )
    write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        + "\n"
        + "None.\n",
    )


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        + "\n"
        + "- **Foo** \u2014 a test term.\n",
    )
    build_component(
        repo_root, "foo", "FOO", "Foo", "Foo doubles a number.", "[]",
        "`foo(x)` MUST return `2 * x`.",
    )
    build_component(
        repo_root, "bar", "BAR", "Bar", "Bar doubles a number using Foo.",
        "[comp-foo]",
        "`bar(x)` MUST return `2 * x`.",
    )


def serialize(bundle):
    data = {}
    for name in FIELDS:
        data[name] = field(bundle, name)
    return json.dumps(data, ensure_ascii=False, default=repr).encode("utf-8")


def snapshot(repo_root):
    files = {}
    for p in sorted(repo_root.rglob("*")):
        if p.is_file():
            files[p.relative_to(repo_root).as_posix()] = p.read_bytes()
    return files


def test_assemble_twice_on_unchanged_corpus_is_byte_identical(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    for component_id in ("comp-foo", "comp-bar"):
        before = snapshot(repo_root)
        first = spec_bundle_assembler.assemble(component_id, repo_root)
        second = spec_bundle_assembler.assemble(component_id, repo_root)
        # The corpus really is unchanged between the two runs.
        assert snapshot(repo_root) == before

        assert field(first, "component_id") == component_id
        assert field(first, "spec_bundle_hash") == field(second, "spec_bundle_hash")
        for name in FIELDS:
            assert field(first, name) == field(second, name), name
        assert serialize(first) == serialize(second)

        if dataclasses.is_dataclass(first) and dataclasses.is_dataclass(second):
            assert dataclasses.asdict(first) == dataclasses.asdict(second)