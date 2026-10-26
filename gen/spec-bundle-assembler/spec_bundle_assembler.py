"""spec-bundle-assembler — bootstrap implementation.

HAND-AUTHORED BOOTSTRAP (sixth instance, temporary exception like
cache-manager -- see verification/spec-bundle-assembler/BOOTSTRAP.md).

Implements R-ASSEMBLE-001..010: assembles a component's SpecBundle (or
a narrower CriterionBundle for test-author) from the real corpus,
reusing spec-linter's own load_corpus() rather than re-parsing files
independently (single source of truth, SPEC_GUIDELINES.md §10) and
graph-query-engine's component_context view for R-ASSEMBLE-010's one
narrow dependency-Purpose exception.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spec-linter"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "graph-query-engine"))
import spec_linter  # noqa: E402
import graph_query_engine  # noqa: E402

_COVERS_RE = re.compile(r"^Covers:\s*(\S+)", re.MULTILINE)


class PreconditionFailureError(Exception):
    """R-ASSEMBLE-005 -- the corpus does not pass spec-linter cleanly at
    hard-fail severity. Assembly refuses to produce a bundle at all,
    rather than a partial one."""


@dataclass
class SpecBundle:
    """Matches `interface/data/SpecBundle.md` exactly."""

    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict[str, str]
    dependency_context: dict[str, str]
    vars: dict[str, str]
    glossary: str
    hint_code: dict[str, str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "spec_bundle_hash": self.spec_bundle_hash,
            "spec": self.spec,
            "interface": self.interface,
            "constraints": self.constraints,
            "dependency_interfaces": self.dependency_interfaces,
            "dependency_context": self.dependency_context,
            "vars": self.vars,
            "glossary": self.glossary,
            "hint_code": self.hint_code,
        }


@dataclass
class CriterionBundle:
    """Matches `interface/data/CriterionBundle.md` exactly."""

    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "criterion_id": self.criterion_id,
            "covers": self.covers,
            "criterion_text": self.criterion_text,
            "requirement_text": self.requirement_text,
            "interface": self.interface,
            "glossary": self.glossary,
        }


def _check_lint_clean(repo_root: Path) -> None:
    """R-ASSEMBLE-005, mirroring impact-analyzer's R-IMPACT-007."""
    report = spec_linter.lint(None, repo_root)
    if report.hard_failures:
        raise PreconditionFailureError(
            f"corpus has {report.hard_failures} hard-fail spec-linter "
            f"finding(s); assembly refused (R-ASSEMBLE-005)"
        )


def _component_spec_text(comp: "spec_linter.Component") -> str:
    """R-ASSEMBLE-001's `spec` field: component.md body + requirements/."""
    parts = [comp.root.body if comp.root else ""]
    for rid in sorted(comp.requirements):
        parts.append(f"### {rid}\n\n{comp.requirements[rid].body}")
    return "\n\n".join(parts)


def _component_interface_text(comp: "spec_linter.Component") -> str:
    """R-ASSEMBLE-002's `interface/` content -- cli.md, library.md,
    interface/data/*.md, interface/guarantees/*.md. Never component.md,
    requirements/, or constraints.md (that boundary is what makes this
    function reusable for both the target's own interface, R-ASSEMBLE-001,
    and each dependency's, R-ASSEMBLE-002 -- a dependent only ever gets
    what this function returns, nothing more)."""
    parts = []
    if comp.interface_cli:
        parts.append(f"### interface/cli.md\n\n{comp.interface_cli.body}")
    if comp.interface_library:
        parts.append(f"### interface/library.md\n\n{comp.interface_library.body}")
    for name in sorted(comp.interface_data):
        parts.append(f"### interface/data/{name}.md\n\n{comp.interface_data[name].body}")
    for gid in sorted(comp.interface_guarantees):
        parts.append(f"### interface/guarantees/{gid}.md\n\n{comp.interface_guarantees[gid].body}")
    return "\n\n".join(parts)


def _find_component_by_id(corpus: "spec_linter.Corpus", comp_id: str) -> "spec_linter.Component | None":
    for comp in corpus.components.values():
        if comp.root and comp.root.doc_id == comp_id:
            return comp
    return None


