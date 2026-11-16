"""Corpus Loader: reads a spec corpus into one in-memory model."""

from __future__ import annotations

import importlib.util
import re
import string
import sys
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import duckdb

_DEP_SLUG = "graph-query-engine"
_DEP_MODULE = "graph_query_engine"

# Patterns relative to specs/, checked part-by-part.
_DOC_TYPES = (
    ("components/*/component.md", "component-root"),
    ("components/*/requirements/R-*.md", "component-requirement"),
    ("components/*/interface/cli.md", "component-interface-cli"),
    ("components/*/interface/library.md", "component-interface-library"),
    ("components/*/interface/data/*.md", "component-interface-data"),
    ("components/*/interface/guarantees/G-*.md", "component-interface-guarantee"),
    ("components/*/acceptance/AC-*.md", "component-acceptance"),
    ("components/*/constraints.md", "component-constraints"),
    ("product/*.md", "product"),
    ("architecture/*.md", "architecture"),
    ("vars/*.md", "var"),
    ("decisions/*.md", "decision"),
)

_STEM_ID_TYPES = {
    "component-requirement",
    "component-acceptance",
    "component-interface-guarantee",
}

_INDEXED_TYPES = {"component-root", "product", "architecture", "var", "decision"}

_SINGLE_ATTRS = {
    "component-root": "root",
    "component-interface-cli": "interface_cli",
    "component-interface-library": "interface_library",
    "component-constraints": "constraints",
}

_KEYED_ATTRS = {
    "component-requirement": "requirements",
    "component-interface-data": "interface_data",
    "component-interface-guarantee": "interface_guarantees",
    "component-acceptance": "acceptance",
}

_ENTRY_RE = re.compile(r"^-\s+\*\*(.+?)\*\*(.*)$")
_LEAD = "\u2014-" + string.whitespace


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


def _matches(parts: tuple, pattern: str) -> bool:
    pat = pattern.split("/")
    return len(parts) == len(pat) and all(
        fnmatchcase(part, p) for part, p in zip(parts, pat)
    )


def _classify(parts: tuple) -> Any:
    for pattern, doc_type in _DOC_TYPES:
        if _matches(parts, pattern):
            return doc_type
    return None


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [item.strip() for item in value[1:-1].split(",") if item.strip()]
    if value in ("true", "false"):
        return value == "true"
    return value.strip("\"'")


def _split(text: str) -> tuple:
    lines = text.splitlines()
    if lines[:1] == ["---"] and "---" in lines[1:]:
        end = lines.index("---", 1)
        frontmatter = {}
        for line in lines[1:end]:
            if ":" in line:
                key, _, raw = line.partition(":")
                frontmatter[key.strip()] = _parse_value(raw)
        return frontmatter, "\n".join(lines[end + 1:]), True
    return {}, text, False


def _glossary_defs(files: list) -> dict:
    defs = {}
    for path in files:
        entries = []
        current = None
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _ENTRY_RE.match(line)
            if match:
                current = [match.group(2).lstrip(_LEAD)]
                entries.append((match.group(1).strip().lower(), current))
            elif current is not None and (not line.strip() or line[0].isspace()):
                current.append(line)
            else:
                current = None
        for term, lines in entries:
            defs[term] = "\n".join(lines).strip()
    return defs


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load_graph_query_engine(repo_root: Path):
    dep_dir = repo_root / "gen" / _DEP_SLUG
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / _DEP_SLUG
    flat = dep_dir / f"{_DEP_MODULE}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(_DEP_MODULE, flat)
    else:
        pkg = dep_dir / _DEP_MODULE
        spec = importlib.util.spec_from_file_location(
            _DEP_MODULE, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DEP_MODULE] = module
    spec.loader.exec_module(module)
    return module


def _new_component(name: str) -> Component:
    return Component(name, None, {}, None, None, {}, {}, {}, None)


def load_corpus(repo_root: Path) -> Corpus:
    root = Path(repo_root).absolute()
    specs = root / "specs"

    docs = []
    components = {}
    id_index = {}
    for path in sorted(specs.rglob("*.md")):
        if path.name == "README.md":
            continue
        parts = path.relative_to(specs).parts
        doc_type = _classify(parts)
        if doc_type is None:
            continue
        frontmatter, body, has_frontmatter = _split(path.read_text(encoding="utf-8"))
        if doc_type in _STEM_ID_TYPES:
            doc_id = path.stem
        else:
            doc_id = frontmatter.get("id")
        component = parts[1] if doc_type.startswith("component-") else None
        doc = Doc(
            path,
            path.relative_to(root).as_posix(),
            doc_id,
            frontmatter,
            body,
            doc_type,
            component,
            has_frontmatter,
        )
        docs.append(doc)

        if component is not None:
            if component not in components:
                components[component] = _new_component(component)
            comp = components[component]
            if doc_type in _SINGLE_ATTRS:
                setattr(comp, _SINGLE_ATTRS[doc_type], doc)
            else:
                getattr(comp, _KEYED_ATTRS[doc_type])[path.stem] = doc

        if doc_type in _INDEXED_TYPES:
            id_index[doc_id] = doc

    glossary_files = sorted(specs.glob("glossary*.md"))
    glossary_defs = _glossary_defs(glossary_files)

    graph = duckdb.connect()
    graph.execute("INSTALL yaml FROM community")
    graph.execute("LOAD yaml")
    gqe = _load_graph_query_engine(root)
    gqe.load_views(graph, root)

    return Corpus(
        root,
        docs,
        components,
        id_index,
        glossary_defs,
        glossary_files,
        graph,
    )
