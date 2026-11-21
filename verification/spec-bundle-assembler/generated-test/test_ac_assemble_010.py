# hotdocs-criterion: sha256:46bd6d5a851432daffaad76435dacbe257508d4929dd1bbe9d129c8db7b868b8
import importlib.util
import json
import re
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


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


RATIONALE_PHRASE = "Cached lookups were chosen under D13 for speed."


def component_md(cid, title, slug, depends_on, purpose, extra=""):
    return (
        "---\n"
        "id: " + cid + "\n"
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
        + extra
    )


def write_component(root, slug, cid, title, prefix, func, depends_on, purpose, extra=""):
    base = "specs/components/" + slug + "/"
    write(root, base + "component.md", component_md(cid, title, slug, depends_on, purpose, extra))
    rid = "R-" + prefix + "-001"
    aid = "AC-" + prefix + "-001"
    write(
        root,
        base + "requirements/" + rid + ".md",
        "# " + rid + "\n\n**" + rid + "** — `" + func + "(x)` MUST return `2 * x`.\n",
    )
    write(
        root,
        base + "acceptance/" + aid + ".md",
        "# " + aid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When " + func + "(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        root,
        base + "interface/library.md",
        "# Library\n\n```\n" + func + "(x: int) -> int\n```\n",
    )
    write(root, base + "constraints.md", "# Constraints\n\nNone.\n")


def build_fixture(root):
    write(root, "specs/glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    write(
        root,
        "specs/decisions/D13.md",
        "---\n"
        "id: D13\n"
        "title: Cache lookups\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D13 — Cache lookups\n"
        "\n"
        "## Decision\n"
        "\n"
        "Bar caches lookups.\n",
    )
    write_component(
        root, "bar", "comp-bar", "Bar", "BAR", "bar", "[]",
        "Caches results.",
        "\n## Rationale\n\n" + RATIONALE_PHRASE + "\n",
    )
    write_component(
        root, "foo", "comp-foo", "Foo", "FOO", "foo", "[comp-bar]",
        "Foo doubles a number.",
    )


def test_ac_assemble_010_dependency_context_is_purpose_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    dependency_context = field(bundle, "dependency_context")
    assert dependency_context["comp-bar"] == "Caches results."

    names = [
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    ]
    d13 = re.compile(r"\bD13\b")
    for name in names:
        value = field(bundle, name)
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        assert not d13.search(text), "D13 found in bundle field " + repr(name)
        assert "Rationale" not in text, "Rationale content found in bundle field " + repr(name)
        assert RATIONALE_PHRASE not in text, "Rationale text found in bundle field " + repr(name)
        assert "speed" not in text, "Rationale text found in bundle field " + repr(name)