def _dependency_context(con: duckdb.DuckDBPyConnection, comp_id: str) -> str:
    """R-ASSEMBLE-010 -- read via the shared component_context view
    (graph-query-engine), never directly from the dependency's
    component.md by this component's own logic."""
    row = con.execute(
        "SELECT purpose FROM component_context WHERE component_id = ?", [comp_id]
    ).fetchone()
    return row[0] if row else ""


def _read_hint_code(repo_root: Path, bare_name: str) -> dict[str, str]:
    """R-ASSEMBLE-008 -- the component's current gen/<component>/ content,
    keyed by path relative to that directory."""
    gen_dir = repo_root / "gen" / bare_name
    if not gen_dir.is_dir():
        return {}
    result = {}
    for path in sorted(gen_dir.rglob("*")):
        if path.is_file():
            try:
                result[str(path.relative_to(gen_dir))] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue  # binary artifact (e.g. __pycache__) -- not spec-relevant content
    return result


def _compute_hash(bundle_without_hash: dict[str, Any]) -> str:
    """R-ASSEMBLE-006/007 -- a content hash of the assembled bundle,
    deterministic (sorted keys, fixed separators) so the same corpus
    bytes always produce the same hash."""
    serialized = json.dumps(bundle_without_hash, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def assemble(component_id: str, repo_root: Path, mode: str = "cold") -> SpecBundle:
    """R-ASSEMBLE-001..008. `component_id` is the comp-id (e.g.
    "comp-foo"), matching interface/cli.md's own usage."""
    repo_root = Path(repo_root)
    _check_lint_clean(repo_root)

    corpus = spec_linter.load_corpus(repo_root)
    comp = _find_component_by_id(corpus, component_id)
    if comp is None or comp.root is None:
        raise ValueError(f"no component with id {component_id!r} found under {repo_root}")

    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    graph_query_engine.load_views(con, repo_root)

    dep_ids = comp.root.frontmatter.get("depends_on") or []
    dependency_interfaces: dict[str, str] = {}
    dependency_context: dict[str, str] = {}
    for dep_id in dep_ids:
        dep_comp = _find_component_by_id(corpus, dep_id)
        if dep_comp is not None:
            dependency_interfaces[dep_id] = _component_interface_text(dep_comp)
        dependency_context[dep_id] = _dependency_context(con, dep_id)

    var_ids = comp.root.frontmatter.get("uses_var") or []
    variables: dict[str, str] = {}
    for var_id in var_ids:
        var_doc = corpus.id_index.get(var_id)
        if var_doc is not None:
            variables[var_id] = var_doc.body

    glossary = (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8")

    bundle_fields = {
        "component_id": component_id,
        "spec": _component_spec_text(comp),
        "interface": _component_interface_text(comp),
        "constraints": comp.constraints.body if comp.constraints else "",
        "dependency_interfaces": dependency_interfaces,
        "dependency_context": dependency_context,
        "vars": variables,
        "glossary": glossary,
        "hint_code": None,
    }

    if mode == "hint":
        bundle_fields["hint_code"] = _read_hint_code(repo_root, comp.name)

    spec_bundle_hash = _compute_hash({k: v for k, v in bundle_fields.items() if k != "hint_code"})

    return SpecBundle(spec_bundle_hash=spec_bundle_hash, **bundle_fields)


def assemble_criterion(component_id: str, criterion_id: str, repo_root: Path) -> CriterionBundle:
    """R-ASSEMBLE-009 -- narrower than SpecBundle by construction, not a
    variant of it: test-author's independence (R-AUTHOR-002) depends on
    seeing less than generator sees, not the same bundle plus something."""
    repo_root = Path(repo_root)
    _check_lint_clean(repo_root)

    corpus = spec_linter.load_corpus(repo_root)
    comp = _find_component_by_id(corpus, component_id)
    if comp is None:
        raise ValueError(f"no component with id {component_id!r} found under {repo_root}")

    criterion_doc = comp.acceptance.get(criterion_id)
    if criterion_doc is None:
        raise ValueError(f"no criterion {criterion_id!r} found for {component_id!r}")

    covers_match = _COVERS_RE.search(criterion_doc.body)
    covers = covers_match.group(1) if covers_match else ""
    requirement_doc = comp.requirements.get(covers)
    requirement_text = requirement_doc.body if requirement_doc else ""

    glossary = (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8")

    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=criterion_doc.body,
        requirement_text=requirement_text,
        interface=_component_interface_text(comp),
        glossary=glossary,
    )
