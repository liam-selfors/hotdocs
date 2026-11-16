import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import spec_bundle_assembler


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    try:
        return value[name]
    except Exception:
        return getattr(value, name, None)


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

FOO_COMPONENT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: [comp-bar]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

BAR_COMPONENT = (
    "---\n"
    "id: comp-bar\n"
    "title: Bar\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/bar/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Bar\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Caches results.\n"
    "\n"
    "## Rationale\n"
    "\n"
    "Bar keeps a cache because D13 chose memoization over recomputation, a quixotic tradeoff.\n"
)

DECISION_D13 = (
    "---\n"
    "id: D13\n"
    "title: Memoize lookups\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# D13 — Memoize lookups\n"
    "\n"
    "## Decision\n"
    "\n"
    "Lookups are memoized rather than recomputed.\n"
)

FOO_REQ = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

FOO_AC = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

FOO_LIB = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

BAR_REQ = "# R-BAR-001\n\n**R-BAR-001** — `bar(x)` MUST return `x`.\n"

BAR_AC = (
    "# AC-BAR-001\n"
    "\n"
    "Covers: R-BAR-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 3\n"
    "When bar(x) is called\n"
    "Then it returns 3\n"
    "```\n"
)

BAR_LIB = "# Library\n\n```\nbar(x: int) -> int\n```\n"

CONSTRAINTS = "# Constraints\n\nNone.\n"


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(specs / "glossary.md", GLOSSARY)
    _write(specs / "decisions" / "D13.md", DECISION_D13)

    foo = specs / "components" / "foo"
    _write(foo / "component.md", FOO_COMPONENT)
    _write(foo / "requirements" / "R-FOO-001.md", FOO_REQ)
    _write(foo / "acceptance" / "AC-FOO-001.md", FOO_AC)
    _write(foo / "interface" / "library.md", FOO_LIB)
    _write(foo / "constraints.md", CONSTRAINTS)

    bar = specs / "components" / "bar"
    _write(bar / "component.md", BAR_COMPONENT)
    _write(bar / "requirements" / "R-BAR-001.md", BAR_REQ)
    _write(bar / "acceptance" / "AC-BAR-001.md", BAR_AC)
    _write(bar / "interface" / "library.md", BAR_LIB)
    _write(bar / "constraints.md", CONSTRAINTS)


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
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


def _serialize_bundle(bundle) -> str:
    parts = {}
    if dataclasses.is_dataclass(bundle) and not isinstance(bundle, type):
        try:
            parts.update(dataclasses.asdict(bundle))
        except Exception:
            pass
    elif isinstance(bundle, dict):
        parts.update(bundle)
    for name in BUNDLE_FIELDS:
        if name not in parts:
            parts[name] = _field(bundle, name)
    return json.dumps(parts, default=str, ensure_ascii=False)


def test_ac_assemble_010_dependency_context_is_purpose_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = (
        report.get("hard_failures")
        if isinstance(report, dict)
        else getattr(report, "hard_failures", None)
    )
    findings = (
        report.get("findings")
        if isinstance(report, dict)
        else getattr(report, "findings", None)
    )
    assert hard == 0, f"fixture is not lint-clean: {findings!r}"

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    dependency_context = _field(bundle, "dependency_context")
    assert dependency_context is not None, "bundle has no dependency_context"
    assert "comp-bar" in dependency_context, (
        f"dependency_context lacks comp-bar: {dependency_context!r}"
    )
    assert dependency_context["comp-bar"] == "Caches results.", (
        f"dependency_context['comp-bar'] was {dependency_context['comp-bar']!r}"
    )

    serialized = _serialize_bundle(bundle)
    assert "D13" not in serialized, "D13 leaked into the assembled bundle"
    assert "quixotic" not in serialized, (
        "Rationale content leaked into the assembled bundle"
    )
    assert "memoization over recomputation" not in serialized, (
        "Rationale content leaked into the assembled bundle"
    )
    assert "Rationale" not in serialized, (
        "Rationale section leaked into the assembled bundle"
    )