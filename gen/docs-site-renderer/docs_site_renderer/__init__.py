"""Docs Site Renderer: a pure presentation layer over corpus-graph.json."""

from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import quote

__all__ = ["render_docs_site"]


_STYLE = """
body { font-family: sans-serif; margin: 1.5em; }
.absent { color: #888; font-style: italic; }
.size { padding: 0.1em 0.5em; border-radius: 0.3em; color: #fff; }
.size-ok { background: #2e7d32; }
.size-over { background: #c62828; }
.size-unknown { background: #757575; }
pre { background: #f4f4f4; padding: 0.8em; white-space: pre-wrap; }
table { border-collapse: collapse; }
td, th { border: 1px solid #ccc; padding: 0.2em 0.5em; vertical-align: top; text-align: left; }
#dag { border: 1px solid #ccc; }
.hidden { display: none; }
"""

_DAG_SCRIPT = """
(function () {
  var svgNS = "http://www.w3.org/2000/svg";
  var svg = document.getElementById("dag");
  var nodeEls = Array.prototype.slice.call(document.querySelectorAll("#nodes .node"));
  var edgeEls = Array.prototype.slice.call(document.querySelectorAll("#edges .edge"));
  var columns = {capability: 0, component: 1, "var": 2};
  var counts = {};
  var pos = {};
  var marks = {};
  nodeEls.forEach(function (li) {
    var col = columns.hasOwnProperty(li.dataset.type) ? columns[li.dataset.type] : 3;
    counts[col] = (counts[col] || 0) + 1;
    pos[li.dataset.id] = {x: 120 + col * 260, y: 30 + (counts[col] - 1) * 40};
  });
  var maxRows = 1;
  Object.keys(counts).forEach(function (k) { maxRows = Math.max(maxRows, counts[k]); });
  svg.setAttribute("width", 1100);
  svg.setAttribute("height", 60 + maxRows * 40);
  var lines = [];
  edgeEls.forEach(function (li) {
    var a = pos[li.dataset.from], b = pos[li.dataset.to];
    if (!a || !b) { return; }
    var line = document.createElementNS(svgNS, "line");
    line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
    line.setAttribute("stroke", li.dataset.kind === "depends_on" ? "#1565c0" :
      (li.dataset.kind === "realizes" ? "#2e7d32" : "#ef6c00"));
    svg.appendChild(line);
    lines.push({el: line, from: li.dataset.from, to: li.dataset.to, li: li});
  });
  nodeEls.forEach(function (li) {
    var p = pos[li.dataset.id];
    var href = li.querySelector("a").getAttribute("href");
    var g = document.createElementNS(svgNS, "g");
    g.style.cursor = "pointer";
    g.addEventListener("click", function () { window.location.href = href; });
    var c = document.createElementNS(svgNS, "circle");
    c.setAttribute("cx", p.x); c.setAttribute("cy", p.y); c.setAttribute("r", 8);
    c.setAttribute("fill", "#455a64");
    var t = document.createElementNS(svgNS, "text");
    t.setAttribute("x", p.x + 12); t.setAttribute("y", p.y + 4);
    t.textContent = li.dataset.id;
    g.appendChild(c); g.appendChild(t);
    svg.appendChild(g);
    marks[li.dataset.id] = g;
  });
  document.getElementById("search").addEventListener("input", function (ev) {
    var q = ev.target.value.toLowerCase();
    var shown = {};
    nodeEls.forEach(function (li) {
      var ok = li.dataset.id.toLowerCase().indexOf(q) !== -1;
      shown[li.dataset.id] = ok;
      li.classList.toggle("hidden", !ok);
      marks[li.dataset.id].style.display = ok ? "" : "none";
    });
    lines.forEach(function (l) {
      var ok = shown[l.from] && shown[l.to];
      l.el.style.display = ok ? "" : "none";
    });
    edgeEls.forEach(function (li) {
      li.classList.toggle("hidden", !(shown[li.dataset.from] && shown[li.dataset.to]));
    });
  });
})();
"""


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _absent() -> str:
    return '<span class="absent">absent</span>'


def _render_value(value) -> str:
    if value is None or (isinstance(value, (dict, list, str)) and not value):
        return _absent()
    if isinstance(value, dict):
        rows = "".join(
            "<tr><th>%s</th><td>%s</td></tr>" % (_esc(k), _render_value(v))
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        )
        return "<table>%s</table>" % rows
    if isinstance(value, list):
        return "<ul>%s</ul>" % "".join("<li>%s</li>" % _render_value(v) for v in value)
    if isinstance(value, str):
        return _esc(value)
    return _esc(json.dumps(value))


