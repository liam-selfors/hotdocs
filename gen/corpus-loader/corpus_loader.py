"""Loads a spec corpus under repo_root/specs/ into one in-memory Corpus."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb

_BULLET_RE = re.compile(r'^- \*\*(?P<term>.+?)\*\*\s*(?P<rest>.*)$')

_DEP_SLUG = "graph-query-engine"
_DEP_MODULE_NAME = "graph_query_engine"


@dataclass
class Doc:
    path: Path
    rel_path: str
    doc_id: Optional[str]
    frontmatter: Dict[str, Any]
    body: str
    doc_type: str
    component: Optional[str] = None
    has_frontmatter: bool = False


@dataclass
class Component:
    name: str
    root: Optional[Doc]
    requirements: Dict[str, Doc]
    interface_cli: Optional[Doc]
    interface_library: Optional[Doc]
    interface_data: Dict[str, Doc]
    interface_guarantees: Dict[str, Doc]
    acceptance: Dict[str, Doc]
    constraints: Optional[Doc]


@dataclass
class Corpus:
    repo_root: Path
    docs: List[Doc]
    components: Dict[str, Component]
    id_index: Dict[str, Doc]
    glossary_defs: Dict[str, str]
    glossary_files: List[Path]
    graph: "duckdb.DuckDBPyConnection"


def _parse_frontmatter(text: str) -> tuple[Dict[str, Any], str, bool]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text, False

    frontmatter: Dict[str, Any] = {}
    for raw_line in lines[1:end_idx]:
        if not raw_line.strip() or ":" not in raw_line:
            continue
        key, _, value = raw_line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            frontmatter[key] = [v.strip() for v in inner.split(",")] if inner else []
        elif value.lower() == "true":
            frontmatter[key] = True
        elif value.lower() == "false":
            frontmatter[key] = False
        else:
            v = value
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                v = v[1:-1]
            frontmatter[key] = v

    body = "\n".join(lines[end_idx + 1:])
    return frontmatter, body, True


def _classify(specs_rel_parts: tuple[str, ...]) -> tuple[Optional[str], Optional[str]]:
    if not specs_rel_parts:
        return None, None

    if specs_rel_parts[0] == "components":
        if len(specs_rel_parts) < 3:
            return None, None
        comp_name = specs_rel_parts[1]
        rest = specs_rel_parts[2:]

        if rest == ("component.md",):
            return "component-root", comp_name
        if len(rest) == 2 and rest[0] == "requirements" and rest[1].startswith("R-") and rest[1].endswith(".md"):
            return "component-requirement", comp_name
        if len(rest) == 2 and rest[0] == "interface" and rest[1] == "cli.md":
            return "component-interface-cli", comp_name
        if len(rest) == 2 and rest[0] == "interface" and rest[1] == "library.md":
            return "component-interface-library", comp_name
        if len(rest) == 3 and rest[0] == "interface" and rest[1] == "data" and rest[2].endswith(".md"):
            return "component-interface-data", comp_name
        if (
            len(rest) == 3
            and rest[0] == "interface"
            and rest[1] == "guarantees"
            and rest[2].startswith("G-")
            and rest[2].endswith(".md")
        ):
            return "component-interface-guarantee", comp_name
        if len(rest) == 2 and rest[0] == "acceptance" and rest[1].startswith("AC-") and rest[1].endswith(".md"):
            return "component-acceptance", comp_name
        if rest == ("constraints.md",):
            return "component-constraints", comp_name
        return None, None

    type_map = {"product": "product", "architecture": "architecture", "vars": "var", "decisions": "decision"}
    if specs_rel_parts[0] in type_map and len(specs_rel_parts) == 2 and specs_rel_parts[1].endswith(".md"):
        return type_map[specs_rel_parts[0]], None

    return None, None


def _parse_glossary_text(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    starts: List[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        m = _BULLET_RE.match(line)
        if m:
            starts.append((i, m.group("term"), m.group("rest")))

    defs: Dict[str, str] = {}
    for idx, (line_no, term, rest) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        rest_clean = rest.lstrip(" \t\u2014-")
        body_lines = [rest_clean] + lines[line_no + 1:end]
        entry_text = "\n".join(body_lines).strip()
        defs[term.lower()] = entry_text
    return defs


def _find_tool_root(module_file: Path) -> Path:
    for parent in module_file.parents:
        if parent.name == "gen":
            return parent.parent
    raise FileNotFoundError("could not locate a 'gen' directory above corpus_loader's own file")


def _dependency_dir(repo_root: Path, dep_slug: str) -> Path:
    repo_candidate = Path(repo_root) / "gen" / dep_slug
    if repo_candidate.is_dir():
        return repo_candidate
    tool_root = _find_tool_root(Path(__file__).resolve())
    return tool_root / "gen" / dep_slug


def _load_dependency_module(repo_root: Path, dep_slug: str, module_name: str):
    dep_dir = _dependency_dir(repo_root, dep_slug)
    flat = dep_dir / f"{module_name}.py"
    pkg_init = dep_dir / module_name / "__init__.py"

    if flat.is_file():
        module_path = flat
    elif pkg_init.is_file():
        module_path = pkg_init
    else:
        raise FileNotFoundError(f"cannot find module '{module_name}' under {dep_dir}")

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _build_graph(repo_root: Path) -> "duckdb.DuckDBPyConnection":
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    gqe_module = _load_dependency_module(repo_root, _DEP_SLUG, _DEP_MODULE_NAME)
    load_views = gqe_module.load_views if hasattr(gqe_module, "load_views") else gqe_module["load_views"]
    load_views(con, repo_root)
    return con


def load_corpus(repo_root: Path) -> Corpus:
    repo_root = Path(repo_root).resolve()
    specs_dir = repo_root / "specs"

    docs: List[Doc] = []
    components: Dict[str, Component] = {}
    id_index: Dict[str, Doc] = {}

    md_files = sorted(specs_dir.rglob("*.md"), key=lambda p: str(p)) if specs_dir.is_dir() else []

    for path in md_files:
        specs_rel_parts = path.relative_to(specs_dir).parts
        doc_type, comp_name = _classify(specs_rel_parts)
        if doc_type is None:
            continue

        text = path.read_text(encoding="utf-8")
        frontmatter, body, has_fm = _parse_frontmatter(text)

        if doc_type in ("component-requirement", "component-acceptance", "component-interface-guarantee"):
            doc_id = path.stem
        else:
            doc_id = frontmatter.get("id")

        rel_path = path.relative_to(repo_root).as_posix()

        doc = Doc(
            path=path,
            rel_path=rel_path,
            doc_id=doc_id,
            frontmatter=frontmatter,
            body=body,
            doc_type=doc_type,
            component=comp_name,
            has_frontmatter=has_fm,
        )
        docs.append(doc)

        if comp_name is not None:
            if comp_name not in components:
                components[comp_name] = Component(
                    name=comp_name,
                    root=None,
                    requirements={},
                    interface_cli=None,
                    interface_library=None,
                    interface_data={},
                    interface_guarantees={},
                    acceptance={},
                    constraints=None,
                )
            component = components[comp_name]

            if doc_type == "component-root":
                component.root = doc
            elif doc_type == "component-requirement":
                component.requirements[doc.doc_id] = doc
            elif doc_type == "component-interface-cli":
                component.interface_cli = doc
            elif doc_type == "component-interface-library":
                component.interface_library = doc
            elif doc_type == "component-interface-data":
                component.interface_data[path.stem] = doc
            elif doc_type == "component-interface-guarantee":
                component.interface_guarantees[doc.doc_id] = doc
            elif doc_type == "component-acceptance":
                component.acceptance[doc.doc_id] = doc
            elif doc_type == "component-constraints":
                component.constraints = doc

        if doc_type in ("component-root", "product", "architecture", "var", "decision") and doc.doc_id:
            id_index[doc.doc_id] = doc

    glossary_files = sorted(specs_dir.glob("glossary*.md"), key=lambda p: str(p)) if specs_dir.is_dir() else []
    glossary_defs: Dict[str, str] = {}
    for gfile in glossary_files:
        glossary_defs.update(_parse_glossary_text(gfile.read_text(encoding="utf-8")))

    graph = _build_graph(repo_root)

    return Corpus(
        repo_root=repo_root,
        docs=docs,
        components=components,
        id_index=id_index,
        glossary_defs=glossary_defs,
        glossary_files=glossary_files,
        graph=graph,
    )