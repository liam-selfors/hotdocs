"""Docs Site Renderer: renders corpus-graph.json into a static explorer site."""

from __future__ import annotations

import html
import json
from pathlib import Path

__all__ = ["render_docs_site", "main"]

_STYLE = (
    "body{font-family:sans-serif;margin:1.5em}"
    ".hidden{display:none}"
    ".absent{color:#888;font-style:italic}"
    ".size-ok{background:#c8e6c9}"
    ".size-over{background:#ffcdd2}"
    ".size-unknown{background:#e0e0e0}"
    "table{border-collapse:collapse}"
    "td,th{border:1px solid #ccc;padding:2px 6px;text-align:left}"
    "pre{background:#f5f5f5;padding:0.5em;white-space:pre-wrap}"
)

_ABSENT = '<span class="absent">absent</span>'


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, (str, list, dict)) and not value)


def _value_html(value) -> str:
    if _is_empty(value):
        return _ABSENT
    if isinstance(value, str):
        return _esc(value)
    return _esc(json.dumps(value, sort_keys=True))


def _table(rows) -> str:
    cells = "".join(
        f"<tr><th>{_esc(key)}</th><td>{_value_html(value)}</td></tr>" for key, value in rows
    )
    return f"<table>{cells}</table>"


def _mapping_html(mapping) -> str:
    if _is_empty(mapping):
        return _ABSENT
    return _table(sorted(mapping.items()))


def _list_html(items) -> str:
    if _is_empty(items):
        return _ABSENT
    return "<ul>" + "".join(f"<li>{_value_html(item)}</li>" for item in items) + "</ul>"


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{_esc(title)}</title>\n<style>{_STYLE}</style>\n</head>\n<body>\n"
        f"{body}\n</body>\n</html>\n"
    )


def _documents_html(documents) -> str:
    if _is_empty(documents):
        return _ABSENT
    return "".join(
        f"<h3>{_esc(path)}</h3><pre>{_esc(text)}</pre>" for path, text in sorted(documents.items())
    )


def _criteria_html(criteria) -> str:
    if _is_empty(criteria):
        return _ABSENT
    if isinstance(criteria, dict):
        entries = [dict(entry, id=cid) for cid, entry in sorted(criteria.items())]
    else:
        entries = list(criteria)
    by_kind: dict = {}
    for entry in entries:
        by_kind.setdefault(str(entry.get("kind")), []).append(entry)
    parts = []
    for kind in sorted(by_kind):
        rows = [(entry.get("id"), entry.get("result")) for entry in by_kind[kind]]
        parts.append(f"<h3>{_esc(kind)}</h3>{_table(rows)}")
    return "".join(parts)


def _component_body(node) -> str:
    verification = node.get("verification") or {}
    size = node.get("size_status")
    return (
        f"<h2>Documents</h2>{_documents_html(node.get('documents'))}"
        f"<h2>Requirements</h2>{_mapping_html(verification.get('requirement_results'))}"
        f"<h2>Acceptance criteria</h2>{_criteria_html(verification.get('criteria'))}"
        f"<h2>Provenance</h2>{_mapping_html(node.get('provenance'))}"
        f'<h2>Size</h2><span class="size size-{_esc(size)}">{_value_html(size)}</span>'
        f"<h2>Exemptions</h2>"
        f"<p>sealed: {_value_html(node.get('sealed'))}</p>"
        f"<p>pinned overrides:</p>{_list_html(node.get('pinned_overrides'))}"
        f"<h2>Owners</h2>{_list_html(node.get('owners'))}"
    )


def _detail_page(node_id, node) -> str:
    node_type = node.get("type")
    body = (
        '<p><a href="../index.html">graph</a> | <a href="../dashboard.html">dashboard</a></p>'
        f"<h1>{_esc(node_id)}</h1><p>type: {_value_html(node_type)}</p>"
    )
    if node_type == "component":
        body += _component_body(node)
    return _page(node_id, body)


def _dashboard_page(nodes, aggregates) -> str:
    sizes: dict = {}
    for node_id in sorted(nodes):
        node = nodes[node_id]
        if node.get("type") == "component":
            status = str(node.get("size_status"))
            sizes[status] = sizes.get(status, 0) + 1
    body = (
        '<p><a href="index.html">graph</a></p><h1>Corpus health</h1>'
        f"<h2>Aggregates</h2>{_mapping_html(aggregates)}"
        f"<h2>Size-cap distribution</h2>{_mapping_html(sizes)}"
    )
    return _page("Corpus health", body)


def _index_page(nodes, edges, script: str) -> str:
    node_items = "".join(
        f'<li class="node" data-id="{_esc(node_id)}" data-type="{_esc(nodes[node_id].get("type"))}">'
        f'<a href="nodes/{_esc(node_id)}.html">{_esc(node_id)}</a></li>'
        for node_id in sorted(nodes)
    )
    edge_items = "".join(
        f'<li class="edge" data-from="{_esc(_get(edge, "from"))}" data-to="{_esc(_get(edge, "to"))}"'
        f' data-kind="{_esc(_get(edge, "kind"))}">'
        f'{_esc(_get(edge, "from"))} -&gt; {_esc(_get(edge, "to"))} ({_esc(_get(edge, "kind"))})</li>'
        for edge in edges
    )
    body = (
        '<p><a href="dashboard.html">dashboard</a></p>'
        '<input id="search" type="search">\n'
        '<svg id="dag"></svg>\n'
        f'<ul id="nodes">{node_items}</ul>\n'
        f'<ul id="edges">{edge_items}</ul>\n'
        f'<script type="module">{script}\ninit(document);\n</script>'
    )
    return _page("Corpus graph", body)


def render_docs_site(graph, out_dir: Path) -> None:
    nodes = _get(graph, "nodes")
    edges = _get(graph, "edges")
    aggregates = _get(graph, "aggregates")
    script = (Path(__file__).parent.parent / "static" / "app.js").read_text(encoding="utf-8")
    out_dir = Path(out_dir)
    (out_dir / "nodes").mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(_index_page(nodes, edges, script), encoding="utf-8")
    (out_dir / "dashboard.html").write_text(_dashboard_page(nodes, aggregates), encoding="utf-8")
    for node_id in sorted(nodes):
        (out_dir / "nodes" / f"{node_id}.html").write_text(
            _detail_page(node_id, nodes[node_id]), encoding="utf-8"
        )


from .cli import main  # noqa: E402
