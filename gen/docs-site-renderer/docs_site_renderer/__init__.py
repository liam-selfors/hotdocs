"""Docs Site Renderer: renders corpus-graph.json into a static explorer site."""

import html
import json
from collections import Counter
from pathlib import Path

ASSET_PATH = Path(__file__).parent.parent / "static" / "app.js"

_SIZE_STYLE = (
    "<style>.size-ok{color:#2e7d32}.size-over{color:#c62828}"
    ".size-unknown{color:#757575}</style>\n"
)
_INDEX_STYLE = "<style>.hidden{display:none}</style>\n"


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _fmt(value) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return "absent"
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _page(title: str, body: str, head_extra: str = "") -> str:
    return (
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{_e(title)}</title>\n{head_extra}</head>\n<body>\n"
        f"{body}</body>\n</html>\n"
    )


def _node_href(node_id: str) -> str:
    return f"nodes/{node_id}.html"


def _render_index(nodes, edges, script: str) -> str:
    parts = [
        "<h1>Corpus graph</h1>\n",
        '<p><a href="dashboard.html">Corpus health</a></p>\n',
        '<input id="search" type="search">\n',
        '<svg id="dag"></svg>\n',
        '<ul id="nodes">\n',
    ]
    for node_id in sorted(nodes):
        node_type = _get(nodes[node_id], "type")
        parts.append(
            f'<li class="node" data-id="{_e(node_id)}" data-type="{_e(node_type)}">'
            f'<a href="{_e(_node_href(node_id))}">{_e(node_id)}</a></li>\n'
        )
    parts.append("</ul>\n")
    parts.append('<ul id="edges">\n')
    for edge in edges:
        src = _get(edge, "from")
        dst = _get(edge, "to")
        kind = _get(edge, "kind")
        parts.append(
            f'<li class="edge" data-from="{_e(src)}" data-to="{_e(dst)}" '
            f'data-kind="{_e(kind)}">{_e(src)} &rarr; {_e(dst)} ({_e(kind)})</li>\n'
        )
    parts.append("</ul>\n")
    parts.append(
        '<script type="module">' + script + "\ninit(document);\n" + "</script>\n"
    )
    return _page("Corpus graph", "".join(parts), _INDEX_STYLE)


def _list_or_absent(items: list, list_id: str) -> str:
    if not items:
        return '<p class="absent">absent</p>\n'
    return f'<ul id="{list_id}">\n' + "".join(items) + "</ul>\n"


def _criteria_entries(criteria):
    if isinstance(criteria, dict):
        return [(cid, criteria[cid]) for cid in sorted(criteria)]
    return [(_get(entry, "id"), entry) for entry in criteria]


