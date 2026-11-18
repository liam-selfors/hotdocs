# hotdocs-criterion: sha256:231770795ede962e21587cf46e5308f741a867b0a116046c4a1a124c70ebe92b
import dataclasses
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


RATIONALE_PHRASE = "Bar keeps a memo table because recomputation proved too slow"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, source_path, depends_on, extra_body):
    return (
        "---\n"
        "id: " + comp_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: " + source_path + "\n"
        "depends_on: " + depends_on + "\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        + extra_body
    )


def _build_component(root, slug, comp_md, req_id, req_text, ac_id, gherkin, signature):
    base = root / "specs" / "components" / slug
    _write(base / "component.md", comp_md)
    _write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — " + req_text + "\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + req_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + gherkin
        + "```\n",
    )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\n" + signature + "\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D13.md",
        "---\n"
        "id: D13\n"
        "title: Cache Bar Results\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D13 — Cache Bar Results\n"
        "\n"
        "## Context\n"
        "\n"
        "Recomputing bar values was slow.\n"
        "\n"
        "## Decision\n"
        "\n"
        "Bar caches its results.\n",
    )

    bar_body = (
        "## Purpose\n"
        "\n"
        "Caches results.\n"
        "\n"
        "## Rationale\n"
        "\n"
        + RATIONALE_PHRASE
        + " (`D13`).\n"
    )
    _build_component(
        repo_root,
        "bar",
        _component_md("comp-bar", "Bar", "legacy/bar/", "[]", bar_body),
        "R-BAR-001",
        "`bar(x)` MUST return the cached value for `x`.",
        "AC-BAR-001",
        "Given x = 2 was computed before\n"
        "When bar(x) is called\n"
        "Then it returns the cached value\n",
        "bar(x: int) -> int",
    )

    foo_body = "## Purpose\n\nFoo doubles a number.\n"
    _build_component(
        repo_root,
        "foo",
        _component_md("comp-foo", "Foo", "legacy/foo/", "[comp-bar]", foo_body),
        "R-FOO-001",
        "`foo(x)` MUST return `2 * x`.",
        "AC-FOO-001",
        "Given x = 2\nWhen foo(x) is called\nThen it returns 4\n",
        "foo(x: int) -> int",
    )


def _load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _collect_strings(value, out):
    if value is None:
        return
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            _collect_strings(k, out)
            _collect_strings(v, out)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            _collect_strings(v, out)
    else:
        out.append(str(value))


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
]


def test_dependency_context_holds_only_stripped_purpose(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    dependency_context = field(bundle, "dependency_context")
    assert "comp-bar" in dependency_context
    assert dependency_context["comp-bar"] == "Caches results."

    strings = []
    for name in BUNDLE_FIELDS:
        _collect_strings(field(bundle, name), strings)
    if dataclasses.is_dataclass(bundle):
        for f in dataclasses.fields(bundle):
            _collect_strings(getattr(bundle, f.name), strings)

    for text in strings:
        assert "D13" not in text, "Rationale citation D13 leaked into bundle: " + repr(text)
        assert RATIONALE_PHRASE not in text, "Rationale content leaked into bundle: " + repr(text)
        assert "## Rationale" not in text, "Rationale heading leaked into bundle: " + repr(text)