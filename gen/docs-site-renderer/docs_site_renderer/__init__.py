"""Docs Site Renderer.

Renders a ``CorpusGraph`` (the contents of ``verification/corpus-graph.json``)
into a static, interactive graph/docs explorer. Pure presentation: nothing is
read or computed beyond what the graph already holds.
"""

import html
import json
from pathlib import Path
from urllib.parse import quote

__all__ = ["render_docs_site"]

_ABSENT = '<span class="absent">absent</span>'

_STYLE = """
body { font-family: system-ui, sans-serif; margin: 1.5rem; color: #222; }
h1, h2, h3 { font-weight: 600; }
table.kv { border-collapse: collapse; margin: 0.25rem 0; }
table.kv th, table.kv td { border: 1px solid #ccc; padding: 0.2rem 0.5rem;
  text-align: left; vertical-align: top; }
pre { background: #f6f6f6; padding: 0.75rem; overflow-x: auto;
  white-space: pre-wrap; }
.absent { color: #888; font-style: italic; }
.size { padding: 0.1rem 0.5rem; border-radius: 0.25rem; color: #fff; }
.size-ok { background: #2e7d32; }
.size-over { background: #c62828; }
.size-unknown { background: #757575; }
#dag-canvas { border: 1px solid #ddd; display: block; margin: 0.5rem 0; }
#dag-canvas .edge-line { stroke: #999; stroke-width: 1.5; }
#dag-canvas .kind-depends_on { stroke: #1565c0; }
#dag-canvas .kind-realizes { stroke: #2e7d32; }
#dag-canvas .kind-uses_var { stroke: #ef6c00; }
#dag-canvas circle { fill: #fff; stroke: #333; stroke-width: 1.5; }
#dag-canvas .type-capability circle { fill: #c8e6c9; }
#dag-canvas .type-component circle { fill: #bbdefb; }
#dag-canvas .type-var circle { fill: #ffe0b2; }
#dag-canvas text { font-size: 12px; }
"""

_DAG_SCRIPT = """
(function () {
  var svgNS = "http://www.w3.org/2000/svg";
  var nodeEls = Array.prototype.slice.call(document.querySelectorAll("#dag-nodes .node"));
  var edgeEls = Array.prototype.slice.call(document.querySelectorAll("#dag-edges .edge"));
  var svg = document.getElementById("dag-canvas");
  var search = document.getElementById("dag-search");
  var columns = {capability: 0, component: 1, "var": 2};
  var counts = {};
  var pos = {};
  var shapes = {};
  var lines = [];
  var maxRows = 0;
  nodeEls.forEach(function (el) {
    var type = el.getAttribute("data-type");
    var col = Object.prototype.hasOwnProperty.call(columns, type) ? columns[type] : 3;
    var row = counts[col] || 0;
    counts[col] = row + 1;
    if (row + 1 > maxRows) { maxRows = row + 1; }
    pos[el.getAttribute("data-id")] = {x: 40 + col * 300, y: 30 + row * 40};
  });
  svg.setAttribute("width", 1240);
  svg.setAttribute("height", 60 + maxRows * 40);
  edgeEls.forEach(function (el) {
    var a = pos[el.getAttribute("data-from")];
    var b = pos[el.getAttribute("data-to")];
    if (!a || !b) { return; }
    var line = document.createElementNS(svgNS, "line");
    line.setAttribute("x1", a.x);
    line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x);
    line.setAttribute("y2", b.y);
    line.setAttribute("class", "edge-line kind-" + el.getAttribute("data-kind"));
    svg.appendChild(line);
    lines.push({line: line, from: el.getAttribute("data-from"), to: el.getAttribute("data-to")});
  });
  nodeEls.forEach(function (el) {
    var id = el.getAttribute("data-id");
    var p = pos[id];
    var link = document.createElementNS(svgNS, "a");
    link.setAttribute("href", el.querySelector("a").getAttribute("href"));
    link.setAttribute("class", "type-" + el.getAttribute("data-type"));
    var circle = document.createElementNS(svgNS, "circle");
    circle.setAttribute("cx", p.x);
    circle.setAttribute("cy", p.y);
    circle.setAttribute("r", 8);
    var text = document.createElementNS(svgNS, "text");
    text.setAttribute("x", p.x + 12);
    text.setAttribute("y", p.y + 4);
    text.textContent = id;
    link.appendChild(circle);
    link.appendChild(text);
    svg.appendChild(link);
    shapes[id] = link;
  });
  search.addEventListener("input", function () {
    var q = search.value.toLowerCase();
    var visible = {};
    nodeEls.forEach(function (el) {
      var id = el.getAttribute("data-id");
      var show = id.toLowerCase().indexOf(q) !== -1;
      visible[id] = show;
      el.style.display = show ? "" : "none";
      shapes[id].style.display = show ? "" : "none";
    });
    lines.forEach(function (l) {
      l.line.style.display = (visible[l.from] && visible[l.to]) ? "" : "none";
    });
    edgeEls.forEach(function (el) {
      var show = visible[el.getAttribute("data-from")] || visible[el.getAttribute("data-to")];
      el.style.display = show ? "" : "none";
    });
  });
})();
"""