def _render_component(node_id: str, node) -> str:
    parts = [f"<h1>{_e(node_id)}</h1>\n", "<p>Type: component</p>\n"]

    parts.append("<h2>Documents</h2>\n")
    documents = _get(node, "documents")
    if documents:
        for path in sorted(documents):
            parts.append(
                f'<section class="document"><h3>{_e(path)}</h3>'
                f"<pre>{_e(documents[path])}</pre></section>\n"
            )
    else:
        parts.append('<p class="absent">absent</p>\n')

    verification = _get(node, "verification")
    requirement_results = _get(verification, "requirement_results") if verification else None
    criteria = _get(verification, "criteria") if verification else None

    parts.append("<h2>Requirements</h2>\n")
    req_items = []
    if requirement_results:
        for rid in sorted(requirement_results):
            req_items.append(
                f'<li class="requirement">{_e(rid)}: '
                f"{_e(_fmt(requirement_results[rid]))}</li>\n"
            )
    parts.append(_list_or_absent(req_items, "requirements"))

    parts.append("<h2>Acceptance criteria</h2>\n")
    if criteria:
        by_kind: dict = {}
        for cid, entry in _criteria_entries(criteria):
            kind = _fmt(_get(entry, "kind"))
            by_kind.setdefault(kind, []).append(
                f'<li class="criterion">{_e(cid)}: '
                f"{_e(_fmt(_get(entry, 'result')))}</li>\n"
            )
        for kind in sorted(by_kind):
            parts.append(f'<h3>{_e(kind)}</h3>\n<ul class="criteria">\n')
            parts.extend(by_kind[kind])
            parts.append("</ul>\n")
    else:
        parts.append('<p class="absent">absent</p>\n')

    parts.append("<h2>Provenance</h2>\n")
    provenance = _get(node, "provenance")
    if provenance:
        parts.append('<dl id="provenance">\n')
        for key in sorted(provenance):
            parts.append(
                f"<dt>{_e(key)}</dt><dd>{_e(_fmt(provenance[key]))}</dd>\n"
            )
        parts.append("</dl>\n")
    else:
        parts.append('<p class="absent">absent</p>\n')

    size = _fmt(_get(node, "size_status"))
    parts.append("<h2>Size</h2>\n")
    parts.append(f'<p class="size size-{_e(size)}">{_e(size)}</p>\n')

    parts.append("<h2>Exemptions</h2>\n")
    parts.append(f'<p class="sealed">Sealed: {_e(_fmt(_get(node, "sealed")))}</p>\n')
    override_items = [
        f'<li class="override">{_e(_fmt(item))}</li>\n'
        for item in (_get(node, "pinned_overrides") or [])
    ]
    parts.append("<h3>Pinned overrides</h3>\n")
    parts.append(_list_or_absent(override_items, "pinned-overrides"))

    parts.append("<h2>Owners</h2>\n")
    owner_items = [
        f'<li class="owner">{_e(_fmt(owner))}</li>\n'
        for owner in (_get(node, "owners") or [])
    ]
    parts.append(_list_or_absent(owner_items, "owners"))

    parts.append('<p><a href="../index.html">Back to graph</a></p>\n')
    return _page(node_id, "".join(parts), _SIZE_STYLE)


def _render_other(node_id: str, node) -> str:
    body = (
        f"<h1>{_e(node_id)}</h1>\n"
        f"<p>Type: {_e(_fmt(_get(node, 'type')))}</p>\n"
        '<p><a href="../index.html">Back to graph</a></p>\n'
    )
    return _page(node_id, body)


def _render_dashboard(nodes, aggregates) -> str:
    parts = ["<h1>Corpus health</h1>\n", "<h2>Aggregates</h2>\n"]
    if aggregates:
        parts.append('<dl id="aggregates">\n')
        for key in sorted(aggregates):
            parts.append(
                f"<dt>{_e(key)}</dt><dd>{_e(_fmt(aggregates[key]))}</dd>\n"
            )
        parts.append("</dl>\n")
    else:
        parts.append('<p class="absent">absent</p>\n')

    sizes = Counter(
        _fmt(_get(nodes[node_id], "size_status"))
        for node_id in nodes
        if _get(nodes[node_id], "type") == "component"
    )
    parts.append("<h2>Size-cap distribution</h2>\n")
    size_items = [
        f'<li class="size size-{_e(status)}">{_e(status)}: {sizes[status]}</li>\n'
        for status in sorted(sizes)
    ]
    parts.append(_list_or_absent(size_items, "size-distribution"))
    parts.append('<p><a href="index.html">Back to graph</a></p>\n')
    return _page("Corpus health", "".join(parts), _SIZE_STYLE)


def render_docs_site(graph, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    nodes = _get(graph, "nodes")
    edges = _get(graph, "edges")
    aggregates = _get(graph, "aggregates")
    script = ASSET_PATH.read_text(encoding="utf-8")

    nodes_dir = out_dir / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "index.html").write_text(
        _render_index(nodes, edges, script), encoding="utf-8"
    )
    (out_dir / "dashboard.html").write_text(
        _render_dashboard(nodes, aggregates), encoding="utf-8"
    )
    for node_id in nodes:
        node = nodes[node_id]
        if _get(node, "type") == "component":
            text = _render_component(node_id, node)
        else:
            text = _render_other(node_id, node)
        (nodes_dir / f"{node_id}.html").write_text(text, encoding="utf-8")


from .cli import main  # noqa: E402

__all__ = ["render_docs_site", "main"]