def _page(title: str, body: str, prefix: str) -> str:
    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        "<title>%s</title><style>%s</style></head><body>"
        "<nav><a href=\"%sindex.html\">Graph</a> | "
        "<a href=\"%sdashboard.html\">Corpus health</a></nav>"
        "<h1>%s</h1>%s</body></html>\n"
    ) % (_esc(title), _STYLE, prefix, prefix, _esc(title), body)


def _node_file(node_id) -> str:
    return "%s.html" % node_id


def _size_badge(status) -> str:
    if status is None:
        return _absent()
    return '<span class="size size-%s">%s</span>' % (_esc(status), _esc(status))


def _render_criteria(criteria) -> str:
    if not criteria:
        return _absent()
    if isinstance(criteria, dict):
        pairs = list(criteria.items())
    else:
        pairs = [(None, c) for c in criteria]
    groups: dict = {}
    for cid, crit in pairs:
        groups.setdefault(_get(crit, "kind"), []).append((cid, crit))
    parts = []
    for kind in sorted(groups, key=str):
        parts.append("<h3>kind: %s</h3>" % _esc(kind))
        for cid, crit in groups[kind]:
            if cid is not None:
                parts.append("<h4>%s</h4>" % _esc(cid))
            parts.append(_render_value(crit))
    return "".join(parts)


def _component_body(node) -> str:
    verification = _get(node, "verification")
    documents = _get(node, "documents")
    if not documents:
        docs_html = _absent()
    else:
        docs_html = "".join(
            "<h3>%s</h3><pre>%s</pre>" % (_esc(path), _esc(text))
            for path, text in sorted(documents.items())
        )
    sections = [
        ("Documents", docs_html),
        ("Requirements", _render_value(_get(verification, "requirement_results"))),
        ("Acceptance criteria", _render_criteria(_get(verification, "criteria"))),
        ("Provenance", _render_value(_get(node, "provenance"))),
        ("Size", _size_badge(_get(node, "size_status"))),
        (
            "Exemptions",
            "<p>sealed: %s</p><p>pinned overrides: %s</p>"
            % (_render_value(_get(node, "sealed")), _render_value(_get(node, "pinned_overrides"))),
        ),
        ("Owners", _render_value(_get(node, "owners"))),
    ]
    return "".join("<h2>%s</h2>%s" % (_esc(t), b) for t, b in sections)


def render_docs_site(graph, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    nodes_dir = out_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    nodes = _get(graph, "nodes") or {}
    edges = _get(graph, "edges") or []
    aggregates = _get(graph, "aggregates")
    ordered = sorted(nodes.items(), key=lambda kv: str(kv[0]))

    node_items = "".join(
        '<li class="node" data-id="%s" data-type="%s"><a href="nodes/%s">%s</a> (%s)</li>'
        % (
            _esc(node_id),
            _esc(_get(node, "type")),
            _esc(quote(_node_file(node_id))),
            _esc(node_id),
            _esc(_get(node, "type")),
        )
        for node_id, node in ordered
    )
    edge_items = "".join(
        '<li class="edge" data-from="%s" data-to="%s" data-kind="%s">%s &rarr; %s (%s)</li>'
        % (
            _esc(_get(e, "from")),
            _esc(_get(e, "to")),
            _esc(_get(e, "kind")),
            _esc(_get(e, "from")),
            _esc(_get(e, "to")),
            _esc(_get(e, "kind")),
        )
        for e in edges
    )
    index_body = (
        '<input id="search" type="search" placeholder="Search nodes">'
        '<svg id="dag"></svg>'
        '<h2>Nodes</h2><ul id="nodes">%s</ul>'
        '<h2>Edges</h2><ul id="edges">%s</ul>'
        "<script>%s</script>"
    ) % (node_items, edge_items, _DAG_SCRIPT)
    (out_dir / "index.html").write_text(_page("Corpus graph", index_body, ""), encoding="utf-8")

    for node_id, node in ordered:
        node_type = _get(node, "type")
        body = "<p>type: %s</p>" % _esc(node_type)
        if node_type == "component":
            body += _component_body(node)
        (nodes_dir / _node_file(node_id)).write_text(
            _page(str(node_id), body, "../"), encoding="utf-8"
        )

    size_rows = "".join(
        '<tr><td><a href="nodes/%s">%s</a></td><td>%s</td></tr>'
        % (_esc(quote(_node_file(node_id))), _esc(node_id), _size_badge(_get(node, "size_status")))
        for node_id, node in ordered
        if _get(node, "type") == "component"
    )
    dashboard_body = (
        "<h2>Aggregates</h2>%s"
        "<h2>Size caps</h2><table><tr><th>component</th><th>size</th></tr>%s</table>"
    ) % (_render_value(aggregates), size_rows)
    (out_dir / "dashboard.html").write_text(
        _page("Corpus health", dashboard_body, ""), encoding="utf-8"
    )
