# hotdocs-criterion: sha256:992e9cdbac9bdd5735183170c046f2b7910a980aa7c08d5e049143cc4dd5c017
import importlib.util
import json
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


def _lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0, [
        (f.rule_id, f.file, f.message) for f in report.findings if f.severity == "fail"
    ]


RATIONALE_SENTENCE = "Chosen per `D13` because recomputation is slow."

BUNDLE_FIELDS = [
    "component_id",
    "spec_bundle_hash",
    "spec",
    "interface",
    "constraints",
    "dependency_interfaces",
    "dependency_context",
    "dependency_usage",
    "vars",
    "glossary",
    "hint_code",
    "spec_bundle_parts",
]


def test_ac_assemble_010_dependency_context_is_purpose_only(tmp_path):
    repo_root = tmp_path
    files = {}
    files.update(
        component_files(
            "bar",
            purpose="Caches results.\n\n## Rationale\n\n" + RATIONALE_SENTENCE,
        )
    )
    files.update(component_files("baz", depends_on="[comp-bar]"))
    files["specs/decisions/D13.md"] = (
        "---\n"
        "id: D13\n"
        "title: Cache results\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D13\n"
        "\n"
        "Results are cached.\n"
    )
    write_fixture(repo_root, files)

    _lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-baz", repo_root)

    dependency_context = field(bundle, "dependency_context")
    assert dependency_context["comp-bar"] == "Caches results."

    whole = json.dumps(
        {name: field(bundle, name) for name in BUNDLE_FIELDS},
        default=str,
        ensure_ascii=False,
    )
    assert "D13" not in whole
    assert "Rationale" not in whole
    assert "recomputation is slow" not in whole