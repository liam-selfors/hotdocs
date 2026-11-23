"""Docs Site Renderer: renders a CorpusGraph into a static graph/docs explorer.

A pure presentation layer over `verification/corpus-graph.json`: the only
other file read is the component's own asset `static/app.js`.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ASSET_PATH = Path(__file__).parent.parent / "static" / "app.js"

CSS = (
    "body{font-family:sans-serif;margin:1.5em;}"
    ".hidden{display:none;}"
    ".absent{color:#888;font-style:italic;}"
    ".size-ok{color:#2e7d32;}"
    ".size-over{color:#c62828;}"
    ".size-unknown{color:#888;}"
    "pre{background:#f5f5f5;padding:0.5em;white-space:pre-wrap;}"
    "svg#dag line{stroke-width:1.5;}"
    "svg#dag circle{fill:#455a64;}"
    "svg#dag text{font-size:12px;}"
)


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _scalar(value) -> str:
    if isinstance(value, str):
        return _e(value)
    return _e(json.dumps(value))


def _value(value) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return '<span class="absent">absent</span>'
    if isinstance(value, dict):
        items = "".join(
            f"<dt>{_e(key)}</dt><dd>{_value(value[key])}</dd>" for key in sorted(value)
        )
        return f"<dl>{items}</dl>"
    if isinstance(value, list):
        items = "".join(f"<li>{_value(item)}</li>" for item in value)
        return f"<ul>{items}</ul>"
    return _scalar(value)


def _entries(value):
    if isinstance(value, dict):
        return list(value.items())
    return [(None, item) for item in value or []]


def _detail_href(node_id) -> str:
    return f"nodes/{node_id}.html"


def _page(title: str, body: str, script: str = "") -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{_e(title)}</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}"
        f"{script}"
        "</body>\n"
        "</html>\n"
    )


def _index_html(nodes, edges, asset_text: str) -> str:
    node_items = "".join(
        f'<li class="node" data-id="{_e(node_id)}" '
        f'data-type="{_e(_get(nodes[node_id], "type"))}">'
        f'<a href="{_e(_detail_href(node_id))}">{_e(node_id)}</a></li>\n'
        for node_id in sorted(nodes)
    )
    edge_items = "".join(
        f'<li class="edge" data-from="{_e(_get(edge, "from"))}" '
        f'data-to="{_e(_get(edge, "to"))}" data-kind="{_e(_get(edge, "kind"))}">'
        f'{_e(_get(edge, "from"))} &rarr; {_e(_get(edge, "to"))} '
        f'({_e(_get(edge, "kind"))})</li>\n'
        for edge in edges
    )
    body = (
        "<h1>Corpus graph</h1>\n"
        '<p><a href="dashboard.html">Corpus health dashboard</a></p>\n'
        '<input id="search" type="search">\n'
        '<svg id="dag"></svg>\n'
        "<h2>Nodes</h2>\n"
        f'<ul id="nodes">\n{node_items}</ul>\n'
        "<h2>Edges</h2>\n"
        f'<ul id="edges">\n{edge_items}</ul>\n'
    )
    script = '<script type="module">' + asset_text + "\ninit(document);\n" + "</script>\n"
    return _page("Corpus graph", body, script)


def _criteria_html(criteria) -> str:
    groups: dict = {}
    for key, item in _entries(criteria):
        groups.setdefault(_get(item, "kind"), []).append((key, item))
    if not groups:
        return _value(None)
    parts = []
    for kind, members in groups.items():
        items = "".join(
            "<li>"
            + ("" if key is None else f"<strong>{_e(key)}</strong>: ")
            + _value(item)
            + "</li>"
            for key, item in members
        )
        parts.append(f'<h3 class="kind">{_value(kind)}</h3>\n<ul>{items}</ul>\n')
    return "".join(parts)


def _component_body(node) -> str:
    verification = _get(node, "verification")
    documents = _get(node, "documents") or {}
    if documents:
        docs = "".join(
            f'<section class="document"><h3>{_e(path)}</h3>'
            f"<pre>{_e(text)}</pre></section>\n"
            for path, text in documents.items()
        )
    else:
        docs = _value(None)
    size_status = _get(node, "size_status")
    return (
        "<h2>Documents</h2>\n"
        f"{docs}\n"
        "<h2>Requirements</h2>\n"
        f'<div id="requirements">{_value(_get(verification, "requirement_results"))}</div>\n'
        "<h2>Acceptance criteria</h2>\n"
        f'<div id="criteria">{_criteria_html(_get(verification, "criteria"))}</div>\n'
        "<h2>Provenance</h2>\n"
        f'<div id="provenance">{_value(_get(node, "provenance"))}</div>\n'
        "<h2>Size</h2>\n"
        f'<p id="size" class="size size-{_e(size_status)}">{_value(size_status)}</p>\n'
        "<h2>Exemptions</h2>\n"
        f'<p id="sealed">sealed: {_value(_get(node, "sealed"))}</p>\n'
        f'<div id="pinned-overrides">pinned overrides: '
        f'{_value(_get(node, "pinned_overrides"))}</div>\n'
        "<h2>Owners</h2>\n"
        f'<div id="owners">{_value(_get(node, "owners"))}</div>\n'
    )


def _detail_html(node_id, node) -> str:
    node_type = _get(node, "type")
    body = (
        '<p><a href="../index.html">Graph</a> | '
        '<a href="../dashboard.html">Dashboard</a></p>\n'
        f"<h1>{_e(node_id)}</h1>\n"
        f'<p class="type">type: {_value(node_type)}</p>\n'
    )
    if node_type == "component":
        body += _component_body(node)
    return _page(str(node_id), body)


def _dashboard_html(nodes, aggregates) -> str:
    type_counts: dict = {}
    size_counts: dict = {}
    for node_id in sorted(nodes):
        node = nodes[node_id]
        node_type = _get(node, "type")
        type_counts[node_type] = type_counts.get(node_type, 0) + 1
        if node_type == "component":
            status = _get(node, "size_status")
            size_counts[status] = size_counts.get(status, 0) + 1
    type_rows = "".join(
        f"<tr><td>{_value(key)}</td><td>{count}</td></tr>"
        for key, count in type_counts.items()
    )
    size_rows = "".join(
        f'<tr class="size-{_e(key)}"><td>{_value(key)}</td><td>{count}</td></tr>'
        for key, count in size_counts.items()
    )
    body = (
        '<p><a href="index.html">Graph</a></p>\n'
        "<h1>Corpus health</h1>\n"
        "<h2>Metrics</h2>\n"
        f'<div id="aggregates">{_value(aggregates)}</div>\n'
        "<h2>Nodes by type</h2>\n"
        f'<table id="node-types">{type_rows}</table>\n'
        "<h2>Size-cap distribution</h2>\n"
        f'<table id="size-distribution">{size_rows}</table>\n'
    )
    return _page("Corpus health", body)


def render_docs_site(graph, out_dir: Path) -> None:
    nodes = _get(graph, "nodes") or {}
    edges = _get(graph, "edges") or []
    aggregates = _get(graph, "aggregates")
    asset_text = ASSET_PATH.read_text(encoding="utf-8")

    out_dir = Path(out_dir)
    (out_dir / "nodes").mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        _index_html(nodes, edges, asset_text), encoding="utf-8"
    )
    (out_dir / "dashboard.html").write_text(
        _dashboard_html(nodes, aggregates), encoding="utf-8"
    )
    for node_id in sorted(nodes):
        (out_dir / _detail_href(node_id)).write_text(
            _detail_html(node_id, nodes[node_id]), encoding="utf-8"
        )


from .cli import main  # noqa: E402

__all__ = ["render_docs_site", "main"]
