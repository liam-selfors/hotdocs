# hotdocs-criterion: sha256:231770795ede962e21587cf46e5308f741a867b0a116046c4a1a124c70ebe92b
import importlib.util
import json
import re
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


RATIONALE_MARKER = "ZQXRationaleMarkerText"


def build_component(repo_root, slug, comp_id, title, req_prefix, purpose, depends_on, extra_body, func):
    comp_dir = repo_root / "specs" / "components" / slug
    write(
        comp_dir / "component.md",
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "depends_on: " + depends_on + "\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose + "\n"
        + extra_body,
    )
    req_id = "R-" + req_prefix + "-001"
    ac_id = "AC-" + req_prefix + "-001"
    write(
        comp_dir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n"
        "\n"
        "**" + req_id + "** — `" + func + "(x)` MUST return `2 * x`.\n",
    )
    write(
        comp_dir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When " + func + "(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        + func + "(x: int) -> int\n"
        "```\n",
    )
    write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    write(
        repo_root / "specs" / "decisions" / "D13.md",
        "---\n"
        "id: D13\n"
        "title: Cache results\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D13: Cache results\n"
        "\n"
        "## Context\n"
        "\n"
        "Results are expensive to compute.\n"
        "\n"
        "## Decision\n"
        "\n"
        "Cache them.\n"
        "\n"
        "## Consequences\n"
        "\n"
        "Results are cached.\n",
    )
    build_component(
        repo_root,
        "bar",
        "comp-bar",
        "Bar",
        "BAR",
        "Caches results.",
        "[]",
        "\n"
        "## Rationale\n"
        "\n"
        "Bar caches results because of `D13`; " + RATIONALE_MARKER + ".\n",
        "bar",
    )
    build_component(
        repo_root,
        "foo",
        "comp-foo",
        "Foo",
        "FOO",
        "Foo doubles a number.",
        "[comp-bar]",
        "",
        "foo",
    )


def bundle_text(bundle):
    names = [
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
    ]
    parts = []
    for name in names:
        try:
            value = field(bundle, name)
        except (KeyError, AttributeError):
            continue
        parts.append(json.dumps(value, default=str, ensure_ascii=False))
    return "\n".join(parts)


def test_dependency_context_is_exactly_purpose_without_rationale(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    dependency_context = field(bundle, "dependency_context")
    assert dependency_context["comp-bar"] == "Caches results."

    text = bundle_text(bundle)
    assert re.search(r"\bD13\b", text) is None
    assert RATIONALE_MARKER not in text
    assert "Bar caches results because of" not in text