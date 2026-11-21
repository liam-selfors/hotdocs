# hotdocs-criterion: sha256:fe64d3f2d56d27bb52571cbd746af789abd9736cec5b33de6eed57c89d05c6f0
import importlib.util
import sys
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


PRODUCT = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo works\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Foo works\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A foo can be made.\n"
    "\n"
    "### CS-FOO-001\n"
    "Covers: P-FOO\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When a foo is made\n"
    "Then it exists\n"
    "```\n"
)


def _component_md(comp_id, title, extra_frontmatter):
    return (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        + extra_frontmatter +
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes a " + title.lower() + ".\n"
        "\n"
        "## Scope\n"
        "\n"
        "**In scope:** making a thing. **Out of scope:** everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "No deltas from `specs/glossary.md`.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "None.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "None.\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def _write_component(root, slug, comp_id, title, prefix, func, extra_frontmatter):
    base = "specs/components/" + slug + "/"
    _write(root, base + "component.md", _component_md(comp_id, title, extra_frontmatter))
    rid = "R-" + prefix + "-001"
    acid = "AC-" + prefix + "-001"
    _write(
        root,
        base + "requirements/" + rid + ".md",
        "# " + rid + "\n\n**" + rid + "** — `" + func + "()` MUST return the string `\"" + slug + "\"`.\n",
    )
    _write(
        root,
        base + "interface/library.md",
        "# Library\n\nOne module file.\n\n```\n" + func + "() -> str\n```\n",
    )
    _write(
        root,
        base + "acceptance/" + acid + ".md",
        "# " + acid + "\n\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When " + func + "() is called\n"
        "Then the result is \"" + slug + "\"\n"
        "```\n",
    )
    _write(
        root,
        base + "constraints.md",
        "# " + title + " — Non-Functional Constraints\n\n- **Pure.** No I/O.\n",
    )


def _build_corpus(root):
    _write(root, "specs/product/foo.md", PRODUCT)
    _write_component(
        root, "foo", "comp-foo", "Foo", "FOO", "make_foo",
        "depends_on: []\nrealizes: [P-FOO]\nsealed: false\n",
    )
    _write_component(
        root, "a", "comp-a", "Alpha", "A", "make_a",
        "depends_on: [comp-does-not-exist-a]\nsealed: true\nsource_path: legacy/a/\n",
    )
    _write_component(
        root, "b", "comp-b", "Beta", "B", "make_b",
        "depends_on: [comp-does-not-exist-b]\nsealed: true\nsource_path: legacy/b/\n",
    )


def _norm(f):
    return str(f).replace("\\", "/")


def test_ac_lint_035_paths_limit_findings(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    monkeypatch.chdir(repo_root)

    # Directory path: findings limited to specs/components/a/
    report_a = spec_linter.lint([Path("specs/components/a")], repo_root)
    findings_a = list(field(report_a, "findings"))
    assert findings_a, "expected at least the R-LINT-003 finding for component a"
    for f in findings_a:
        file = _norm(field(f, "file"))
        assert file.startswith("specs/components/a/"), (
            "finding outside specs/components/a/: " + repr(file) + " " + repr(field(f, "rule_id"))
        )
    assert any(
        field(f, "rule_id") == "R-LINT-003"
        and _norm(field(f, "file")) == "specs/components/a/component.md"
        for f in findings_a
    ), "no R-LINT-003 finding for specs/components/a/component.md: " + repr(
        [(field(f, "rule_id"), field(f, "file")) for f in findings_a]
    )

    # File path: findings limited to exactly specs/components/b/component.md
    report_b = spec_linter.lint([Path("specs/components/b/component.md")], repo_root)
    findings_b = list(field(report_b, "findings"))
    assert findings_b, "expected at least the R-LINT-003 finding for component b"
    for f in findings_b:
        file = _norm(field(f, "file"))
        assert file == "specs/components/b/component.md", (
            "finding outside specs/components/b/component.md: " + repr(file) + " " + repr(field(f, "rule_id"))
        )
    assert any(field(f, "rule_id") == "R-LINT-003" for f in findings_b), (
        "no R-LINT-003 finding: " + repr([(field(f, "rule_id"), field(f, "file")) for f in findings_b])
    )