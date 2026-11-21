# hotdocs-criterion: sha256:2baef4bc8b85b0ac7a13eeca53bde9590129d25eea991ef2978409afed31dc62
import dataclasses
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


GEN_MARKER = "GENERATED_CODE_MARKER_ZQX"
CONSTRAINT_MARKER = "CONSTRAINT_MARKER_QWV"
OTHER_REQ_PHRASE = "MUST return `2 * x`"
OTHER_REQ_PHRASE_PLAIN = "2 * x"
TARGET_REQ_PHRASE = "MUST raise `TypeError` when `x` is not an int"
TARGET_CRIT_PHRASE = "When foo(x) is called with a string"
TARGET_CRIT_THEN = "Then it raises TypeError"
INTERFACE_SIG = "foo(x: int) -> int"
GLOSSARY_PHRASE = "a test term."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
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
        "Foo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — `foo(x)` MUST raise `TypeError` when `x` is not an int.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
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
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = \"a\"\n"
        "When foo(x) is called with a string\n"
        "Then it raises TypeError\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n\nNone. " + CONSTRAINT_MARKER + "\n",
    )
    # Existing generated content for the component.
    write(
        repo_root / "gen" / "foo" / "foo.py",
        "# " + GEN_MARKER + "\n"
        "def foo(x):\n"
        "    return 2 * x\n",
    )
    write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n"
        "    return 2 * x\n",
    )


def all_text(value):
    out = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            out.append(str(k))
            out.extend(all_text(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            out.extend(all_text(v))
    elif value is not None:
        out.append(str(value))
    return out


def test_ac_assemble_009_criterion_bundle_is_narrow(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-002", repo_root)

    # Shape: dataclass with exactly the documented CriterionBundle fields.
    expected_names = [
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
        "testing",
    ]
    if dataclasses.is_dataclass(bundle):
        names = [f.name for f in dataclasses.fields(bundle)]
        assert names == expected_names
    for forbidden in ("constraints", "spec", "hint_code", "vars", "dependency_context", "dependency_usage"):
        if dataclasses.is_dataclass(bundle):
            assert forbidden not in [f.name for f in dataclasses.fields(bundle)]

    # Contains this criterion's text.
    criterion_text = field(bundle, "criterion_text")
    assert TARGET_CRIT_PHRASE in criterion_text
    assert TARGET_CRIT_THEN in criterion_text

    # Contains its covered requirement's text.
    assert field(bundle, "covers") == "R-FOO-002"
    requirement_text = field(bundle, "requirement_text")
    assert TARGET_REQ_PHRASE in requirement_text

    # Contains the interface.
    assert INTERFACE_SIG in field(bundle, "interface")

    # Contains the glossary.
    assert GLOSSARY_PHRASE in field(bundle, "glossary")

    # Contains nothing from gen/, other requirements, or constraints.md.
    texts = []
    for name in expected_names:
        texts.extend(all_text(field(bundle, name)))
    joined = "\n".join(texts)
    assert GEN_MARKER not in joined
    assert CONSTRAINT_MARKER not in joined
    assert OTHER_REQ_PHRASE not in joined
    assert OTHER_REQ_PHRASE_PLAIN not in joined
    assert "R-FOO-001" not in requirement_text