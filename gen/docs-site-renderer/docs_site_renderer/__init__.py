"""Docs Site Renderer: renders corpus-graph.json into a static graph/docs explorer."""

from __future__ import annotations

import html
import importlib.util
import json
import sys
from pathlib import Path

__all__ = ["render_docs_site", "main"]

_ABSENT = '<span class="muted">absent</span>'

_SIZE_TONES = {"ok": "ok", "over": "fail", "unknown": "neutral"}


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _is_absent(value) -> bool:
    return value is None or (isinstance(value, (str, list, tuple, dict)) and len(value) == 0)


def _value(value) -> str:
    if _is_absent(value):
        return _ABSENT
    if isinstance(value, str):
        return _esc(value)
    return _esc(json.dumps(value, sort_keys=True))


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_ui_style():
    path = _tool_root() / "gen" / "ui-style" / "ui_style.py"
    spec = importlib.util.spec_from_file_location("ui_style", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ui_style"] = module
    spec.loader.exec_module(module)
    return module


def _read_asset() -> str:
    return (Path(__file__).parent.parent / "static" / "app.js").read_text(encoding="utf-8")


def _page(title: str, style: str, nav: str, body: str, script: str = "") -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n"
        f"{style}\n"
        "</head>\n"
        "<body>\n"
        f"<nav>{nav}</nav>\n"
        f"<main>\n{body}</main>\n"
        f"{script}"
        "</body>\n"
        "</html>\n"
    )


def _section(title: str, content: str) -> str:
    return f"<section>\n<h2>{_esc(title)}</h2>\n{content}\n</section>\n"


def _rows(value):
    if isinstance(value, dict):
        return sorted(value.items(), key=lambda item: str(item[0]))
    return [(_get(item, "id"), item) for item in value]


def _items(value) -> str:
    if _is_absent(value):
        return _ABSENT
    lines = "".join(f"<li>{_value(item)}</li>\n" for item in value)
    return f"<ul>\n{lines}</ul>"


def _mapping(value) -> str:
    if _is_absent(value):
        return _ABSENT
    lines = "".join(
        f"<dt>{_esc(key)}</dt><dd>{_value(item)}</dd>\n" for key, item in _rows(value)
    )
    return f"<dl>\n{lines}</dl>"


def _documents(documents) -> str:
    if _is_absent(documents):
        return _ABSENT
    return "".join(
        f"<article>\n<h3>{_esc(path)}</h3>\n<pre>{_esc(text)}</pre>\n</article>\n"
        for path, text in _rows(documents)
    )


def _requirements(results) -> str:
    if _is_absent(results):
        return _ABSENT
    lines = "".join(
        f"<li><code>{_value(rid)}</code> {_value(_get(entry, 'status', entry))}</li>\n"
        for rid, entry in _rows(results)
    )
    return f"<ul>\n{lines}</ul>"


def _criteria(criteria) -> str:
    if _is_absent(criteria):
        return _ABSENT
    groups: dict = {}
    for cid, entry in _rows(criteria):
        groups.setdefault(_get(entry, "kind"), []).append((cid, entry))
    out = []
    for kind in sorted(groups, key=str):
        lines = "".join(
            f"<li><code>{_value(cid)}</code> {_value(_get(entry, 'result', entry))}</li>\n"
            for cid, entry in groups[kind]
        )
        out.append(f"<h3>{_value(kind)}</h3>\n<ul>\n{lines}</ul>\n")
    return "".join(out)


def _size(status) -> str:
    tone = _SIZE_TONES.get(status, "neutral")
    return f'<span class="size tone-{tone}">{_value(status)}</span>'


def _component_body(node) -> str:
    verification = _get(node, "verification")
    exemptions = (
        f"<p>Sealed: {_value(_get(node, 'sealed'))}</p>\n"
        f"<h3>Pinned overrides</h3>\n{_items(_get(node, 'pinned_overrides'))}"
    )
    return (
        _section("Documents", _documents(_get(node, "documents")))
        + _section("Requirements", _requirements(_get(verification, "requirement_results")))
        + _section("Acceptance criteria", _criteria(_get(verification, "criteria")))
        + _section("Provenance", _mapping(_get(node, "provenance")))
        + _section("Size", _size(_get(node, "size_status")))
        + _section("Exemptions", exemptions)
        + _section("Owners", _items(_get(node, "owners")))
    )


def _detail_page(node_id, node, style: str) -> str:
    node_type = _get(node, "type")
    body = f"<h1>{_esc(node_id)}</h1>\n<p>Type: {_value(node_type)}</p>\n"
    if node_type == "component":
        body += _component_body(node)
    nav = '<a href="../index.html">Graph</a> <a href="../dashboard.html">Dashboard</a>'
    return _page(str(node_id), style, nav, body)


def _index_page(nodes, edges, style: str, asset: str) -> str:
    node_lines = "".join(
        f'<li class="node" data-id="{_esc(node_id)}" data-type="{_esc(_get(nodes[node_id], "type"))}">'
        f'<a href="nodes/{_esc(node_id)}.html">{_esc(node_id)}</a> '
        f'<span class="muted">{_value(_get(nodes[node_id], "type"))}</span></li>\n'
        for node_id in sorted(nodes)
    )
    edge_lines = "".join(
        f'<li class="edge" data-from="{_esc(_get(edge, "from"))}" data-to="{_esc(_get(edge, "to"))}" '
        f'data-kind="{_esc(_get(edge, "kind"))}">{_esc(_get(edge, "from"))} '
        f'<span class="muted">{_esc(_get(edge, "kind"))}</span> {_esc(_get(edge, "to"))}</li>\n'
        for edge in edges
    )
    body = (
        "<h1>Corpus graph</h1>\n"
        '<label for="search">Search nodes</label>\n'
        '<input id="search" type="search">\n'
        '<svg id="dag"></svg>\n'
        "<h2>Nodes</h2>\n"
        f'<ul id="nodes">\n{node_lines}</ul>\n'
        "<h2>Edges</h2>\n"
        f'<ul id="edges">\n{edge_lines}</ul>\n'
    )
    script = '<script type="module">' + asset + "\ninit(document);\n" + "</script>\n"
    nav = '<a href="dashboard.html">Dashboard</a>'
    return _page("Corpus graph", style, nav, body, script)


def _dashboard_page(aggregates, style: str) -> str:
    if _is_absent(aggregates):
        table = _ABSENT
    else:
        rows = "".join(
            f"<tr><th>{_esc(key)}</th><td>{_value(value)}</td></tr>\n"
            for key, value in _rows(aggregates)
        )
        table = f"<table>\n<tr><th>Metric</th><th>Value</th></tr>\n{rows}</table>"
    body = "<h1>Corpus health</h1>\n" + table + "\n"
    nav = '<a href="index.html">Graph</a>'
    return _page("Corpus health", style, nav, body)


def render_docs_site(graph, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    style = _load_ui_style().style_element()
    asset = _read_asset()
    nodes = _get(graph, "nodes")
    edges = _get(graph, "edges")
    aggregates = _get(graph, "aggregates")

    nodes_dir = out_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "index.html").write_text(_index_page(nodes, edges, style, asset), encoding="utf-8")
    (out_dir / "dashboard.html").write_text(_dashboard_page(aggregates, style), encoding="utf-8")
    for node_id in sorted(nodes):
        (nodes_dir / f"{node_id}.html").write_text(
            _detail_page(node_id, nodes[node_id], style), encoding="utf-8"
        )


from .cli import main  # noqa: E402
