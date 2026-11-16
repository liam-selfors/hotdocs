"""AC-IMPACT-004 — covers R-IMPACT-004.

Given VAR-CACHE-STORE-URL changed, and comp-cache-manager has
  uses_var: [VAR-CACHE-STORE-URL]
When hotdocs impact --changed VAR-CACHE-STORE-URL runs
Then the report's impacted list contains comp-cache-manager with reason
  "transitive-var" and via "VAR-CACHE-STORE-URL"
"""

import importlib.util
import sys
from pathlib import Path

import pytest

import impact_analyzer


VAR_ID = "VAR-CACHE-STORE-URL"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(specs: Path, slug: str, prefix: str, title: str,
                     purpose: str, uses_var=None) -> None:
    comp_dir = specs / "components" / slug
    fm_lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {title}",
        "status: draft",
        "owners: [alice]",
        "sealed: true",
        f"source_path: legacy/{slug.replace('-', '_')}",
    ]
    if uses_var:
        fm_lines.append("uses_var: [" + ", ".join(uses_var) + "]")
    fm_lines.append("---")
    body = "\n".join(
        [
            "",
            f"# {title}",
            "",
            "## Purpose",
            "",
            purpose,
            "",
            "## Scope",
            "",
            f"- In scope: the {title.lower()} behavior described in `requirements/`.",
            "- Out of scope: everything else.",
            "",
            "## Definitions",
            "",
            "None beyond the glossary.",
            "",
            "## Behavior",
            "",
            "See `requirements/`.",
            "",
            "## Interfaces",
            "",
            "See `interface/`.",
            "",
            "## Data",
            "",
            "None.",
            "",
            "## Acceptance criteria",
            "",
            "See `acceptance/`.",
            "",
            "## Non-functional constraints",
            "",
            "See `constraints.md`.",
            "",
            "## Open questions",
            "",
            "## Change log",
            "",
            "- Initial draft.",
            "",
        ]
    )
    _write(comp_dir / "component.md", "\n".join(fm_lines) + "\n" + body)

    req_id = f"R-{prefix}-001"
    ac_id = f"AC-{prefix}-001"
    _write(
        comp_dir / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\n**{req_id}** — The component MUST return the stored "
        "value for a known key and MUST return nothing for an unknown key.\n",
    )
    _write(
        comp_dir / "acceptance" / f"{ac_id}.md",
        f"# {ac_id}\n\nCovers: {req_id}\nKind: generated-test\n\n"
        "```gherkin\n"
        "Given a key that was stored with a value\n"
        "When the value for that key is requested\n"
        "Then the stored value is returned\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nget(key: str) -> str | None\n```\n\n"
        "Returns the stored value for `key`, or `None` when absent.\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- A lookup MUST complete within 100 ms, measured "
        "by a local benchmark over 1000 lookups.\n",
    )


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n"
        "- **Cache store** — the backing store a cache component reads "
        "and writes.\n",
    )
    _write(
        specs / "vars" / f"{VAR_ID}.md",
        "---\n"
        f"id: {VAR_ID}\n"
        "title: Cache store URL\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        f"# {VAR_ID}\n"
        "\n"
        f"- name: {VAR_ID}\n"
        "- required: required\n"
        "- type: url\n"
        "- description: Base URL of the cache store the cache manager uses.\n"
        "- sensitivity: non-secret\n"
        "- example: https://cache.example.invalid/store\n",
    )
    _write_component(
        specs,
        "cache-manager",
        "CACHE",
        "Cache manager",
        "Stores and retrieves cached values in the cache store located by "
        "its configured URL.",
        uses_var=[VAR_ID],
    )
    _write_component(
        specs,
        "audit-log",
        "AUDIT",
        "Audit log",
        "Records and retrieves audit entries in a local append-only store.",
        uses_var=None,
    )


def _locate_spec_linter():
    """Find spec_linter's real file next to the component under test."""
    try:
        start = Path(impact_analyzer.__file__).resolve()
    except Exception:
        return None
    for parent in start.parents:
        for base in (parent / "gen" / "spec-linter", parent / "spec-linter"):
            flat = base / "spec_linter.py"
            if flat.is_file():
                return flat, False
            pkg = base / "spec_linter" / "__init__.py"
            if pkg.is_file():
                return pkg, True
    return None


def _load_lint():
    found = _locate_spec_linter()
    if found is not None:
        module_path, is_pkg = found
        module_name = "spec_linter"
        if is_pkg:
            spec = importlib.util.spec_from_file_location(
                module_name,
                module_path,
                submodule_search_locations=[str(module_path.parent)],
            )
        else:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)
        return getattr(module, "lint", None)
    try:
        import spec_linter  # type: ignore

        return getattr(spec_linter, "lint", None)
    except Exception:
        return None


def _hard_failures(report):
    count = _get(report, "hard_failures")
    if count is None:
        summary = _get(report, "summary")
        if summary is not None:
            count = _get(summary, "hard_failures")
    if count is None:
        findings = _get(report, "findings") or []
        count = sum(1 for f in findings if _get(f, "severity") == "fail")
    return count


def test_changed_var_includes_uses_var_component_as_transitive_var(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    # Precondition (R-IMPACT-007): the fixture corpus must lint clean.
    lint = _load_lint()
    if lint is not None:
        lint_report = lint(None, repo_root)
        failures = _hard_failures(lint_report)
        findings = _get(lint_report, "findings") or []
        assert failures == 0, (
            "fixture corpus is not lint-clean: "
            + repr(
                [
                    (_get(f, "rule_id"), _get(f, "file"), _get(f, "message"))
                    for f in findings
                    if _get(f, "severity") == "fail"
                ]
            )
        )

    report = impact_analyzer.compute_blast_radius([VAR_ID], repo_root)

    precondition_error = _get(report, "precondition_error")
    assert precondition_error is None, (
        f"unexpected precondition_error: {precondition_error!r}"
    )

    impacted = _get(report, "impacted")
    assert impacted is not None
    impacted = list(impacted)

    matches = [
        entry
        for entry in impacted
        if _get(entry, "component_id") == "comp-cache-manager"
    ]
    assert len(matches) == 1, (
        f"expected comp-cache-manager exactly once in impacted, got {impacted!r}"
    )
    entry = matches[0]
    assert _get(entry, "reason") == "transitive-var"
    assert _get(entry, "via") == VAR_ID

    # Never the bare slug form.
    assert not any(
        _get(e, "component_id") == "cache-manager" for e in impacted
    )

    # A component with no relation to the changed var is not included.
    assert not any(
        _get(e, "component_id") in ("comp-audit-log", "audit-log")
        for e in impacted
    ), f"unrelated component unexpectedly impacted: {impacted!r}"

    # Each component appears at most once.
    ids = [_get(e, "component_id") for e in impacted]
    assert len(ids) == len(set(ids))