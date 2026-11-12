"""Corpus loader: reads a spec corpus under ``repo_root/specs/`` into one
in-memory ``Corpus`` model (classified docs, parsed frontmatter, assembled
components, glossary, and the shared graph views)."""
from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb


@dataclass
class Doc:
    path: Path
    rel_path: str
    doc_id: Any
    frontmatter: dict
    body: str
    doc_type: str
    component: Any = None
    has_frontmatter: bool = False


@dataclass
class Component:
    name: str
    root: Any
    requirements: dict
    interface_cli: Any
    interface_library: Any
    interface_data: dict
    interface_guarantees: dict
    acceptance: dict
    constraints: Any


@dataclass
class Corpus:
    repo_root: Path
    docs: list
    components: dict
    id_index: dict
    glossary_defs: dict
    glossary_files: list
    graph: Any


_TOP_LEVEL_TYPES = {
    "product": "product",
    "architecture": "architecture",
    "vars": "var",
    "decisions": "decision",
}

_STEM_ID_TYPES = {
    "component-requirement",
    "component-acceptance",
    "component-interface-guarantee",
}

_INDEXED_TYPES = {"component-root", "product", "architecture", "var", "decision"}

_GLOSSARY_ENTRY_RE = re.compile(r"^- \*\*(.+?)\*\*(.*)$")

_DEP_SLUG = "graph-query-engine"
_DEP_MODULE = "graph_query_engine"


def _classify(parts):
    """Return (doc_type, component_name) for a path's parts relative to
    ``specs/``, or None when the path is not a listed doc."""
    name = parts[-1]
    if name == "README.md":
        return None
    if len(parts) == 2 and parts[0] in _TOP_LEVEL_TYPES:
        return _TOP_LEVEL_TYPES[parts[0]], None
    if len(parts) < 3 or parts[0] != "components":
        return None
    comp = parts[1]
    rest = parts[2:]
    if rest == ("component.md",):
        return "component-root", comp
    if rest == ("constraints.md",):
        return "component-constraints", comp
    if len(rest) == 2 and rest[0] == "requirements" and name.startswith("R-"):
        return "component-requirement", comp
    if len(rest) == 2 and rest[0] == "acceptance" and name.startswith("AC-"):
        return "component-acceptance", comp
    if rest == ("interface", "cli.md"):
        return "component-interface-cli", comp
    if rest == ("interface", "library.md"):
        return "component-interface-library", comp
    if len(rest) == 3 and rest[:2] == ("interface", "data"):
        return "component-interface-data", comp
    if len(rest) == 3 and rest[:2] == ("interface", "guarantees") and name.startswith("G-"):
        return "component-interface-guarantee", comp
    return None


def _parse_value(raw):
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [item.strip() for item in value[1:-1].split(",") if item.strip()]
    if value == "true":
        return True
    if value == "false":
        return False
    return value.strip("\"'")


def _split_frontmatter(text):
    """Return (frontmatter, body, has_frontmatter)."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                frontmatter = {}
                for line in lines[1:end]:
                    if ":" in line:
                        key, _, value = line.partition(":")
                        frontmatter[key.strip()] = _parse_value(value)
                return frontmatter, "\n".join(lines[end + 1:]), True
    return {}, text, False


def _new_component(name):
    return Component(name, None, {}, None, None, {}, {}, {}, None)


def _attach(component, doc):
    doc_type = doc.doc_type
    if doc_type == "component-root":
        component.root = doc
    elif doc_type == "component-requirement":
        component.requirements[doc.doc_id] = doc
    elif doc_type == "component-interface-cli":
        component.interface_cli = doc
    elif doc_type == "component-interface-library":
        component.interface_library = doc
    elif doc_type == "component-interface-data":
        component.interface_data[doc.path.stem] = doc
    elif doc_type == "component-interface-guarantee":
        component.interface_guarantees[doc.doc_id] = doc
    elif doc_type == "component-acceptance":
        component.acceptance[doc.doc_id] = doc
    else:
        component.constraints = doc


def _glossary_defs(files):
    entries = {}
    for path in files:
        entry = None
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _GLOSSARY_ENTRY_RE.match(line)
            if match:
                entry = [match.group(2).lstrip("—- \t")]
                entries[match.group(1).lower()] = entry
            elif entry is not None and (not line.strip() or line[:1].isspace()):
                entry.append(line)
            else:
                entry = None
    return {term: "\n".join(lines).strip() for term, lines in entries.items()}


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load_graph_query_engine(repo_root):
    dep_dir = repo_root / "gen" / _DEP_SLUG
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / _DEP_SLUG
    digest = hashlib.sha1(str(dep_dir).encode("utf-8")).hexdigest()[:16]
    name = f"_corpus_loader_dep_{_DEP_MODULE}_{digest}"
    flat = dep_dir / f"{_DEP_MODULE}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(name, flat)
    else:
        init = dep_dir / _DEP_MODULE / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            name, init, submodule_search_locations=[str(init.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_graph(repo_root):
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    _load_graph_query_engine(repo_root).load_views(con, repo_root)
    return con


def load_corpus(repo_root: Path) -> Corpus:
    repo_root = Path(repo_root).absolute()
    specs = repo_root / "specs"
    docs = []
    components = {}
    id_index = {}
    for path in sorted(specs.rglob("*.md")):
        classified = _classify(path.relative_to(specs).parts)
        if classified is None:
            continue
        doc_type, comp_name = classified
        frontmatter, body, has_frontmatter = _split_frontmatter(
            path.read_text(encoding="utf-8")
        )
        doc_id = path.stem if doc_type in _STEM_ID_TYPES else frontmatter.get("id")
        doc = Doc(
            path,
            path.relative_to(repo_root).as_posix(),
            doc_id,
            frontmatter,
            body,
            doc_type,
            comp_name,
            has_frontmatter,
        )
        docs.append(doc)
        if doc_type in _INDEXED_TYPES:
            id_index[doc_id] = doc
        if comp_name is not None:
            if comp_name not in components:
                components[comp_name] = _new_component(comp_name)
            _attach(components[comp_name], doc)
    glossary_files = sorted(specs.glob("glossary*.md"))
    return Corpus(
        repo_root,
        docs,
        components,
        id_index,
        _glossary_defs(glossary_files),
        glossary_files,
        _load_graph(repo_root),
    )