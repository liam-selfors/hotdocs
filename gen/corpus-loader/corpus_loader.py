"""Corpus Loader: reads a spec corpus into one in-memory model."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import duckdb

__all__ = ["Doc", "Component", "Corpus", "load_corpus"]


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
    root: Optional[Doc]
    requirements: dict
    interface_cli: Optional[Doc]
    interface_library: Optional[Doc]
    interface_data: dict
    interface_guarantees: dict
    acceptance: dict
    constraints: Optional[Doc]


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

_ID_INDEX_TYPES = {
    "component-root",
    "product",
    "architecture",
    "var",
    "decision",
}

_ENTRY_RE = re.compile(r"^- \*\*(.+?)\*\*(.*)$")
_LEADING_RE = re.compile(r"^[\s\u2014-]+")


def _classify(parts: tuple) -> tuple:
    """Return (doc_type, component) for a path relative to specs/, or (None, None)."""
    name = parts[-1]
    if len(parts) == 2 and parts[0] in _TOP_LEVEL_TYPES:
        return _TOP_LEVEL_TYPES[parts[0]], None
    if parts[0] != "components" or len(parts) < 3:
        return None, None
    comp = parts[1]
    sub = parts[2:]
    doc_type = None
    if len(sub) == 1:
        if name == "component.md":
            doc_type = "component-root"
        elif name == "constraints.md":
            doc_type = "component-constraints"
    elif len(sub) == 2:
        if sub[0] == "requirements" and name.startswith("R-"):
            doc_type = "component-requirement"
        elif sub[0] == "acceptance" and name.startswith("AC-"):
            doc_type = "component-acceptance"
        elif sub[0] == "interface" and name == "cli.md":
            doc_type = "component-interface-cli"
        elif sub[0] == "interface" and name == "library.md":
            doc_type = "component-interface-library"
    elif len(sub) == 3 and sub[0] == "interface":
        if sub[1] == "data":
            doc_type = "component-interface-data"
        elif sub[1] == "guarantees" and name.startswith("G-"):
            doc_type = "component-interface-guarantee"
    if doc_type is None:
        return None, None
    return doc_type, comp


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        if not inner.strip():
            return []
        return [item.strip() for item in inner.split(",")]
    if value == "true":
        return True
    if value == "false":
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        return value[1:-1]
    return value


def _parse(text: str) -> tuple:
    """Return (frontmatter, body, has_frontmatter)."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                frontmatter = {}
                for line in lines[1:j]:
                    if ":" in line:
                        key, raw = line.split(":", 1)
                        frontmatter[key.strip()] = _parse_value(raw)
                return frontmatter, "\n".join(lines[j + 1:]), True
    return {}, text, False


def _parse_glossary(text: str, defs: dict) -> None:
    term = None
    chunk: list = []

    def flush() -> None:
        if term is not None:
            joined = "\n".join(chunk)
            defs[term] = _LEADING_RE.sub("", joined).strip()

    for line in text.splitlines():
        match = _ENTRY_RE.match(line)
        if match:
            flush()
            term = match.group(1).strip().lower()
            chunk = [match.group(2)]
        elif term is not None:
            if line.strip() and not line[0].isspace():
                flush()
                term = None
                chunk = []
            else:
                chunk.append(line)
    flush()


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_graph_query_engine(repo_root: Path):
    rel = Path("gen") / "graph-query-engine"
    base = repo_root / rel
    if not base.is_dir():
        base = _tool_root() / rel
    name = "graph_query_engine"
    package_init = base / name / "__init__.py"
    if package_init.is_file():
        spec = importlib.util.spec_from_file_location(
            name, package_init, submodule_search_locations=[str(base / name)]
        )
    else:
        spec = importlib.util.spec_from_file_location(name, base / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _new_component(name: str) -> Component:
    return Component(
        name=name,
        root=None,
        requirements={},
        interface_cli=None,
        interface_library=None,
        interface_data={},
        interface_guarantees={},
        acceptance={},
        constraints=None,
    )


def load_corpus(repo_root: Path) -> Corpus:
    repo_root = Path(repo_root)
    root_abs = repo_root.absolute()
    specs = root_abs / "specs"

    docs: list = []
    components: dict = {}
    id_index: dict = {}

    for path in sorted(specs.rglob("*.md")):
        parts = path.relative_to(specs).parts
        if path.name == "README.md":
            continue
        doc_type, comp = _classify(parts)
        if doc_type is None:
            continue
        text = path.read_text(encoding="utf-8")
        frontmatter, body, has_fm = _parse(text)
        if doc_type in _STEM_ID_TYPES:
            doc_id = path.stem
        else:
            doc_id = frontmatter.get("id")
        doc = Doc(
            path=path,
            rel_path=path.relative_to(root_abs).as_posix(),
            doc_id=doc_id,
            frontmatter=frontmatter,
            body=body,
            doc_type=doc_type,
            component=comp,
            has_frontmatter=has_fm,
        )
        docs.append(doc)

        if doc_type in _ID_INDEX_TYPES:
            id_index[doc_id] = doc

        if comp is not None:
            component = components.get(comp)
            if component is None:
                component = _new_component(comp)
                components[comp] = component
            if doc_type == "component-root":
                component.root = doc
            elif doc_type == "component-requirement":
                component.requirements[doc_id] = doc
            elif doc_type == "component-interface-cli":
                component.interface_cli = doc
            elif doc_type == "component-interface-library":
                component.interface_library = doc
            elif doc_type == "component-interface-data":
                component.interface_data[path.stem] = doc
            elif doc_type == "component-interface-guarantee":
                component.interface_guarantees[doc_id] = doc
            elif doc_type == "component-acceptance":
                component.acceptance[doc_id] = doc
            else:
                component.constraints = doc

    glossary_files = sorted(specs.glob("glossary*.md"))
    glossary_defs: dict = {}
    for gpath in glossary_files:
        _parse_glossary(gpath.read_text(encoding="utf-8"), glossary_defs)

    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    gqe = _load_graph_query_engine(repo_root)
    gqe.load_views(con, repo_root)

    return Corpus(
        repo_root=repo_root,
        docs=docs,
        components=components,
        id_index=id_index,
        glossary_defs=glossary_defs,
        glossary_files=glossary_files,
        graph=con,
    )
