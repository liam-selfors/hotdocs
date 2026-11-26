# hotdocs-criterion: sha256:7d985e91cb73ce3725561fee38baabd931183e43be611a1fa175333433c20fe7
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


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def lint_fixture(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


PURPOSE_TEXT = "Foo doubles a number, marker purposeplum."
SCOPE_TEXT = "Scope marker scopequince covers integer inputs only."
RATIONALE_TEXT = "Rationale marker rationalezebra explains why doubling."
OPEN_QUESTIONS_TEXT = "Open question marker openquestionyak about overflow."
CHANGE_LOG_TEXT = "Change log marker changelogwombat first draft."


def test_ac_assemble_012_cold_spec_excludes_rationale_open_questions_change_log(tmp_path):
    repo_root = tmp_path
    files = component_files("foo", purpose=PURPOSE_TEXT)
    key = "specs/components/foo/component.md"
    files[key] = (
        files[key]
        + "\n## Scope\n\n" + SCOPE_TEXT + "\n"
        + "\n## Rationale\n\n" + RATIONALE_TEXT + "\n"
        + "\n## Open questions\n\n" + OPEN_QUESTIONS_TEXT + "\n"
        + "\n## Change log\n\n" + CHANGE_LOG_TEXT + "\n"
    )
    write_fixture(repo_root, files)

    lint_fixture(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    spec_text = field(bundle, "spec")

    assert "purposeplum" in spec_text
    assert "scopequince" in spec_text
    assert "rationalezebra" not in spec_text
    assert "openquestionyak" not in spec_text
    assert "changelogwombat" not in spec_text