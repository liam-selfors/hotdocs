"""Corpus Loader: reads a spec corpus into one in-memory model."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

__all__ = ["Doc", "Component", "Corpus", "load_corpus"]


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

_ID_INDEX_TYPES = {"component-root", "product", "architecture", "var", "decision"}

_GLOSSARY_ENTRY = re.compile(r"^- \*\*(.+?)\*\*(.*)$")


def _classify(parts):
    """Return (doc_type, component_name) for a path's parts under specs/, or None."""
    name = parts[-1]
    if name == "README.md":
        return None
    if len(parts) == 2 and parts[0] in _TOP_LEVEL_TYPES:
        return _TOP_LEVEL_TYPES[parts[0]], None
    if len(parts) < 3 or parts[0] != "components":
        return None
    comp = parts[1]
    rest = tuple(parts[2:])
    doc_type = None
    if rest == ("component.md",):
        doc_type = "component-root"
    elif rest == ("constraints.md",):
        doc_type = "component-constraints"
    elif rest == ("interface", "cli.md"):
        doc_type = "component-interface-cli"
    elif rest == ("interface", "library.md"):
        doc_type = "component-interface-library"
    elif len(rest) == 2 and rest[0] == "requirements" and name.startswith("R-"):
        doc_type = "component-requirement"
    elif len(rest) == 2 and rest[0] == "acceptance" and name.startswith("AC-"):
        doc_type = "component-acceptance"
    elif len(rest) == 3 and rest[:2] == ("interface", "data"):
        doc_type = "component-interface-data"
    elif len(rest) == 3 and rest[:2] == ("interface", "guarantees") and name.startswith("G-"):
        doc_type = "component-interface-guarantee"
    if doc_type is None:
        return None
    return doc_type, comp


def _parse_value(raw):
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [item.strip() for item in inner.split(",") if item.strip()]
    if value == "true":
        return True
    if value == "false":
        return False
    return value.strip("\"'")


def _parse_text(text):
    """Return (frontmatter, body, has_frontmatter)."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                frontmatter = {}
                for line in lines[1:j]:
                    if ":" in line:
                        key, _, raw = line.partition(":")
                        frontmatter[key.strip()] = _parse_value(raw)
                return frontmatter, "\n".join(lines[j + 1:]), True
    return {}, text, False


def _parse_glossary(text, defs):
    term = None
    buf = []

    def flush():
        if term is not None:
            defs[term] = "\n".join(buf).strip()

    for line in text.splitlines():
        m = _GLOSSARY_ENTRY.match(line)
        if m:
            flush()
            term = m.group(1).strip().lower()
            buf = [m.group(2).lstrip("—- \t")]
        elif term is not None:
            buf.append(line)
    flush()


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_graph_query_engine(repo_root):
    module_name = "graph_query_engine"
    rel = Path("gen") / "graph-query-engine"
    base = Path(repo_root) / rel
    if not base.is_dir():
        base = _tool_root() / rel
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg_dir = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_dir / "__init__.py",
            submodule_search_locations=[str(pkg_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _get(obj, name):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _new_component(name):
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

    docs = []
    components = {}
    id_index = {}

    for path in sorted(specs.rglob("*.md")):
        parts = path.relative_to(specs).parts
        classified = _classify(parts)
        if classified is None:
            continue
        doc_type, comp_name = classified
        text = path.read_text(encoding="utf-8")
        frontmatter, body, has_fm = _parse_text(text)
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
            component=comp_name,
            has_frontmatter=has_fm,
        )
        docs.append(doc)

        if doc_type in _ID_INDEX_TYPES:
            id_index[doc_id] = doc

        if comp_name is None:
            continue
        comp = components.get(comp_name)
        if comp is None:
            comp = _new_component(comp_name)
            components[comp_name] = comp
        if doc_type == "component-root":
            comp.root = doc
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
        elif doc_type == "component-acceptance":
            comp.acceptance[doc_id] = doc
        else:
            comp.constraints = doc

    glossary_files = sorted(specs.glob("glossary*.md"))
    glossary_defs = {}
    for gpath in glossary_files:
        _parse_glossary(gpath.read_text(encoding="utf-8"), glossary_defs)

    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    gqe = _load_graph_query_engine(repo_root)
    _get(gqe, "load_views")(con, repo_root)

    return Corpus(
        repo_root=repo_root,
        docs=docs,
        components=components,
        id_index=id_index,
        glossary_defs=glossary_defs,
        glossary_files=glossary_files,
        graph=con,
    )
