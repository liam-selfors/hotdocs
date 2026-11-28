# hotdocs-criterion: sha256:98a6c7c59152a661cafb8ae7f516927f5febff54006acf98a63b9b257736c7ef
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


def _lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def _field_names(bundle):
    if isinstance(bundle, dict):
        return list(bundle.keys())
    if dataclasses.is_dataclass(bundle):
        return [f.name for f in dataclasses.fields(bundle)]
    return list(bundle.keys())


def _all_strings(value):
    out = []
    if value is None:
        return out
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            out.extend(_all_strings(k))
            out.extend(_all_strings(v))
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            out.extend(_all_strings(v))
    else:
        out.append(str(value))
    return out


def test_ac_assemble_001_cold_bundle_has_spec_interface_constraints_and_no_acceptance(tmp_path):
    repo_root = tmp_path
    write_fixture(repo_root, component_files("foo"))
    _lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    assert field(bundle, "component_id") == "comp-foo"

    spec_text = field(bundle, "spec")
    interface_text = field(bundle, "interface")
    constraints_text = field(bundle, "constraints")

    assert isinstance(spec_text, str)
    assert isinstance(interface_text, str)
    assert isinstance(constraints_text, str)

    # component.md body and requirements/ content are in spec
    assert "Foo doubles a number." in spec_text
    assert "## Purpose" in spec_text
    assert "`foo(x)` MUST return `2 * x`." in spec_text
    assert "R-FOO-001" in spec_text

    # interface/ content
    assert "foo(x: int) -> int" in interface_text

    # constraints.md body
    assert "None." in constraints_text
    assert "# Constraints" in constraints_text

    # cold mode: no hint code
    assert field(bundle, "hint_code") is None

    # No field derived from acceptance/
    names = _field_names(bundle)
    for name in names:
        lowered = name.lower()
        assert "acceptance" not in lowered, name
        assert "criterion" not in lowered, name
        assert "criteria" not in lowered, name

    acceptance_markers = [
        "AC-FOO-001",
        "Kind: generated-test",
        "Given x = 2",
        "When foo(x) is called",
        "Then it returns 4",
        "```gherkin",
    ]
    for name in names:
        for text in _all_strings(field(bundle, name)):
            for marker in acceptance_markers:
                assert marker not in text, (name, marker)