"""Corpus Loader: reads a spec corpus into one in-memory model."""
from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
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
    root: Any = None
    requirements: dict = field(default_factory=dict)
    interface_cli: Any = None
    interface_library: Any = None
    interface_data: dict = field(default_factory=dict)
    interface_guarantees: dict = field(default_factory=dict)
    acceptance: dict = field(default_factory=dict)
    constraints: Any = None


@dataclass
class Corpus:
    repo_root: Path
    docs: list
    components: dict
    id_index: dict
    glossary_defs: dict
    glossary_files: list
    graph: Any


_TOP_DIRS = {
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


def _classify(parts: tuple) -> tuple:
    """Return (doc_type, component_name) or (None, None) for unlisted paths."""
    if len(parts) == 2 and parts[0] in _TOP_DIRS:
        return _TOP_DIRS[parts[0]], None
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
        if len(sub) == 3 and sub[:2] == ("interface", "guarantees") and name.startswith("G-"):
            return "component-interface-guarantee", comp
        if len(sub) == 2 and sub[0] == "acceptance" and name.startswith("AC-"):
            return "component-acceptance", comp
    return None, None


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [s.strip() for s in value[1:-1].split(",") if s.strip()]
    if value == "true":
        return True
    if value == "false":
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _split_frontmatter(text: str) -> tuple:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm = {}
                for line in lines[1:i]:
                    key, sep, val = line.partition(":")
                    if sep:
                        fm[key.strip()] = _parse_value(val)
                return fm, "\n".join(lines[i + 1:]), True
    return {}, text, False


_ENTRY_RE = re.compile(r"^- \*\*(.+?)\*\*(.*)$")


def _parse_glossary(text: str, defs: dict) -> None:
    term = None
    chunk: list = []

    def flush() -> None:
        if term is not None:
            joined = "\n".join(chunk).lstrip("—- \t\n").strip()
            defs[term.lower()] = joined

    for line in text.splitlines():
        m = _ENTRY_RE.match(line)
        if m:
            flush()
            term = m.group(1)
            chunk = [m.group(2)]
        elif term is not None and (line.strip() == "" or line[:1].isspace()):
            chunk.append(line)
        else:
            flush()
            term = None
            chunk = []
    flush()


def _tool_root() -> Path:
    for parent in Path(__file__).absolute().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).absolute().parent


def _load_graph_query_engine(repo_root: Path):
    rel = Path("gen") / "graph-query-engine"
    base = repo_root / rel
    if not base.is_dir():
        base = _tool_root() / rel
    pkg_init = base / "graph_query_engine" / "__init__.py"
    name = "graph_query_engine"
    if pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            name, pkg_init, submodule_search_locations=[str(pkg_init.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location(name, base / "graph_query_engine.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _dep_get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def load_corpus(repo_root: Path) -> Corpus:
    root = Path(repo_root).absolute()
    specs = root / "specs"

    docs: list = []
    components: dict = {}
    id_index: dict = {}

    for path in sorted(specs.rglob("*.md")):
        if path.name == "README.md":
            continue
        doc_type, comp_name = _classify(path.relative_to(specs).parts)
        if doc_type is None:
            continue
        text = path.read_text(encoding="utf-8")
        fm, body, has_fm = _split_frontmatter(text)
        doc_id = path.stem if doc_type in _STEM_ID_TYPES else fm.get("id")
        doc = Doc(
            path=path,
            rel_path=path.relative_to(root).as_posix(),
            doc_id=doc_id,
            frontmatter=fm,
            body=body,
            doc_type=doc_type,
            component=comp_name,
            has_frontmatter=has_fm,
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

    glossary_files = sorted(specs.glob("glossary*.md"))
    glossary_defs: dict = {}
    for gpath in glossary_files:
        _parse_glossary(gpath.read_text(encoding="utf-8"), glossary_defs)

    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    gqe = _load_graph_query_engine(root)
    _dep_get(gqe, "load_views")(con, root)

    return Corpus(
        repo_root=root,
        docs=docs,
        components=components,
        id_index=id_index,
        glossary_defs=glossary_defs,
        glossary_files=glossary_files,
        graph=con,
    )
