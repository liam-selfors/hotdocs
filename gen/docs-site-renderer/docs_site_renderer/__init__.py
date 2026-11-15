"""Docs site renderer.

Renders ``verification/corpus-graph.json`` (``corpus-graph-builder``'s
``CorpusGraph``) into a static, interactive graph/docs explorer. This is a
pure presentation layer: every value shown comes from the graph alone, and
the in-browser script does the DAG layout and filtering.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import quote

__all__ = ["render_docs_site"]


_ABSENT = '<span class="absent">absent</span>'

_CSS = """
body { font-family: system-ui, sans-serif; margin: 1.5rem; color: #222; }
nav a { margin-right: 1rem; }
pre { background: #f6f8fa; padding: 0.75rem; overflow-x: auto; white-space: pre-wrap; }
table { border-collapse: collapse; }
td, th { border: 1px solid #ccc; padding: 0.25rem 0.5rem; text-align: left; }
.absent { color: #888; font-style: italic; }
.size { padding: 0.1rem 0.4rem; border-radius: 3px; color: #fff; }
.size-ok { background: #2e7d32; }
.size-over { background: #c62828; }
.size-unknown { background: #757575; }
#dag line { stroke: #999; stroke-width: 1; }
#dag line.edge-depends_on { stroke: #1565c0; }
#dag line.edge-realizes { stroke: #2e7d32; }
#dag line.edge-uses_var { stroke: #ef6c00; }
#dag circle { fill: #fff; stroke: #333; stroke-width: 1.5; }
#dag circle.type-capability { fill: #c8e6c9; }
#dag circle.type-component { fill: #bbdefb; }
#dag circle.type-var { fill: #ffe0b2; }
#dag text { font-size: 11px; }
"""

_DAG_SCRIPT = """
(function () {
  var ns = "http://www.w3.org/2000/svg";
  var svg = document.getElementById("dag");
  var nodeEls = Array.prototype.slice.call(document.querySelectorAll("#nodes li.node"));
  var edgeEls = Array.prototype.slice.call(document.querySelectorAll("#edges li.edge"));
  var cols = { capability: 0, component: 1, "var": 2 };
  var rows = [0, 0, 0, 0];
  var pos = {};
  var shapes = {};
  var lines = [];
  nodeEls.forEach(function (li) {
    var id = li.getAttribute("data-id");
    var t = li.getAttribute("data-type");
    var c = Object.prototype.hasOwnProperty.call(cols, t) ? cols[t] : 3;
    pos[id] = { x: 40 + c * 280, y: 30 + rows[c] * 28 };
    rows[c] += 1;
  });
  svg.setAttribute("width", String(4 * 280 + 40));
  svg.setAttribute("height", String(40 + Math.max.apply(null, rows) * 28));
  edgeEls.forEach(function (li) {
    var from = li.getAttribute("data-from");
    var to = li.getAttribute("data-to");
    var a = pos[from];
    var b = pos[to];
    if (!a || !b) { return; }
    var l = document.createElementNS(ns, "line");
    l.setAttribute("x1", a.x); l.setAttribute("y1", a.y);
    l.setAttribute("x2", b.x); l.setAttribute("y2", b.y);
    l.setAttribute("class", "edge-" + li.getAttribute("data-kind"));
    svg.appendChild(l);
    lines.push({ el: l, li: li, from: from, to: to });
  });
  nodeEls.forEach(function (li) {
    var id = li.getAttribute("data-id");
    var p = pos[id];
    var link = document.createElementNS(ns, "a");
    link.setAttribute("href", li.querySelector("a").getAttribute("href"));
    var circ = document.createElementNS(ns, "circle");
    circ.setAttribute("cx", p.x); circ.setAttribute("cy", p.y); circ.setAttribute("r", 7);
    circ.setAttribute("class", "type-" + li.getAttribute("data-type"));
    var text = document.createElementNS(ns, "text");
    text.setAttribute("x", p.x + 11); text.setAttribute("y", p.y + 4);
    text.textContent = id;
    link.appendChild(circ);
    link.appendChild(text);
    svg.appendChild(link);
    shapes[id] = link;
  });
  document.getElementById("search").addEventListener("input", function (e) {
    var q = e.target.value.toLowerCase();
    var vis = {};
    nodeEls.forEach(function (li) {
      var id = li.getAttribute("data-id");
      var show = id.toLowerCase().indexOf(q) >= 0;
      vis[id] = show;
      li.style.display = show ? "" : "none";
      shapes[id].style.display = show ? "" : "none";
    });
    edgeEls.forEach(function (li) {
      var show = vis[li.getAttribute("data-from")] && vis[li.getAttribute("data-to")];
      li.style.display = show ? "" : "none";
    });
    lines.forEach(function (ln) {
      ln.el.style.display = (vis[ln.from] && vis[ln.to]) ? "" : "none";
    });
  });
})();
"""


def _get(obj, key):
    """Read ``key`` from a dict or an attribute-bearing object."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _is_absent(value) -> bool:
    return value is None or (isinstance(value, (str, list, tuple, dict)) and len(value) == 0)


def _render_value(value) -> str:
    if _is_absent(value):
        return _ABSENT
    if isinstance(value, dict):
        items = "".join(
            f"<dt>{_esc(k)}</dt><dd>{_render_value(v)}</dd>" for k, v in value.items()
        )
        return f"<dl>{items}</dl>"
    if isinstance(value, (list, tuple)):
        items = "".join(f"<li>{_render_value(v)}</li>" for v in value)
        return f"<ul>{items}</ul>"
    if isinstance(value, str):
        return _esc(value)
    return _esc(json.dumps(value))


def _node_href(node_id, prefix: str) -> str:
    return f"{prefix}nodes/{quote(str(node_id), safe='')}.html"


def _page(title: str, body: str, prefix: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        f'<nav><a href="{prefix}index.html">Graph</a>'
        f'<a href="{prefix}dashboard.html">Corpus health</a></nav>\n'
        f"<h1>{_esc(title)}</h1>\n{body}\n</body>\n</html>\n"
    )


def _size_badge(status) -> str:
    return f'<span class="size size-{_esc(status)}">{_render_value(status)}</span>'


def _render_index(nodes: dict, edges) -> str:
    node_items = "".join(
        f'<li class="node" data-id="{_esc(node_id)}" data-type="{_esc(_get(node, "type"))}">'
        f'<a href="{_esc(_node_href(node_id, ""))}">{_esc(node_id)}</a> '
        f"({_esc(_get(node, 'type'))})</li>\n"
        for node_id, node in nodes
    )
    edge_items = "".join(
        f'<li class="edge" data-from="{_esc(_get(edge, "from"))}" '
        f'data-to="{_esc(_get(edge, "to"))}" data-kind="{_esc(_get(edge, "kind"))}">'
        f"{_esc(_get(edge, 'from'))} &rarr; {_esc(_get(edge, 'to'))} "
        f"({_esc(_get(edge, 'kind'))})</li>\n"
        for edge in edges
    )
    body = (
        '<input id="search" type="search" placeholder="Search nodes">\n'
        '<svg id="dag" xmlns="http://www.w3.org/2000/svg"></svg>\n'
        f'<h2>Nodes</h2>\n<ul id="nodes">\n{node_items}</ul>\n'
        f'<h2>Edges</h2>\n<ul id="edges">\n{edge_items}</ul>\n'
        f"<script>{_DAG_SCRIPT}</script>"
    )
    return _page("Corpus graph", body, "")


def _render_documents(documents) -> str:
    if _is_absent(documents):
        return _ABSENT
    return "".join(
        f"<section><h3>{_esc(path)}</h3><pre>{_esc(text)}</pre></section>\n"
        for path, text in documents.items()
    )


def _render_criteria(criteria) -> str:
    if _is_absent(criteria):
        return _ABSENT
    if isinstance(criteria, dict):
        entries = list(criteria.items())
    else:
        entries = [(None, value) for value in criteria]
    groups: dict = {}
    for key, value in entries:
        groups.setdefault(_get(value, "kind"), []).append((key, value))
    parts = []
    for kind, members in groups.items():
        items = "".join(
            "<li>"
            + ("" if key is None else f"<strong>{_esc(key)}</strong> ")
            + _render_value(value)
            + "</li>"
            for key, value in members
        )
        parts.append(f"<h3>Kind: {_render_value(kind)}</h3>\n<ul>{items}</ul>\n")
    return "".join(parts)


def _render_component(node_id, node) -> str:
    verification = _get(node, "verification")
    body = (
        f"<p>Type: {_render_value(_get(node, 'type'))}</p>\n"
        f"<h2>Documents</h2>\n{_render_documents(_get(node, 'documents'))}\n"
        "<h2>Requirements</h2>\n"
        f"{_render_value(_get(verification, 'requirement_results'))}\n"
        "<h2>Acceptance criteria</h2>\n"
        f"{_render_criteria(_get(verification, 'criteria'))}\n"
        f"<h2>Provenance</h2>\n{_render_value(_get(node, 'provenance'))}\n"
        f"<h2>Size</h2>\n<p>{_size_badge(_get(node, 'size_status'))}</p>\n"
        "<h2>Exemptions</h2>\n"
        f"<p>Sealed: {_render_value(_get(node, 'sealed'))}</p>\n"
        f"<p>Pinned overrides: {_render_value(_get(node, 'pinned_overrides'))}</p>\n"
        f"<h2>Owners</h2>\n{_render_value(_get(node, 'owners'))}\n"
    )
    return _page(str(node_id), body, "../")


def _render_plain_node(node_id, node) -> str:
    body = f"<p>Type: {_render_value(_get(node, 'type'))}</p>\n"
    return _page(str(node_id), body, "../")


def _render_dashboard(nodes: list, aggregates) -> str:
    if _is_absent(aggregates):
        agg_html = _ABSENT
    else:
        rows = "".join(
            f"<tr><th>{_esc(k)}</th><td>{_render_value(v)}</td></tr>\n"
            for k, v in aggregates.items()
        )
        agg_html = f"<table>\n{rows}</table>"
    size_rows = "".join(
        f'<tr><td><a href="{_esc(_node_href(node_id, ""))}">{_esc(node_id)}</a></td>'
        f"<td>{_size_badge(_get(node, 'size_status'))}</td></tr>\n"
        for node_id, node in nodes
        if _get(node, "type") == "component"
    )
    body = (
        f"<h2>Aggregates</h2>\n{agg_html}\n"
        "<h2>Component size status</h2>\n"
        f"<table>\n<tr><th>Component</th><th>Size</th></tr>\n{size_rows}</table>\n"
    )
    return _page("Corpus health", body, "")


def render_docs_site(graph, out_dir: Path) -> None:
    """Render ``graph`` (a ``CorpusGraph`` or its dict form) into ``out_dir``."""
    out_dir = Path(out_dir)
    nodes = sorted((_get(graph, "nodes") or {}).items(), key=lambda item: str(item[0]))
    edges = _get(graph, "edges") or []
    aggregates = _get(graph, "aggregates")

    nodes_dir = out_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "index.html").write_text(_render_index(nodes, edges), encoding="utf-8")
    (out_dir / "dashboard.html").write_text(
        _render_dashboard(nodes, aggregates), encoding="utf-8"
    )
    for node_id, node in nodes:
        if _get(node, "type") == "component":
            page = _render_component(node_id, node)
        else:
            page = _render_plain_node(node_id, node)
        (nodes_dir / f"{node_id}.html").write_text(page, encoding="utf-8")
