# hotdocs-criterion: sha256:a3402eb1157d3d6d50cd4a1c79b5b6d36483c17a83a72220ff96ec32aee3cdfc
import dataclasses
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


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

COMPONENT_MD = (
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

REQUIREMENT_MD = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

ACCEPTANCE_MD = (
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

LIBRARY_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"


def build_corpus(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (specs / "glossary.md").write_text(GLOSSARY, encoding="utf-8")
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD, encoding="utf-8")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD, encoding="utf-8")
    (comp / "interface" / "library.md").write_text(LIBRARY_MD, encoding="utf-8")
    (comp / "constraints.md").write_text(CONSTRAINTS_MD, encoding="utf-8")


def field_names(bundle):
    if isinstance(bundle, dict):
        return list(bundle.keys())
    if dataclasses.is_dataclass(bundle):
        return [f.name for f in dataclasses.fields(bundle)]
    return list(bundle.keys())


def collect_strings(value, out):
    if value is None:
        return
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                out.append(k)
            collect_strings(v, out)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            collect_strings(v, out)
    else:
        out.append(str(value))


def test_ac_assemble_001_cold_bundle_includes_spec_excludes_acceptance(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    spec_text = field(bundle, "spec")
    interface_text = field(bundle, "interface")
    constraints_text = field(bundle, "constraints")

    # Spec: component.md body and requirements/ content.
    assert isinstance(spec_text, str)
    assert "Foo doubles a number." in spec_text
    assert "MUST return `2 * x`" in spec_text

    # Interface content.
    assert isinstance(interface_text, str)
    assert "foo(x: int) -> int" in interface_text

    # Constraints content.
    assert isinstance(constraints_text, str)
    assert "None." in constraints_text

    # No field derived from acceptance/.
    names = field_names(bundle)
    for name in names:
        lowered = name.lower()
        assert "acceptance" not in lowered, name
        assert "criteri" not in lowered, name

    strings = []
    for name in names:
        collect_strings(field(bundle, name), strings)
    joined = "\n".join(strings)
    assert "AC-FOO-001" not in joined
    assert "Given x = 2" not in joined
    assert "When foo(x) is called" not in joined
    assert "Then it returns 4" not in joined
    assert "Kind: generated-test" not in joined
    assert "Covers: R-FOO-001" not in joined