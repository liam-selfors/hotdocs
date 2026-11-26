# hotdocs-criterion: sha256:729798fb51ac84d70439ea9c04de09b1ddbb0b52a026f71696009fe48e107031
import importlib.util
import sys
from pathlib import Path

import pytest

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


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


RULES_REL = "specs/architecture/rules.md"
RULES_TEXT = (
    "---\n"
    "id: arch-rules\n"
    "title: Rules\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Rules\n"
    "\n"
    "Foo rounds down.\n"
)


def build(repo_root, implements_path):
    files = component_files("foo")
    lib = "specs/components/foo/interface/library.md"
    files[lib] = files[lib] + "\nImplements: `" + implements_path + "`\n"
    files[RULES_REL] = RULES_TEXT
    write_fixture(repo_root, files)


def assert_appended(interface):
    marker = "\n## Implements: specs/architecture/rules.md\n\n"
    assert marker in interface, interface
    rest = interface[interface.index(marker) + len(marker):]
    full_text = (Path(".") / RULES_TEXT).name if False else RULES_TEXT
    body = full_text.rstrip()
    assert rest.startswith(body), rest
    assert rest[len(body):].strip() == "", rest


def test_implements_document_appended_to_both_bundles(tmp_path):
    repo_root = tmp_path
    build(repo_root, RULES_REL)
    # The file's full text as read from disk.
    assert (repo_root / RULES_REL).read_text(encoding="utf-8") == RULES_TEXT

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    assert_appended(field(bundle, "interface"))

    cbundle = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert_appended(field(cbundle, "interface"))


def test_missing_implements_document_raises_precondition_failure(tmp_path):
    repo_root = tmp_path
    build(repo_root, "specs/architecture/missing.md")
    assert not (repo_root / "specs/architecture/missing.md").exists()

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble("comp-foo", repo_root)
    names = [cls.__name__ for cls in type(excinfo.value).__mro__]
    assert "PreconditionFailure" in names, names