"""Docs site renderer: renders ``verification/corpus-graph.json`` into a static site.

A pure presentation layer: the DAG view (``index.html``), one detail page per
node (``nodes/<id>.html``) and the corpus-health dashboard (``dashboard.html``),
all drawn from the corpus graph alone. Layout and search run in the browser,
in the declared asset ``static/app.js``.
"""

from __future__ import annotations

import html
import importlib.util
import json
import sys
from pathlib import Path

__all__ = ["render_docs_site", "main"]

_SIZE_TONES = {"ok": "ok", "over": "fail", "unknown": "neutral"}
_STATUS_KEYS = ("status", "result", "verdict")
_ABSENT = '<p class="muted">absent</p>'


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _first(record, names):
    for name in names:
        value = _get(record, name)
        if value is not None:
            return value
    return None


def _status(value):
    return _first(value, _STATUS_KEYS) if isinstance(value, dict) else value


def _text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _esc(value):
    return html.escape(_text(value), quote=True)


def _shown(value):
    return html.escape("absent" if value is None else _text(value), quote=True)


def _block(items, open_tag, close_tag):
    if items:
        return open_tag + "\n" + "\n".join(items) + "\n" + close_tag + "\n"
    return _ABSENT + "\n"


def _tool_root():
    for parent in Path(__file__).absolute().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_ui_style():
    path = _tool_root() / "gen" / "ui-style" / "ui_style.py"
    spec = importlib.util.spec_from_file_location("ui_style", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ui_style"] = module
    spec.loader.exec_module(module)
    return module


def _page(title, style, body, script=""):
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{_esc(title)}</title>\n"
        f"{style}\n"
        "</head>\n"
        "<body>\n"
        f"{body}"
        f"{script}"
        "</body>\n"
        "</html>\n"
    )


def _requirement_rows(verification):
    results = _get(verification, "requirement_results")
    if isinstance(results, dict):
        return [(rid, _status(value)) for rid, value in results.items()]
    return [
        (_first(entry, ("id", "requirement_id")), _status(entry))
        for entry in results or []
    ]


def _criterion_rows(verification):
    criteria = _get(verification, "criteria")
    if isinstance(criteria, dict):
        entries = list(criteria.items())
    else:
        entries = [(_first(entry, ("id", "criterion_id")), entry) for entry in criteria or []]
    return [(cid, _get(entry, "kind"), _status(entry)) for cid, entry in entries]


def _index_html(style, script, nodes, edges):
    node_items = [
        f'<li class="node" data-id="{_esc(node_id)}" data-type="{_esc(_get(nodes[node_id], "type"))}">'
        f'<a href="nodes/{_esc(node_id)}.html">{_esc(node_id)}</a> '
        f'<span class="muted">{_shown(_get(nodes[node_id], "type"))}</span></li>'
        for node_id in sorted(nodes)
    ]
    edge_items = [
        f'<li class="edge" data-from="{_esc(_get(edge, "from"))}" data-to="{_esc(_get(edge, "to"))}" '
        f'data-kind="{_esc(_get(edge, "kind"))}"><code>{_esc(_get(edge, "from"))}</code> '
        f'{_esc(_get(edge, "kind"))} <code>{_esc(_get(edge, "to"))}</code></li>'
        for edge in edges
    ]
    body = (
        '<nav><a href="dashboard.html">Dashboard</a></nav>\n'
        "<h1>Corpus graph</h1>\n"
        '<input id="search" type="search" aria-label="Filter nodes by id" placeholder="Filter nodes by id">\n'
        '<svg id="dag"></svg>\n'
        "<h2>Nodes</h2>\n"
        '<ul id="nodes">\n' + "".join(item + "\n" for item in node_items) + "</ul>\n"
        "<h2>Edges</h2>\n"
        '<ul id="edges">\n' + "".join(item + "\n" for item in edge_items) + "</ul>\n"
    )
    script_element = '<script type="module">' + script + "\ninit(document);\n" + "</script>\n"
    return _page("Corpus graph", style, body, script_element)


