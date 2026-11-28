# hotdocs-criterion: sha256:a53d95571d6307dd1683f2b00a1504691383a5f24d58380b9796da9c5b0f6ea5
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


VAR_BODY_LINES = [
    "# VAR-FOO-URL",
    "- **Name:** VAR-FOO-URL",
    "- **Type:** url",
    "- **Required:** required",
    "- **Description:** The zebra-quokka endpoint foo talks to.",
    "- **Sensitivity:** internal",
]


def var_file():
    return (
        "---\n"
        "id: VAR-FOO-URL\n"
        "title: Foo URL\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        + "\n\n".join(VAR_BODY_LINES)
        + "\n"
    )


def lint_fixture(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def test_bundle_vars_contains_full_var_declaration(tmp_path):
    repo_root = tmp_path
    files = component_files("foo", extra_frontmatter="uses_var: [VAR-FOO-URL]\n")
    files["specs/vars/VAR-FOO-URL.md"] = var_file()
    write_fixture(repo_root, files)

    lint_fixture(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    vars_field = field(bundle, "vars")
    assert "VAR-FOO-URL" in vars_field
    content = vars_field["VAR-FOO-URL"]
    assert isinstance(content, str)

    for line in VAR_BODY_LINES[1:]:
        assert line in content, (line, content)