# hotdocs-criterion: sha256:3ce1427643cdd075e9ec6ce15ceeb478c92121a66598b1405bd56dabe50ae23b
"""AC-ASSEMBLE-006: assembling the same component twice over an unchanged
corpus yields byte-identical SpecBundles (R-ASSEMBLE-006)."""

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE_FIELDS = [
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


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
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
    return spec_linter


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def write_component(repo_root, slug, title, upper, depends_on, purpose):
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
        + "depends_on: [" + depends_on + "]\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + purpose + "\n",
    )
    for n in ("001", "002"):
        rid = "R-" + upper + "-" + n
        acid = "AC-" + upper + "-" + n
        write(
            comp_dir / "requirements" / (rid + ".md"),
            "# " + rid + "\n"
            + "\n"
            + "**" + rid + "** — `" + slug + "(x)` MUST return `2 * x`.\n",
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
        + "- **Foo** — a test term.\n",
    )
    write_component(repo_root, "foo", "Foo", "FOO", "", "Foo doubles a number.")
    write_component(
        repo_root, "bar", "Bar", "BAR", "comp-foo", "Bar doubles a number too."
    )


def snapshot_files(repo_root):
    return {
        str(p.relative_to(repo_root)): p.read_bytes()
        for p in sorted(repo_root.rglob("*"))
        if p.is_file()
    }


def to_plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    return value


def bundle_bytes(bundle):
    plain = {name: to_plain(field(bundle, name)) for name in BUNDLE_FIELDS}
    return json.dumps(plain, ensure_ascii=False, sort_keys=False).encode("utf-8")


def test_assemble_twice_is_byte_identical(tmp_path):
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
        for name in BUNDLE_FIELDS:
            assert field(first, name) == field(second, name), name

        hash_value = field(first, "spec_bundle_hash")
        assert isinstance(hash_value, str) and hash_value.startswith("sha256:")

        assert bundle_bytes(first) == bundle_bytes(second)

    # Corpus stayed unchanged throughout (assemble has no side effects).
    assert snapshot_files(repo_root) == before


def test_cli_json_output_twice_is_byte_identical(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    argv = ["comp-bar", "--format=json", "--repo-root=" + str(repo_root)]

    capsys.readouterr()
    code1 = spec_bundle_assembler.main(list(argv))
    out1 = capsys.readouterr().out
    code2 = spec_bundle_assembler.main(list(argv))
    out2 = capsys.readouterr().out

    assert code1 == 0
    assert code2 == 0
    assert out1.encode("utf-8") == out2.encode("utf-8")
    doc = json.loads(out1)
    assert doc["component_id"] == "comp-bar"