# hotdocs-criterion: sha256:af88e5deec2c24e00186379d73572354bf2e40ff7ff27bd99bf95d5e2ed1c9e5
import dataclasses
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


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


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

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

REQUIREMENT = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"

ACCEPTANCE = (
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

LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS = "# Constraints\n\nNone.\n"


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "constraints.md", CONSTRAINTS)


def field_names(bundle):
    if dataclasses.is_dataclass(bundle):
        return [f.name for f in dataclasses.fields(bundle)]
    if isinstance(bundle, dict):
        return list(bundle.keys())
    return [n for n in dir(bundle) if not n.startswith("_")]


def collect_strings(value, out):
    if value is None:
        return
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            collect_strings(k, out)
            collect_strings(v, out)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            collect_strings(v, out)


def test_ac_assemble_001_cold_bundle_includes_spec_interface_constraints_not_acceptance(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    spec_text = field(bundle, "spec")
    interface_text = field(bundle, "interface")
    constraints_text = field(bundle, "constraints")

    # spec: component.md body + requirements/ content
    assert isinstance(spec_text, str)
    assert "Foo doubles a number." in spec_text
    assert "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`." in spec_text

    # interface content
    assert isinstance(interface_text, str)
    assert "foo(x: int) -> int" in interface_text

    # constraints content
    assert isinstance(constraints_text, str)
    assert "None." in constraints_text
    assert "# Constraints" in constraints_text

    # cold mode: no hint code
    assert field(bundle, "hint_code") is None

    # no field derived from acceptance/
    names = field_names(bundle)
    for name in names:
        lowered = name.lower()
        assert "acceptance" not in lowered, name
        assert "criteri" not in lowered, name

    strings = []
    for name in names:
        try:
            value = field(bundle, name)
        except (KeyError, AttributeError):
            continue
        if callable(value):
            continue
        collect_strings(value, strings)

    acceptance_markers = [
        "AC-FOO-001",
        "Covers: R-FOO-001",
        "Kind: generated-test",
        "Given x = 2",
        "When foo(x) is called",
        "Then it returns 4",
        "gherkin",
    ]
    for text in strings:
        for marker in acceptance_markers:
            assert marker not in text, "acceptance content " + repr(marker) + " leaked into bundle"