def _component_body(node):
    verification = _get(node, "verification")
    documents = _get(node, "documents") or {}
    doc_items = [
        f"<section><h3>{_esc(path)}</h3><pre>{_esc(text)}</pre></section>"
        for path, text in documents.items()
    ]
    req_items = [
        f"<li><code>{_shown(rid)}</code>: {_shown(status)}</li>"
        for rid, status in _requirement_rows(verification)
    ]
    groups = {}
    for cid, kind, result in _criterion_rows(verification):
        groups.setdefault(_shown(kind), []).append(
            f"<li><code>{_shown(cid)}</code>: {_shown(result)}</li>"
        )
    crit_items = [
        f"<h3>{kind}</h3>\n<ul>\n" + "\n".join(items) + "\n</ul>"
        for kind, items in groups.items()
    ]
    provenance = _get(node, "provenance") or {}
    prov_items = [
        f"<dt>{_esc(key)}</dt><dd>{_shown(provenance[key])}</dd>" for key in sorted(provenance)
    ]
    size_status = _get(node, "size_status")
    tone = _SIZE_TONES.get(size_status, "neutral")
    override_items = [f"<li>{_shown(item)}</li>" for item in _get(node, "pinned_overrides") or []]
    owner_items = [f"<li>{_shown(owner)}</li>" for owner in _get(node, "owners") or []]
    return (
        "<h2>Documents</h2>\n" + _block(doc_items, "<div>", "</div>")
        + "<h2>Requirements</h2>\n" + _block(req_items, "<ul>", "</ul>")
        + "<h2>Acceptance criteria</h2>\n" + _block(crit_items, "<div>", "</div>")
        + "<h2>Provenance</h2>\n" + _block(prov_items, "<dl>", "</dl>")
        + "<h2>Size</h2>\n"
        + f'<p><span class="size tone-{tone}">{_shown(size_status)}</span></p>\n'
        + "<h2>Exemptions</h2>\n"
        + f"<p>sealed: {_shown(_get(node, 'sealed'))}</p>\n"
        + "<h3>Pinned overrides</h3>\n" + _block(override_items, "<ul>", "</ul>")
        + "<h2>Owners</h2>\n" + _block(owner_items, "<ul>", "</ul>")
    )


def _detail_html(style, node_id, node):
    node_type = _get(node, "type")
    body = (
        '<nav><a href="../index.html">Graph</a> <a href="../dashboard.html">Dashboard</a></nav>\n'
        f"<h1>{_esc(node_id)}</h1>\n"
        f'<p class="muted">{_shown(node_type)}</p>\n'
    )
    if node_type == "component":
        body += _component_body(node)
    return _page(node_id, style, body)


def _tally_items(counts, tones=None):
    items = []
    for key in sorted(counts):
        label = f"{_esc(key)}: {counts[key]}"
        if tones is not None:
            label = f'<span class="tone-{tones.get(key, "neutral")}">{label}</span>'
        items.append(f"<li>{label}</li>")
    return items


def _dashboard_html(style, nodes, aggregates):
    type_counts = {}
    size_counts = {}
    req_counts = {}
    for node_id in sorted(nodes):
        node = nodes[node_id]
        node_type = _text(_get(node, "type"))
        type_counts[node_type] = type_counts.get(node_type, 0) + 1
        if _get(node, "type") == "component":
            size = _text(_get(node, "size_status"))
            size_counts[size] = size_counts.get(size, 0) + 1
            for _rid, status in _requirement_rows(_get(node, "verification")):
                key = _text(status)
                req_counts[key] = req_counts.get(key, 0) + 1
    agg_items = [
        f"<dt>{_esc(key)}</dt><dd>{_shown(aggregates[key])}</dd>" for key in sorted(aggregates)
    ]
    body = (
        '<nav><a href="index.html">Graph</a></nav>\n'
        "<h1>Corpus health</h1>\n"
        "<h2>Aggregates</h2>\n" + _block(agg_items, "<dl>", "</dl>")
        + "<h2>Nodes by type</h2>\n" + _block(_tally_items(type_counts), "<ul>", "</ul>")
        + "<h2>Size-cap distribution</h2>\n"
        + _block(_tally_items(size_counts, _SIZE_TONES), "<ul>", "</ul>")
        + "<h2>Requirement coverage</h2>\n" + _block(_tally_items(req_counts), "<ul>", "</ul>")
    )
    return _page("Corpus health", style, body)


def render_docs_site(graph, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    style = _load_ui_style().style_element()
    script = (Path(__file__).parent.parent / "static" / "app.js").read_text(encoding="utf-8")
    nodes = _get(graph, "nodes") or {}
    edges = _get(graph, "edges") or []
    aggregates = _get(graph, "aggregates") or {}
    (out_dir / "nodes").mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(_index_html(style, script, nodes, edges), encoding="utf-8")
    for node_id in sorted(nodes):
        (out_dir / "nodes" / f"{node_id}.html").write_text(
            _detail_html(style, node_id, nodes[node_id]), encoding="utf-8"
        )
    (out_dir / "dashboard.html").write_text(
        _dashboard_html(style, nodes, aggregates), encoding="utf-8"
    )


from .cli import main  # noqa: E402
