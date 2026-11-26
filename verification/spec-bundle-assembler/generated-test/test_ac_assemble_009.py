# hotdocs-criterion: sha256:a4d3a9a23fe55b98aa1f1283ee626ac14c684238ca4e01864deebd4627e1ade6
import dataclasses
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def component_files(slug, depends_on="[]", extra_frontmatter="", purpose="Foo doubles a number."):
    """The files of one fixture component, keyed by path under repo_root."""
    upper = slug.upper()
    base = f"specs/components/{slug}/"
    return {
        base + "component.md": (
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            f"depends_on: {depends_on}\n"
            + extra_frontmatter +
            "---\n"
            "\n"
            f"# {slug.capitalize()}\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"{purpose}\n"
        ),
        base + f"requirements/R-{upper}-001.md": (
            f"# R-{upper}-001\n"
            "\n"
            f"**R-{upper}-001** — `foo(x)` MUST return `2 * x`.\n"
        ),
        base + f"acceptance/AC-{upper}-001.md": (
            f"# AC-{upper}-001\n"
            "\n"
            f"Covers: R-{upper}-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
            "```\n"
        ),
        base + "interface/library.md": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        base + "constraints.md": "# Constraints\n\nNone.\n",
    }


def write_fixture(repo_root, files):
    files = {"specs/glossary.md": "# Glossary\n\n- **Foo** — a test term.\n", **files}
    for rel, text in files.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def field_names(value):
    if isinstance(value, dict):
        return list(value.keys())
    if dataclasses.is_dataclass(value):
        return [f.name for f in dataclasses.fields(value)]
    return list(value.keys())


def all_strings(value):
    out = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            out.extend(all_strings(k))
            out.extend(all_strings(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            out.extend(all_strings(v))
    return out


def lint_fixture(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


GEN_MARKER = "pelicanforge"
OTHER_REQ_MARKER = "quillzebra"
CONSTRAINTS_MARKER = "ottervault"


def test_criterion_bundle_contains_only_its_own_inputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    files = component_files("foo")
    base = "specs/components/foo/"
    files[base + "requirements/R-FOO-002.md"] = (
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — `foo(x)` MUST return `0` when x is `0` (" + OTHER_REQ_MARKER + ").\n"
    )
    files[base + "acceptance/AC-FOO-002.md"] = (
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 0\n"
        "When foo(x) is called\n"
        "Then it returns 0\n"
        "```\n"
    )
    files[base + "constraints.md"] = (
        "# Constraints\n\nNo network access, ever (" + CONSTRAINTS_MARKER + ").\n"
    )
    write_fixture(repo_root, files)

    gen_file = repo_root / "gen" / "foo" / "foo.py"
    gen_file.parent.mkdir(parents=True, exist_ok=True)
    gen_file.write_text(
        "def foo(x):\n    return 2 * x  # " + GEN_MARKER + "\n", encoding="utf-8"
    )

    lint_fixture(repo_root)

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    assert field(bundle, "component_id") == "comp-foo"
    assert field(bundle, "criterion_id") == "AC-FOO-001"
    assert field(bundle, "covers") == "R-FOO-001"

    criterion_text = field(bundle, "criterion_text")
    assert "Given x = 2" in criterion_text
    assert "Then it returns 4" in criterion_text

    requirement_text = field(bundle, "requirement_text")
    assert "`foo(x)` MUST return `2 * x`." in requirement_text

    assert "foo(x: int) -> int" in field(bundle, "interface")
    assert "a test term" in field(bundle, "glossary")

    allowed = {
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary",
        "dependency_interfaces", "testing",
    }
    names = field_names(bundle)
    assert set(names) <= allowed, sorted(set(names) - allowed)
    for forbidden in ("constraints", "hint_code", "spec"):
        assert forbidden not in names

    texts = []
    for name in names:
        texts.extend(all_strings(field(bundle, name)))
    blob = "\n".join(texts)

    assert GEN_MARKER not in blob
    assert OTHER_REQ_MARKER not in blob
    assert "R-FOO-002" not in field(bundle, "requirement_text")
    assert CONSTRAINTS_MARKER not in blob