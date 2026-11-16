"""Corpus Loader: reads a spec corpus into one in-memory model.

`load_corpus(repo_root)` classifies every spec file under
`repo_root/specs/`, parses its frontmatter, assembles components from
their files, parses the glossary, and opens a DuckDB connection with
`graph-query-engine`'s shared views loaded.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import duckdb


@dataclass
class Doc:
    path: Path
    rel_path: str
    doc_id: Optional[str]
    frontmatter: dict
    body: str
    doc_type: str
    component: Optional[str] = None
    has_frontmatter: bool = False


@dataclass
class Component:
    name: str
    root: Optional[Doc] = None
    requirements: dict = field(default_factory=dict)
    interface_cli: Optional[Doc] = None
    interface_library: Optional[Doc] = None
    interface_data: dict = field(default_factory=dict)
    interface_guarantees: dict = field(default_factory=dict)
    acceptance: dict = field(default_factory=dict)
    constraints: Optional[Doc] = None


@dataclass
class Corpus:
    repo_root: Path
    docs: list
    components: dict
    id_index: dict
    glossary_defs: dict
    glossary_files: list
    graph: Any


_FLAT_DIR_TYPES = {
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

_GLOSSARY_ENTRY = re.compile(r"^-\s+\*\*(.+?)\*\*(.*)$")
_LEADING_DASHES = re.compile(r"^[\s\u2014-]+")


def _classify(parts: tuple) -> tuple:
    """Return (doc_type, component_name) for a path's parts under specs/,
    or (None, None) when the path is unlisted."""
    if parts[-1] == "README.md":
        return None, None
    if len(parts) == 2 and parts[0] in _FLAT_DIR_TYPES:
        return _FLAT_DIR_TYPES[parts[0]], None
    if len(parts) >= 3 and parts[0] == "components":
        comp = parts[1]
        sub = parts[2:]
        name = sub[-1]
        if sub == ("component.md",):
            return "component-root", comp
        if sub == ("constraints.md",):
            return "component-constraints", comp
        if len(sub) == 2 and sub[0] == "requirements" and name.startswith("R-"):
            return "component-requirement", comp
        if sub == ("interface", "cli.md"):
            return "component-interface-cli", comp
        if sub == ("interface", "library.md"):
            return "component-interface-library", comp
        if len(sub) == 3 and sub[:2] == ("interface", "data"):
            return "component-interface-data", comp
        if (
            len(sub) == 3
            and sub[:2] == ("interface", "guarantees")
            and name.startswith("G-")
        ):
            return "component-interface-guarantee", comp
        if len(sub) == 2 and sub[0] == "acceptance" and name.startswith("AC-"):
            return "component-acceptance", comp
    return None, None


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [item.strip() for item in value[1:-1].split(",") if item.strip()]
    if value == "true":
        return True
    if value == "false":
        return False
    return value.strip("\"'")


def _parse_text(text: str) -> tuple:
    """Return (frontmatter, body, has_frontmatter) for a file's text."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for end in range(1, len(lines)):
            if lines[end].strip() == "---":
                frontmatter = {}
                for line in lines[1:end]:
                    if ":" in line:
                        key, _, raw = line.partition(":")
                        frontmatter[key.strip()] = _parse_value(raw)
                return frontmatter, "\n".join(lines[end + 1:]), True
    return {}, text, False


def _parse_glossary(text: str, defs: dict) -> None:
    term = None
    chunk: list = []

    def flush() -> None:
        if term is not None:
            joined = "\n".join(chunk)
            defs[term] = _LEADING_DASHES.sub("", joined).strip()

    for line in text.splitlines():
        match = _GLOSSARY_ENTRY.match(line)
        if match:
            flush()
            term = match.group(1).lower()
            chunk = [match.group(2)]
        elif term is not None:
            chunk.append(line)
    flush()


def _tool_root() -> Optional[Path]:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_graph_query_engine(repo_root: Path):
    module_name = "graph_query_engine"
    dep_dir = repo_root / "gen" / "graph-query-engine"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "graph-query-engine"
    flat = dep_dir / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg_dir = dep_dir / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _open_graph(repo_root: Path):
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    engine = _load_graph_query_engine(repo_root)
    load_views = (
        engine["load_views"] if isinstance(engine, dict) else getattr(engine, "load_views")
    )
    load_views(con, repo_root)
    return con


def load_corpus(repo_root: Path) -> Corpus:
    repo_root = Path(repo_root).absolute()
    specs_dir = repo_root / "specs"

    docs: list = []
    components: dict = {}
    id_index: dict = {}

    for path in sorted(specs_dir.rglob("*.md")):
        parts = path.relative_to(specs_dir).parts
        doc_type, comp_name = _classify(parts)
        if doc_type is None:
            continue
        text = path.read_text(encoding="utf-8")
        frontmatter, body, has_frontmatter = _parse_text(text)
        if doc_type in _STEM_ID_TYPES:
            doc_id = path.stem
        else:
            doc_id = frontmatter.get("id")
        doc = Doc(
            path=path,
            rel_path=path.relative_to(repo_root).as_posix(),
            doc_id=doc_id,
            frontmatter=frontmatter,
            body=body,
            doc_type=doc_type,
            component=comp_name,
            has_frontmatter=has_frontmatter,
        )
        docs.append(doc)

        if doc_type in _INDEXED_TYPES:
            id_index[doc_id] = doc

        if comp_name is not None:
            comp = components.setdefault(comp_name, Component(name=comp_name))
            if doc_type == "component-root":
                comp.root = doc
            elif doc_type == "component-constraints":
                comp.constraints = doc
            elif doc_type == "component-requirement":
                comp.requirements[doc_id] = doc
            elif doc_type == "component-interface-cli":
                comp.interface_cli = doc
            elif doc_type == "component-interface-library":
                comp.interface_library = doc
            elif doc_type == "component-interface-data":
                comp.interface_data[path.stem] = doc
            elif doc_type == "component-interface-guarantee":
                comp.interface_guarantees[doc_id] = doc
            else:
                comp.acceptance[doc_id] = doc

    glossary_files = sorted(specs_dir.glob("glossary*.md"))
    glossary_defs: dict = {}
    for gpath in glossary_files:
        _parse_glossary(gpath.read_text(encoding="utf-8"), glossary_defs)

    return Corpus(
        repo_root=repo_root,
        docs=docs,
        components=components,
        id_index=id_index,
        glossary_defs=glossary_defs,
        glossary_files=glossary_files,
        graph=_open_graph(repo_root),
    )