"""Docs site renderer: renders corpus-graph.json into a static explorer site."""

import html
import json
from pathlib import Path

ASSET_PATH = Path(__file__).parent.parent / "static" / "app.js"

CSS = (
    "body{font-family:sans-serif;margin:1em}"
    ".hidden{display:none}"
    ".absent{color:#888;font-style:italic}"
    ".size-ok{color:#2e7d32}"
    ".size-over{color:#c62828}"
    ".size-unknown{color:#888}"
    "pre{background:#f5f5f5;padding:.5em;white-space:pre-wrap}"
)


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _esc(value):
    return html.escape(str(value), quote=True)


def _absent(value):
    return value is None or value == "" or value == [] or value == {}


ABSENT = '<span class="absent">absent</span>'


def _value(value):
    if _absent(value):
        return ABSENT
    if isinstance(value, dict):
        return "<dl>" + "".join(
            f"<dt>{_esc(k)}</dt><dd>{_value(v)}</dd>" for k, v in value.items()
        ) + "</dl>"
    if isinstance(value, list):
        return "<ul>" + "".join(f"<li>{_value(v)}</li>" for v in value) + "</ul>"
    return _esc(value if isinstance(value, str) else json.dumps(value))


def _page(title, body):
    return (
        "<!DOCTYPE html>\n"
        f'<html><head><meta charset="utf-8"><title>{_esc(title)}</title>'
        f"<style>{CSS}</style></head><body>\n{body}\n</body></html>\n"
    )


def _documents(documents):
    if _absent(documents):
        return ABSENT
    return "".join(
        f"<h3>{_esc(path)}</h3><pre>{_esc(text)}</pre>"
        for path, text in documents.items()
    )


def _criteria(criteria):
    if _absent(criteria):
        return ABSENT
    if isinstance(criteria, dict):
        entries = [({key: item}, item) for key, item in criteria.items()]
    else:
        entries = [(item, item) for item in criteria]
    groups = {}
    for shown, item in entries:
        groups.setdefault(str(_get(item, "kind")), []).append(shown)
    return "".join(
        f'<h3 class="kind">{_esc(kind)}</h3>{_value(groups[kind])}'
        for kind in sorted(groups)
    )


def _size(status):
    if _absent(status):
        return ABSENT
    return f'<span class="size size-{_esc(status)}">{_esc(status)}</span>'


def _component_body(node):
    verification = _get(node, "verification")
    return (
        f'<h2>Documents</h2><div id="documents">{_documents(_get(node, "documents"))}</div>'
        f'<h2>Requirements</h2><div id="requirements">'
        f'{_value(_get(verification, "requirement_results"))}</div>'
        f'<h2>Acceptance criteria</h2><div id="criteria">'
        f'{_criteria(_get(verification, "criteria"))}</div>'
        f'<h2>Provenance</h2><div id="provenance">{_value(_get(node, "provenance"))}</div>'
        f'<h2>Size</h2><div id="size">{_size(_get(node, "size_status"))}</div>'
        f'<h2>Exemptions</h2><div id="exemptions">'
        f'<h3>sealed</h3>{_value(_get(node, "sealed"))}'
        f'<h3>pinned_overrides</h3>{_value(_get(node, "pinned_overrides"))}</div>'
        f'<h2>Owners</h2><div id="owners">{_value(_get(node, "owners"))}</div>'
    )


def _detail_page(node_id, node):
    node_type = _get(node, "type")
    body = (
        '<p><a href="../index.html">Graph</a> | '
        '<a href="../dashboard.html">Corpus health</a></p>'
        f"<h1>{_esc(node_id)}</h1>"
        f'<p class="type">{_esc(node_type)}</p>'
    )
    if node_type == "component":
        body += _component_body(node)
    return _page(node_id, body)


def _index_page(nodes, edges, script):
    node_items = "".join(
        f'<li class="node" data-id="{_esc(node_id)}" '
        f'data-type="{_esc(_get(nodes[node_id], "type"))}">'
        f'<a href="nodes/{_esc(node_id)}.html">{_esc(node_id)}</a></li>'
        for node_id in sorted(nodes)
    )
    edge_items = "".join(
        f'<li class="edge" data-from="{_esc(_get(e, "from"))}" '
        f'data-to="{_esc(_get(e, "to"))}" data-kind="{_esc(_get(e, "kind"))}">'
        f'{_esc(_get(e, "from"))} {_esc(_get(e, "kind"))} {_esc(_get(e, "to"))}</li>'
        for e in edges
    )
    body = (
        "<h1>Corpus graph</h1>"
        '<p><a href="dashboard.html">Corpus health</a></p>'
        '<input id="search" type="search">\n'
        '<svg id="dag"></svg>\n'
        f'<ul id="nodes">{node_items}</ul>\n'
        f'<ul id="edges">{edge_items}</ul>\n'
        '<script type="module">' + script + "\ninit(document);\n" + "</script>"
    )
    return _page("Corpus graph", body)


def _dashboard_page(nodes, aggregates):
    sizes = {}
    for node_id in nodes:
        node = nodes[node_id]
        if _get(node, "type") == "component":
            status = str(_get(node, "size_status"))
            sizes[status] = sizes.get(status, 0) + 1
    size_rows = "".join(
        f'<tr><td class="size-{_esc(s)}">{_esc(s)}</td><td>{sizes[s]}</td></tr>'
        for s in sorted(sizes)
    )
    body = (
        '<p><a href="index.html">Graph</a></p>'
        "<h1>Corpus health</h1>"
        f'<h2>Aggregates</h2><div id="aggregates">{_value(aggregates)}</div>'
        '<h2>Size-cap distribution</h2>'
        f'<table id="sizes"><tr><th>size_status</th><th>components</th></tr>{size_rows}</table>'
    )
    return _page("Corpus health", body)


def render_docs_site(graph, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    nodes = _get(graph, "nodes")
    edges = _get(graph, "edges")
    aggregates = _get(graph, "aggregates")
    script = ASSET_PATH.read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "nodes").mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(
        _index_page(nodes, edges, script), encoding="utf-8"
    )
    (out_dir / "dashboard.html").write_text(
        _dashboard_page(nodes, aggregates), encoding="utf-8"
    )
    for node_id in nodes:
        (out_dir / "nodes" / f"{node_id}.html").write_text(
            _detail_page(node_id, nodes[node_id]), encoding="utf-8"
        )


from .cli import main  # noqa: E402

__all__ = ["render_docs_site", "main"]
