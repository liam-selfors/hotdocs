# hotdocs-criterion: sha256:f6038c263c5afc9b7d592b125a3478d679b58af64c7c3a20123915d7df193c13
import importlib.util
import sys
from pathlib import Path

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(cid, title, slug, depends_on, purpose):
    return (
        "---\n"
        "id: " + cid + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "depends_on: " + depends_on + "\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose + "\n"
    )


def build_corpus(repo_root):
    specs = repo_root / "specs"

    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** \u2014 a test term, kept in `glossed_word`.\n",
    )

    # comp-foo
    foo = specs / "components" / "foo"
    write(foo / "component.md", component_md("comp-foo", "Foo", "foo", "[]", "Foo doubles a number."))
    write(
        foo / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        foo / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        foo / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "Returns `dep_word`.\n",
    )
    write(foo / "constraints.md", "# Constraints\n\nNone.\n")

    # comp-baz
    baz = specs / "components" / "baz"
    write(
        baz / "component.md",
        component_md("comp-baz", "Baz", "baz", "[comp-foo]", "Baz returns a value."),
    )
    write(
        baz / "requirements" / "R-BAZ-001.md",
        "# R-BAZ-001\n"
        "\n"
        "**R-BAZ-001** \u2014 `baz(x)` MUST return `seen`.\n",
    )
    write(
        baz / "acceptance" / "AC-BAZ-001.md",
        "# AC-BAZ-001\n"
        "\n"
        "Covers: R-BAZ-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given `given_word` is set\n"
        "When baz(x) is called\n"
        "Then it returns `dep_word`, `glossed_word`, `iface_word`,\n"
        "  `nowhere_word` and `seen<x>`\n"
        "```\n",
    )
    write(
        baz / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "baz(x: int) -> int\n"
        "```\n"
        "\n"
        "Returns `iface_word`.\n",
    )
    write(baz / "constraints.md", "# Constraints\n\nNone.\n")


def load_linter():
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def test_ac_review_009_only_invisible_token_reported(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    report = spec_reviewer.check(["comp-baz"], repo_root)

    findings = field(report, "findings")
    tokens = [
        field(f, "token")
        for f in findings
        if field(f, "criterion_id") == "AC-BAZ-001"
        and field(f, "kind") == "invisible_reference"
    ]
    assert tokens == ["nowhere_word"]