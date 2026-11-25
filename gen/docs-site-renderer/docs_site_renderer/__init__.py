"""Docs Site Renderer: renders a CorpusGraph into the static docs explorer.

A pure presentation layer over ``verification/corpus-graph.json``: the DAG
view (laid out and filtered in the browser by the asset ``static/app.js``),
one detail page per node, and the corpus-health dashboard.
"""
from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

__all__ = ["render_docs_site", "main"]

_SIZE_COLORS = {"ok": "#2e7d32", "over": "#c62828"}
_UNKNOWN_SIZE_COLOR = "#757575"

_STYLE = (
    "body{font-family:sans-serif;margin:1.5em;}"
    ".hidden{display:none;}"
    ".absent{color:#757575;font-style:italic;}"
    "pre{background:#f5f5f5;padding:0.75em;white-space:pre-wrap;}"
)


def _get(obj, key):
    """Read ``key`` from a dict or as an attribute of an object."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _absent(value) -> bool:
    return value is None or (isinstance(value, (str, list, dict)) and len(value) == 0)


_ABSENT_HTML = '<span class="absent">absent</span>'


def _render_value(value) -> str:
    if _absent(value):
        return _ABSENT_HTML
    if isinstance(value, dict):
        items = "".join(
            f"<dt>{_esc(k)}</dt><dd>{_render_value(v)}</dd>" for k, v in value.items()
        )
        return f"<dl>{items}</dl>"
    if isinstance(value, list):
        items = "".join(f"<li>{_render_value(v)}</li>" for v in value)
        return f"<ul>{items}</ul>"
    if isinstance(value, bool):
        return "true" if value else "false"
    return _esc(value)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>{_STYLE}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}"
        "</body>\n"
        "</html>\n"
    )


def _detail_href(node_id) -> str:
    return "nodes/" + quote(str(node_id), safe="") + ".html"


def _index_html(nodes, edges, asset_text: str) -> str:
    node_items = "".join(
        f'<li class="node" data-id="{_esc(node_id)}" '
        f'data-type="{_esc(_get(nodes[node_id], "type"))}">'
        f'<a href="{_esc(_detail_href(node_id))}">{_esc(node_id)}</a></li>\n'
        for node_id in sorted(nodes)
    )
    edge_items = "".join(
        f'<li class="edge" data-from="{_esc(_get(edge, "from"))}" '
        f'data-to="{_esc(_get(edge, "to"))}" data-kind="{_esc(_get(edge, "kind"))}">'
        f'{_esc(_get(edge, "from"))} {_esc(_get(edge, "kind"))} {_esc(_get(edge, "to"))}'
        "</li>\n"
        for edge in edges
    )
    body = (
        "<h1>Corpus graph</h1>\n"
        '<p><a href="dashboard.html">Corpus health</a></p>\n'
        '<input id="search" type="search">\n'
        '<svg id="dag"></svg>\n'
        f'<ul id="nodes">\n{node_items}</ul>\n'
        f'<ul id="edges">\n{edge_items}</ul>\n'
        '<script type="module">'
        + asset_text
        + "\ninit(document);\n"
        + "</script>\n"
    )
    return _page("Corpus graph", body)


def _documents_html(documents) -> str:
    if _absent(documents):
        return _ABSENT_HTML
    return "".join(
        f'<section class="document"><h3>{_esc(name)}</h3><pre>{_esc(text)}</pre></section>\n'
        for name, text in documents.items()
    )


def _criteria_html(criteria) -> str:
    if _absent(criteria):
        return _ABSENT_HTML
    if isinstance(criteria, dict):
        entries = list(criteria.items())
    else:
        entries = [(None, c) for c in criteria]
    groups: dict[str, list] = {}
    for criterion_id, criterion in entries:
        groups.setdefault(str(_get(criterion, "kind")), []).append((criterion_id, criterion))
    parts = []
    for kind in sorted(groups):
        items = "".join(
            "<li>"
            + (f"<strong>{_esc(cid)}</strong> " if cid is not None else "")
            + _render_value(c)
            + "</li>"
            for cid, c in groups[kind]
        )
        parts.append(
            f'<section class="criteria-kind" data-kind="{_esc(kind)}">'
            f"<h3>{_esc(kind)}</h3><ul>{items}</ul></section>\n"
        )
    return "".join(parts)


def _size_html(status) -> str:
    if _absent(status):
        return _ABSENT_HTML
    color = _SIZE_COLORS.get(status, _UNKNOWN_SIZE_COLOR)
    return (
        f'<span class="size size-{_esc(status)}" style="color:{color}">'
        f"{_esc(status)}</span>"
    )


def _component_body(node) -> str:
    verification = _get(node, "verification")
    return (
        "<h2>Documents</h2>\n"
        f'<div id="documents">{_documents_html(_get(node, "documents"))}</div>\n'
        "<h2>Requirements</h2>\n"
        f'<div id="requirements">{_render_value(_get(verification, "requirement_results"))}</div>\n'
        "<h2>Acceptance criteria</h2>\n"
        f'<div id="criteria">{_criteria_html(_get(verification, "criteria"))}</div>\n'
        "<h2>Provenance</h2>\n"
        f'<div id="provenance">{_render_value(_get(node, "provenance"))}</div>\n'
        "<h2>Size</h2>\n"
        f'<div id="size">{_size_html(_get(node, "size_status"))}</div>\n'
        "<h2>Exemptions</h2>\n"
        f'<div id="exemptions"><p>sealed: {_render_value(_get(node, "sealed"))}</p>'
        f'<p>pinned overrides: {_render_value(_get(node, "pinned_overrides"))}</p></div>\n'
        "<h2>Owners</h2>\n"
        f'<div id="owners">{_render_value(_get(node, "owners"))}</div>\n'
    )


def _detail_html(node_id, node) -> str:
    node_type = _get(node, "type")
    body = (
        '<p><a href="../index.html">Corpus graph</a></p>\n'
        f"<h1>{_esc(node_id)}</h1>\n"
        f'<p class="type">{_esc(node_type)}</p>\n'
    )
    if node_type == "component":
        body += _component_body(node)
    return _page(str(node_id), body)


def _dashboard_html(nodes, aggregates) -> str:
    type_counts: dict[str, int] = {}
    size_counts: dict[str, int] = {}
    for node_id in sorted(nodes):
        node = nodes[node_id]
        node_type = str(_get(node, "type"))
        type_counts[node_type] = type_counts.get(node_type, 0) + 1
        if node_type == "component":
            status = str(_get(node, "size_status"))
            size_counts[status] = size_counts.get(status, 0) + 1
    type_rows = "".join(
        f'<tr data-type="{_esc(t)}"><td>{_esc(t)}</td><td>{n}</td></tr>'
        for t, n in sorted(type_counts.items())
    )
    size_rows = "".join(
        f'<tr data-size="{_esc(s)}"><td>{_size_html(s)}</td><td>{n}</td></tr>'
        for s, n in sorted(size_counts.items())
    )
    body = (
        '<p><a href="index.html">Corpus graph</a></p>\n'
        "<h1>Corpus health</h1>\n"
        "<h2>Aggregates</h2>\n"
        f'<div id="aggregates">{_render_value(aggregates)}</div>\n'
        "<h2>Nodes by type</h2>\n"
        f'<table id="node-types">{type_rows}</table>\n'
        "<h2>Size-cap distribution</h2>\n"
        f'<table id="size-distribution">{size_rows}</table>\n'
    )
    return _page("Corpus health", body)


def render_docs_site(graph, out_dir: Path) -> None:
    """Render ``graph`` (a CorpusGraph or its dict form) into ``out_dir``."""
    out_dir = Path(out_dir)
    nodes = _get(graph, "nodes")
    edges = _get(graph, "edges")
    aggregates = _get(graph, "aggregates")
    asset_text = (Path(__file__).parent.parent / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    nodes_dir = out_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        _index_html(nodes, edges, asset_text), encoding="utf-8"
    )
    (out_dir / "dashboard.html").write_text(
        _dashboard_html(nodes, aggregates), encoding="utf-8"
    )
    for node_id in sorted(nodes):
        (nodes_dir / (quote(str(node_id), safe="") + ".html")).write_text(
            _detail_html(node_id, nodes[node_id]), encoding="utf-8"
        )


from .cli import main  # noqa: E402  (re-export, after render_docs_site exists)
