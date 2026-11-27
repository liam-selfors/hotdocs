"""Docs site renderer: renders a CorpusGraph into a static explorer site."""

from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import quote

__all__ = ["render_docs_site", "main"]

_STYLE = (
    "<style>\n"
    ".hidden { display: none; }\n"
    ".absent { color: #757575; font-style: italic; }\n"
    ".size-ok { color: #2e7d32; font-weight: bold; }\n"
    ".size-over { color: #c62828; font-weight: bold; }\n"
    ".size-unknown { color: #757575; font-weight: bold; }\n"
    "</style>\n"
)

_ABSENT = '<span class="absent">absent</span>'


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _is_absent(value) -> bool:
    return value is None or (isinstance(value, (str, list, dict)) and len(value) == 0)


def _value(value) -> str:
    if _is_absent(value):
        return _ABSENT
    if isinstance(value, dict):
        rows = "".join(
            f"<dt>{_esc(key)}</dt><dd>{_value(value[key])}</dd>"
            for key in sorted(value, key=str)
        )
        return f"<dl>{rows}</dl>"
    if isinstance(value, list):
        return "<ul>" + "".join(f"<li>{_value(item)}</li>" for item in value) + "</ul>"
    if isinstance(value, str):
        return _esc(value)
    return _esc(json.dumps(value))


def _page(title: str, body: str, script: str = "") -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n"
        f"{_STYLE}</head>\n<body>\n{body}{script}</body>\n</html>\n"
    )


def _node_href(node_id: str) -> str:
    return "nodes/" + quote(str(node_id), safe="") + ".html"


def _documents_section(documents) -> str:
    if _is_absent(documents):
        return _ABSENT
    parts = []
    for key in sorted(documents, key=str):
        parts.append(
            f'<section class="document"><h3>{_esc(key)}</h3>'
            f"<pre>{_esc(documents[key])}</pre></section>\n"
        )
    return "".join(parts)


def _criteria_section(criteria) -> str:
    if _is_absent(criteria):
        return _ABSENT
    if isinstance(criteria, dict):
        pairs = [(key, criteria[key]) for key in criteria]
    else:
        pairs = [(_get(item, "id"), item) for item in criteria]
    groups: dict[str, list] = {}
    for crit_id, item in pairs:
        groups.setdefault(str(_get(item, "kind")), []).append((crit_id, item))
    parts = []
    for kind in sorted(groups):
        parts.append(f'<section class="criteria-kind"><h3>{_esc(kind)}</h3>\n')
        for crit_id, item in groups[kind]:
            parts.append(f"<h4>{_value(crit_id)}</h4>{_value(item)}\n")
        parts.append("</section>\n")
    return "".join(parts)


def _size_section(status) -> str:
    if _is_absent(status):
        return _ABSENT
    return f'<span class="size size-{_esc(status)}">{_esc(status)}</span>'


def _component_body(node) -> str:
    verification = _get(node, "verification")
    requirement_results = _get(verification, "requirement_results") if verification is not None else None
    criteria = _get(verification, "criteria") if verification is not None else None
    return (
        f'<h2>Documents</h2>\n<div id="documents">{_documents_section(_get(node, "documents"))}</div>\n'
        f'<h2>Requirements</h2>\n<div id="requirements">{_value(requirement_results)}</div>\n'
        f'<h2>Acceptance criteria</h2>\n<div id="criteria">{_criteria_section(criteria)}</div>\n'
        f'<h2>Provenance</h2>\n<div id="provenance">{_value(_get(node, "provenance"))}</div>\n'
        f'<h2>Size</h2>\n<div id="size">{_size_section(_get(node, "size_status"))}</div>\n'
        f'<h2>Exemptions</h2>\n<div id="exemptions"><dl>'
        f'<dt>sealed</dt><dd id="sealed">{_value(_get(node, "sealed"))}</dd>'
        f'<dt>pinned_overrides</dt><dd id="pinned-overrides">{_value(_get(node, "pinned_overrides"))}</dd>'
        f"</dl></div>\n"
        f'<h2>Owners</h2>\n<div id="owners">{_value(_get(node, "owners"))}</div>\n'
    )


def _detail_page(node_id, node) -> str:
    node_type = _get(node, "type")
    body = (
        '<p><a href="../index.html">Graph</a> | <a href="../dashboard.html">Dashboard</a></p>\n'
        f"<h1>{_esc(node_id)}</h1>\n"
        f'<p>type: <span id="type">{_value(node_type)}</span></p>\n'
    )
    if node_type == "component":
        body += _component_body(node)
    return _page(str(node_id), body)


def _dashboard_page(nodes, aggregates) -> str:
    sizes: dict[str, int] = {}
    for node_id in sorted(nodes, key=str):
        node = nodes[node_id]
        if _get(node, "type") == "component":
            key = str(_get(node, "size_status"))
            sizes[key] = sizes.get(key, 0) + 1
    body = (
        '<p><a href="index.html">Graph</a></p>\n'
        "<h1>Corpus health</h1>\n"
        f'<h2>Aggregates</h2>\n<div id="aggregates">{_value(aggregates)}</div>\n'
        f'<h2>Size-cap distribution</h2>\n<div id="size-distribution">{_value(sizes)}</div>\n'
    )
    return _page("Corpus health", body)


def _index_page(nodes, edges, asset: str) -> str:
    node_items = []
    for node_id in sorted(nodes, key=str):
        node_type = _get(nodes[node_id], "type")
        node_items.append(
            f'<li class="node" data-id="{_esc(node_id)}" data-type="{_esc(node_type)}">'
            f'<a href="{_esc(_node_href(node_id))}">{_esc(node_id)}</a></li>\n'
        )
    edge_items = []
    for edge in edges:
        edge_items.append(
            f'<li class="edge" data-from="{_esc(_get(edge, "from"))}" '
            f'data-to="{_esc(_get(edge, "to"))}" data-kind="{_esc(_get(edge, "kind"))}">'
            f'{_esc(_get(edge, "from"))} {_esc(_get(edge, "kind"))} {_esc(_get(edge, "to"))}</li>\n'
        )
    body = (
        '<p><a href="dashboard.html">Dashboard</a></p>\n'
        "<h1>Corpus graph</h1>\n"
        '<input id="search" type="search">\n'
        '<svg id="dag"></svg>\n'
        '<ul id="nodes">\n' + "".join(node_items) + "</ul>\n"
        '<ul id="edges">\n' + "".join(edge_items) + "</ul>\n"
    )
    script = '<script type="module">' + asset + "\ninit(document);\n" + "</script>\n"
    return _page("Corpus graph", body, script)


def render_docs_site(graph, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    nodes = _get(graph, "nodes") or {}
    edges = _get(graph, "edges") or []
    aggregates = _get(graph, "aggregates")
    asset = (Path(__file__).parent.parent / "static" / "app.js").read_text(encoding="utf-8")

    nodes_dir = out_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(_index_page(nodes, edges, asset), encoding="utf-8")
    (out_dir / "dashboard.html").write_text(_dashboard_page(nodes, aggregates), encoding="utf-8")
    for node_id in sorted(nodes, key=str):
        (nodes_dir / (str(node_id) + ".html")).write_text(
            _detail_page(node_id, nodes[node_id]), encoding="utf-8"
        )


from .cli import main  # noqa: E402
