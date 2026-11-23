"""Docs site renderer: renders corpus-graph.json into a static explorer site."""

from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import quote

ASSET_PATH = Path(__file__).parent.parent / "static" / "app.js"

_SIZE_COLORS = {"ok": "#2e7d32", "over": "#c62828"}
_UNKNOWN_SIZE_COLOR = "#757575"

_STYLE = (
    "<style>.hidden{display:none}"
    ".absent{color:#757575;font-style:italic}"
    "pre{white-space:pre-wrap}</style>"
)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _is_absent(value) -> bool:
    return value is None or (isinstance(value, (str, list, tuple, dict)) and len(value) == 0)


def _value(value) -> str:
    if _is_absent(value):
        return '<span class="absent">absent</span>'
    if isinstance(value, dict):
        rows = "".join(
            f"<dt>{_esc(k)}</dt><dd>{_value(v)}</dd>" for k, v in value.items()
        )
        return f"<dl>{rows}</dl>"
    if isinstance(value, (list, tuple)):
        items = "".join(f"<li>{_value(v)}</li>" for v in value)
        return f"<ul>{items}</ul>"
    return _esc(value)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{_esc(title)}</title>\n{_STYLE}\n</head>\n<body>\n"
        f"{body}\n</body>\n</html>\n"
    )


def _href(node_id: str) -> str:
    return quote(str(node_id), safe="") + ".html"


def _criteria_by_kind(criteria) -> str:
    if _is_absent(criteria):
        return _value(criteria)
    if isinstance(criteria, dict):
        items = list(criteria.items())
    else:
        items = [(_get(c, "id"), c) for c in criteria]
    groups: dict[str, list] = {}
    for cid, crit in items:
        groups.setdefault(str(_get(crit, "kind")), []).append((cid, crit))
    parts = []
    for kind in sorted(groups):
        lis = "".join(
            f'<li class="criterion"><strong>{_esc(cid)}</strong>: {_value(crit)}</li>'
            for cid, crit in groups[kind]
        )
        parts.append(f'<h3 class="kind">{_esc(kind)}</h3><ul>{lis}</ul>')
    return "".join(parts)


def _component_body(node_id: str, node) -> str:
    documents = _get(node, "documents")
    if _is_absent(documents):
        docs_html = _value(documents)
    else:
        docs_html = "".join(
            f'<section class="document"><h3>{_esc(name)}</h3><pre>{_esc(text)}</pre></section>'
            for name, text in documents.items()
        )
    verification = _get(node, "verification")
    size_status = _get(node, "size_status")
    color = _SIZE_COLORS.get(size_status, _UNKNOWN_SIZE_COLOR)
    return (
        f"<p><a href=\"../index.html\">Graph</a></p>\n"
        f"<h1>{_esc(node_id)}</h1>\n"
        f"<p>Type: {_esc(_get(node, 'type'))}</p>\n"
        f"<h2>Documents</h2>\n{docs_html}\n"
        f"<h2>Requirements</h2>\n{_value(_get(verification, 'requirement_results'))}\n"
        f"<h2>Acceptance criteria</h2>\n{_criteria_by_kind(_get(verification, 'criteria'))}\n"
        f"<h2>Provenance</h2>\n{_value(_get(node, 'provenance'))}\n"
        f"<h2>Size</h2>\n<p class=\"size size-{_esc(size_status)}\" "
        f"style=\"color:{color}\">{_value(size_status)}</p>\n"
        f"<h2>Exemptions</h2>\n<p>Sealed: {_value(_get(node, 'sealed'))}</p>\n"
        f"<p>Pinned overrides:</p>{_value(_get(node, 'pinned_overrides'))}\n"
        f"<h2>Owners</h2>\n{_value(_get(node, 'owners'))}"
    )


def _plain_body(node_id: str, node) -> str:
    return (
        f"<p><a href=\"../index.html\">Graph</a></p>\n"
        f"<h1>{_esc(node_id)}</h1>\n"
        f"<p>Type: {_esc(_get(node, 'type'))}</p>"
    )


def _index_body(node_ids: list, nodes, edges, script: str) -> str:
    node_items = "".join(
        f'<li class="node" data-id="{_esc(nid)}" data-type="{_esc(_get(nodes[nid], "type"))}">'
        f'<a href="nodes/{_esc(_href(nid))}">{_esc(nid)}</a></li>\n'
        for nid in node_ids
    )
    edge_items = "".join(
        f'<li class="edge" data-from="{_esc(_get(e, "from"))}" data-to="{_esc(_get(e, "to"))}" '
        f'data-kind="{_esc(_get(e, "kind"))}">{_esc(_get(e, "from"))} &rarr; '
        f'{_esc(_get(e, "to"))} ({_esc(_get(e, "kind"))})</li>\n'
        for e in edges
    )
    return (
        "<h1>Corpus graph</h1>\n"
        "<p><a href=\"dashboard.html\">Corpus health dashboard</a></p>\n"
        "<input id=\"search\" type=\"search\">\n"
        "<svg id=\"dag\"></svg>\n"
        f"<ul id=\"nodes\">\n{node_items}</ul>\n"
        f"<ul id=\"edges\">\n{edge_items}</ul>\n"
        f"<script type=\"module\">{script}\ninit(document);\n</script>"
    )


def _dashboard_body(node_ids: list, nodes, aggregates) -> str:
    sizes: dict[str, int] = {}
    for nid in node_ids:
        node = nodes[nid]
        if _get(node, "type") == "component":
            key = str(_get(node, "size_status"))
            sizes[key] = sizes.get(key, 0) + 1
    size_rows = "".join(
        f'<li class="size size-{_esc(k)}" style="color:{_SIZE_COLORS.get(k, _UNKNOWN_SIZE_COLOR)}">'
        f"{_esc(k)}: {_esc(v)}</li>"
        for k, v in sorted(sizes.items())
    )
    return (
        "<p><a href=\"index.html\">Graph</a></p>\n"
        "<h1>Corpus health</h1>\n"
        f"<h2>Aggregates</h2>\n{_value(aggregates)}\n"
        f"<h2>Size-cap distribution</h2>\n<ul id=\"size-distribution\">{size_rows}</ul>"
    )


def render_docs_site(graph, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    nodes = _get(graph, "nodes") or {}
    edges = _get(graph, "edges") or []
    aggregates = _get(graph, "aggregates")
    node_ids = sorted(nodes)
    script = ASSET_PATH.read_text(encoding="utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        _page("Corpus graph", _index_body(node_ids, nodes, edges, script)), encoding="utf-8"
    )
    (out_dir / "dashboard.html").write_text(
        _page("Corpus health", _dashboard_body(node_ids, nodes, aggregates)), encoding="utf-8"
    )
    detail_dir = out_dir / "nodes"
    detail_dir.mkdir(parents=True, exist_ok=True)
    for nid in node_ids:
        node = nodes[nid]
        if _get(node, "type") == "component":
            body = _component_body(nid, node)
        else:
            body = _plain_body(nid, node)
        (detail_dir / _href(nid)).write_text(_page(str(nid), body), encoding="utf-8")


from .cli import main  # noqa: E402

__all__ = ["render_docs_site", "main"]
