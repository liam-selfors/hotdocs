# hotdocs-criterion: sha256:3ab83a8ba095f33a8f6dcf0406ca511f25c648ce66de98136327215b957b779e
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


def lint_fixture(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


PURPOSE_MARKER = "Foo doubles a number via PURPOSEMARKERFOO."
REQ_MARKER = "REQMARKERFOO"
CONSTRAINT_MARKER = "CONSTRAINTMARKERFOO"
IFACE_MARKER = "IFACEMARKERFOO"


def test_dependency_interfaces_holds_only_interface_content(tmp_path):
    repo_root = tmp_path
    foo = component_files("foo", purpose=PURPOSE_MARKER)
    req_path = "specs/components/foo/requirements/R-FOO-001.md"
    foo[req_path] = foo[req_path] + "\n" + REQ_MARKER + " is extra requirement prose.\n"
    foo["specs/components/foo/constraints.md"] = (
        "# Constraints\n\n" + CONSTRAINT_MARKER + " applies here.\n"
    )
    foo_interface = (
        "# Library\n\n```\nfoo(x: int) -> int\n```\n\n" + IFACE_MARKER + " describes foo.\n"
    )
    foo["specs/components/foo/interface/library.md"] = foo_interface

    baz = component_files("baz", depends_on="[comp-foo]")
    files = {}
    files.update(foo)
    files.update(baz)
    write_fixture(repo_root, files)

    lint_fixture(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-baz", repo_root)

    dep_ifaces = field(bundle, "dependency_interfaces")
    assert set(dep_ifaces.keys()) == {"comp-foo"}
    text = dep_ifaces["comp-foo"]
    assert isinstance(text, str)

    # The dependency's interface/ content is present.
    assert IFACE_MARKER in text
    assert "foo(x: int) -> int" in text

    # Never its component.md (frontmatter or body).
    assert "PURPOSEMARKERFOO" not in text
    assert "## Purpose" not in text
    assert "id: comp-foo" not in text
    assert "owners: [team-a]" not in text
    assert "source_path: legacy/foo/" not in text
    assert "# Foo\n" not in text

    # Never its requirements/.
    assert REQ_MARKER not in text
    assert "R-FOO-001" not in text
    assert "MUST return" not in text

    # Never its constraints.md.
    assert CONSTRAINT_MARKER not in text
    assert "# Constraints" not in text