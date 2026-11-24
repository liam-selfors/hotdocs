"""Docs Site Renderer: renders corpus-graph.json into a static docs explorer."""

import html
import json
from pathlib import Path

_SIZE_COLORS = {"ok": "#2e7d32", "over": "#c62828"}
_ABSENT = "<em>absent</em>"


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _esc(value):
    return html.escape(str(value), quote=True)


def _page(title, body):
    return (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>" + _esc(title) + "</title>\n"
        "<style>.hidden{display:none}</style>\n"
        "</head>\n<body>\n" + body + "</body>\n</html>\n"
    )


def _value(value):
    if value is None or value == "" or value == [] or value == {}:
        return _ABSENT
    if isinstance(value, dict):
        rows = "".join(
            "<tr><th>" + _esc(key) + "</th><td>" + _value(item) + "</td></tr>"
            for key, item in value.items()
        )
        return "<table>" + rows + "</table>"
    if isinstance(value, list):
        return "<ul>" + "".join("<li>" + _value(item) + "</li>" for item in value) + "</ul>"
    if isinstance(value, str):
        return _esc(value)
    return _esc(json.dumps(value))


def _criteria_by_kind(criteria):
    if not criteria:
        return _ABSENT
    if isinstance(criteria, dict):
        entries = [(item, {cid: item}) for cid, item in criteria.items()]
    else:
        entries = [(item, item) for item in criteria]
    groups = {}
    for item, shown in entries:
        groups.setdefault(str(_get(item, "kind")), []).append(shown)
    return "".join(
        "<h3>" + _esc(kind) + "</h3>\n" + _value(groups[kind]) + "\n"
        for kind in sorted(groups)
    )


def _documents(documents):
    body = "".join(
        "<h3>" + _esc(path) + "</h3>\n<pre>" + _esc(documents[path]) + "</pre>\n"
        for path in sorted(documents or {})
    )
    return body or _ABSENT


def _component_body(node):
    verification = _get(node, "verification")
    status = _get(node, "size_status")
    color = _SIZE_COLORS.get(status, "#757575")
    return (
        "<h2>Documents</h2>\n" + _documents(_get(node, "documents")) + "\n"
        "<h2>Requirements</h2>\n" + _value(_get(verification, "requirement_results")) + "\n"
        "<h2>Acceptance criteria</h2>\n" + _criteria_by_kind(_get(verification, "criteria")) + "\n"
        "<h2>Provenance</h2>\n" + _value(_get(node, "provenance")) + "\n"
        "<h2>Size</h2>\n<p class=\"size\"><span style=\"color:" + color + "\">"
        + _value(status) + "</span></p>\n"
        "<h2>Exemptions</h2>\n<p>Sealed: " + _value(_get(node, "sealed")) + "</p>\n"
        "<p>Pinned overrides: " + _value(_get(node, "pinned_overrides")) + "</p>\n"
        "<h2>Owners</h2>\n" + _value(_get(node, "owners")) + "\n"
    )


def _detail_page(node_id, node):
    node_type = _get(node, "type")
    body = (
        "<p><a href=\"../index.html\">Graph</a> | <a href=\"../dashboard.html\">Dashboard</a></p>\n"
        "<h1>" + _esc(node_id) + "</h1>\n"
        "<p>Type: " + _value(node_type) + "</p>\n"
    )
    if node_type == "component":
        body += _component_body(node)
    return _page(node_id, body)


def _dashboard_page(nodes, aggregates):
    type_counts = {}
    size_counts = {}
    for node in nodes.values():
        node_type = str(_get(node, "type"))
        type_counts[node_type] = type_counts.get(node_type, 0) + 1
        if node_type == "component":
            status = str(_get(node, "size_status"))
            size_counts[status] = size_counts.get(status, 0) + 1
    body = (
        "<p><a href=\"index.html\">Graph</a></p>\n"
        "<h1>Corpus health</h1>\n"
        "<h2>Aggregates</h2>\n" + _value(aggregates) + "\n"
        "<h2>Nodes by type</h2>\n" + _value({k: type_counts[k] for k in sorted(type_counts)}) + "\n"
        "<h2>Size-cap distribution</h2>\n" + _value({k: size_counts[k] for k in sorted(size_counts)}) + "\n"
    )
    return _page("Corpus health", body)


def _index_page(nodes, edges, script):
    node_items = "".join(
        "<li class=\"node\" data-id=\"" + _esc(node_id) + "\" data-type=\""
        + _esc(_get(nodes[node_id], "type")) + "\"><a href=\"nodes/" + _esc(node_id)
        + ".html\">" + _esc(node_id) + "</a></li>\n"
        for node_id in sorted(nodes)
    )
    edge_items = "".join(
        "<li class=\"edge\" data-from=\"" + _esc(_get(edge, "from")) + "\" data-to=\""
        + _esc(_get(edge, "to")) + "\" data-kind=\"" + _esc(_get(edge, "kind")) + "\">"
        + _esc(_get(edge, "from")) + " " + _esc(_get(edge, "kind")) + " "
        + _esc(_get(edge, "to")) + "</li>\n"
        for edge in edges
    )
    body = (
        "<p><a href=\"dashboard.html\">Dashboard</a></p>\n"
        "<input id=\"search\" type=\"search\">\n"
        "<svg id=\"dag\"></svg>\n"
        "<ul id=\"nodes\">\n" + node_items + "</ul>\n"
        "<ul id=\"edges\">\n" + edge_items + "</ul>\n"
        "<script type=\"module\">" + script + "\ninit(document);\n</script>\n"
    )
    return _page("Corpus graph", body)


def render_docs_site(graph, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    nodes = _get(graph, "nodes")
    edges = _get(graph, "edges")
    aggregates = _get(graph, "aggregates")
    script = (Path(__file__).parent.parent / "static" / "app.js").read_text(encoding="utf-8")
    (out_dir / "nodes").mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(_index_page(nodes, edges, script), encoding="utf-8")
    (out_dir / "dashboard.html").write_text(_dashboard_page(nodes, aggregates), encoding="utf-8")
    for node_id, node in nodes.items():
        (out_dir / "nodes" / (node_id + ".html")).write_text(
            _detail_page(node_id, node), encoding="utf-8"
        )


from .cli import main  # noqa: E402

__all__ = ["render_docs_site", "main"]