def _field(obj, key):
    """Dual dict-or-attribute access."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _esc(value):
    return html.escape(str(value), quote=True)


def _is_absent(value):
    return value is None or (isinstance(value, (str, list, dict)) and not value)


def _render_value(value):
    if _is_absent(value):
        return _ABSENT
    if isinstance(value, dict):
        rows = "".join(
            f"<tr><th>{_esc(k)}</th><td>{_render_value(v)}</td></tr>"
            for k, v in value.items()
        )
        return f'<table class="kv">{rows}</table>'
    if isinstance(value, list):
        items = "".join(f"<li>{_render_value(v)}</li>" for v in value)
        return f"<ul>{items}</ul>"
    if isinstance(value, str):
        return _esc(value)
    return _esc(json.dumps(value))


def _page(title, body, prefix):
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>{_STYLE}</style>\n"
        "</head>\n<body>\n"
        f'<nav><a href="{prefix}index.html">Graph &amp; corpus health</a></nav>\n'
        f"{body}\n"
        "</body>\n</html>\n"
    )


def _href(node_id):
    return "nodes/" + quote(str(node_id), safe="") + ".html"


def _render_criteria(criteria):
    if isinstance(criteria, dict):
        items = sorted(criteria.items())
    else:
        items = [(_field(c, "id"), c) for c in (criteria or [])]
    groups = {}
    for cid, c in items:
        groups.setdefault(str(_field(c, "kind")), []).append((cid, c))
    parts = []
    for kind in sorted(groups):
        rows = "".join(
            f"<tr><th>{_render_value(cid)}</th><td>{_render_value(c)}</td></tr>"
            for cid, c in groups[kind]
        )
        parts.append(
            f'<h3>kind: {_esc(kind)}</h3><table class="kv">{rows}</table>'
        )
    return "".join(parts) or _ABSENT


def _component_body(node):
    verification = _field(node, "verification")
    documents = _field(node, "documents")
    size = _field(node, "size_status")
    docs_html = "".join(
        f'<section class="document"><h3>{_esc(path)}</h3>'
        f"<pre>{_esc(text)}</pre></section>"
        for path, text in sorted((documents or {}).items())
    ) or _ABSENT
    return (
        "<h2>Documents</h2>\n"
        f"{docs_html}\n"
        "<h2>Requirements</h2>\n"
        f'<div class="requirements">'
        f"{_render_value(_field(verification, 'requirement_results'))}</div>\n"
        "<h2>Acceptance criteria</h2>\n"
        f'<div class="criteria">{_render_criteria(_field(verification, "criteria"))}</div>\n'
        "<h2>Provenance</h2>\n"
        f'<div class="provenance">{_render_value(_field(node, "provenance"))}</div>\n'
        "<h2>Size</h2>\n"
        f'<p><span class="size size-{_esc(size)}">{_render_value(size)}</span></p>\n'
        "<h2>Exemptions</h2>\n"
        f'<p>Sealed: <span class="sealed">{_render_value(_field(node, "sealed"))}</span></p>\n'
        f'<div class="pinned-overrides">Pinned overrides: '
        f'{_render_value(_field(node, "pinned_overrides"))}</div>\n'
        "<h2>Owners</h2>\n"
        f'<div class="owners">{_render_value(_field(node, "owners"))}</div>\n'
    )


def _detail_page(node_id, node):
    node_type = _field(node, "type")
    body = (
        f"<h1>{_esc(node_id)}</h1>\n"
        f'<p>Type: <span class="node-type">{_render_value(node_type)}</span></p>\n'
    )
    if node_type == "component":
        body += _component_body(node)
    return _page(str(node_id), body, "../")


def _index_page(nodes, edges, aggregates):
    node_items = "".join(
        f'<li class="node" data-id="{_esc(node_id)}" '
        f'data-type="{_esc(_field(node, "type"))}">'
        f'<a href="{_esc(_href(node_id))}">{_esc(node_id)}</a> '
        f'<span class="node-type">({_esc(_field(node, "type"))})</span></li>\n'
        for node_id, node in sorted(nodes.items())
    )
    edge_items = "".join(
        f'<li class="edge" data-from="{_esc(_field(e, "from"))}" '
        f'data-to="{_esc(_field(e, "to"))}" data-kind="{_esc(_field(e, "kind"))}">'
        f'{_esc(_field(e, "from"))} &rarr; {_esc(_field(e, "to"))} '
        f'({_esc(_field(e, "kind"))})</li>\n'
        for e in edges
    )
    size_counts = {}
    for _node_id, node in sorted(nodes.items()):
        if _field(node, "type") == "component":
            key = str(_field(node, "size_status"))
            size_counts[key] = size_counts.get(key, 0) + 1
    size_rows = "".join(
        f'<tr><th><span class="size size-{_esc(k)}">{_esc(k)}</span></th>'
        f"<td>{_esc(v)}</td></tr>"
        for k, v in sorted(size_counts.items())
    )
    size_html = f'<table class="kv">{size_rows}</table>' if size_rows else _ABSENT
    body = (
        "<h1>Corpus graph</h1>\n"
        '<section id="dag">\n'
        '<input id="dag-search" type="search" placeholder="Search nodes">\n'
        '<svg id="dag-canvas" xmlns="http://www.w3.org/2000/svg"></svg>\n'
        "<h2>Nodes</h2>\n"
        f'<ul id="dag-nodes">\n{node_items}</ul>\n'
        "<h2>Edges</h2>\n"
        f'<ul id="dag-edges">\n{edge_items}</ul>\n'
        "</section>\n"
        '<section id="health">\n'
        "<h1>Corpus health</h1>\n"
        "<h2>Aggregates</h2>\n"
        f'<div class="aggregates">{_render_value(aggregates)}</div>\n'
        "<h2>Size-cap distribution</h2>\n"
        f'<div class="size-distribution">{size_html}</div>\n'
        "</section>\n"
        f"<script>{_DAG_SCRIPT}</script>"
    )
    return _page("Corpus graph", body, "")


def render_docs_site(graph, out_dir):
    """Render ``graph`` (a CorpusGraph or its dict shape) into ``out_dir``."""
    out_dir = Path(out_dir)
    nodes = _field(graph, "nodes") or {}
    edges = _field(graph, "edges") or []
    aggregates = _field(graph, "aggregates")
    nodes_dir = out_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        _index_page(nodes, edges, aggregates), encoding="utf-8"
    )
    for node_id, node in sorted(nodes.items()):
        (nodes_dir / f"{node_id}.html").write_text(
            _detail_page(node_id, node), encoding="utf-8"
        )
