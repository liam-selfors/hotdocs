"""Renders a `CorpusGraph` into a static docs/graph explorer site.

Implements `interface/library.md`:

    render_docs_site(graph: CorpusGraph, out_dir: Path) -> None

Everything here is pure templating over the `CorpusGraph` it is handed --
no file reads beyond what the caller already loaded, no network access, no
model calls (R-DOCS-004, R-DOCS-006). Output ordering is sorted
everywhere so the render is deterministic regardless of the input dict's
iteration order, per the spec's "all six acceptance criteria are `kind:
compiled` ... pure, deterministic templating."
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .graph import CorpusGraph, GraphLike, coerce_graph
from .html import esc

# R-DOCS-002: D9's owners list, minus the verification-toggle item this
# build has no repo-wide toggle to display for.
EXCLUDED_OWNER_ITEMS = {"cross_model_divergence_check", "fallback_standby_build"}

SIZE_STATUS_COLORS = {
    "ok": "#1b5e20",
    "warn": "#e65100",
    "warning": "#e65100",
    "over": "#b71c1c",
    "over_cap": "#b71c1c",
    "breach": "#b71c1c",
    "exceeded": "#b71c1c",
}
DEFAULT_SIZE_STATUS_COLOR = "#424242"

NODE_TYPE_LABELS = {
    "capability": "Capability",
    "component": "Component",
    "var": "Var",
}

# Candidate keys (tried in order) for each well-known provenance field.
PROVENANCE_FIELD_CANDIDATES = [
    (("model_pin", "model"), "Model pin"),
    (("prompt_version",), "Prompt version"),
    (
        ("last_cold_regen", "last_cold_regen_timestamp", "cold_regen_timestamp", "timestamp"),
        "Last cold-regen timestamp",
    ),
    (("freshness", "freshness_relative_to_d1", "freshness_vs_d1"), "Freshness (relative to D1)"),
]

# Candidate keys for each rendered spec-bundle section. Deliberately
# distinct from the keys used for R-id/acceptance status extraction below,
# so a structured status list is never mistaken for raw markdown content.
SPEC_CONTENT_FIELD_CANDIDATES = [
    ("component.md", ("component_md", "component_content")),
    ("requirements/", ("requirements_md", "requirements_content")),
    ("interface/", ("interface_md", "interface_content")),
    ("acceptance/", ("acceptance_md", "acceptance_content")),
    ("constraints.md", ("constraints_md", "constraints_content")),
]


def render_docs_site(graph: GraphLike, out_dir: Path) -> None:
    """Renders `graph` into a static site under `out_dir`.

    `out_dir` is created if it does not already exist. This never reads
    `verification/corpus-graph.json` itself -- the caller (the CLI, or any
    other library caller) is responsible for loading the `CorpusGraph` and
    passing it in.
    """
    g: CorpusGraph = coerce_graph(graph)
    out_dir = Path(out_dir)
    nodes_dir = out_dir / "nodes"
    assets_dir = out_dir / "assets"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    node_ids = sorted(g.nodes.keys())
    edges = sorted(
        (dict(e) for e in g.edges),
        key=lambda e: (str(e.get("from", "")), str(e.get("to", "")), str(e.get("kind", ""))),
    )
    filenames = {nid: f"{quote(nid, safe='')}.html" for nid in node_ids}

    (assets_dir / "app.css").write_text(_CSS, encoding="utf-8")
    (assets_dir / "app.js").write_text(_JS, encoding="utf-8")

    (out_dir / "index.html").write_text(
        _render_index(g, node_ids, edges, filenames), encoding="utf-8"
    )
    (out_dir / "health.html").write_text(_render_health(g, node_ids), encoding="utf-8")

    outgoing: "dict[str, list[dict[str, str]]]" = {nid: [] for nid in node_ids}
    incoming: "dict[str, list[dict[str, str]]]" = {nid: [] for nid in node_ids}
    for edge in edges:
        src, dst = edge.get("from"), edge.get("to")
        if src in outgoing:
            outgoing[src].append(edge)
        if dst in incoming:
            incoming[dst].append(edge)

    for nid in node_ids:
        node = g.nodes.get(nid) or {}
        doc = _render_node(nid, node, outgoing.get(nid, []), incoming.get(nid, []), filenames)
        (nodes_dir / filenames[nid]).write_text(doc, encoding="utf-8")


# --------------------------------------------------------------------------
# Page shell
# --------------------------------------------------------------------------


def _page(title: str, body: str, depth: int) -> str:
    prefix = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(title)} \u2014 Hotdocs Corpus Explorer</title>
<link rel="stylesheet" href="{prefix}assets/app.css">
</head>
<body>
<header class="site-header">
  <a class="brand" href="{prefix}index.html">Hotdocs Corpus Explorer</a>
  <nav>
    <a href="{prefix}index.html">Graph</a>
    <a href="{prefix}health.html">Corpus health</a>
  </nav>
</header>
<main>
{body}
</main>
<script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Index page: the DAG (R-DOCS-001)
# --------------------------------------------------------------------------


def _render_index(g: CorpusGraph, node_ids, edges, filenames) -> str:
    graph_json = json.dumps(
        {"nodes": g.nodes, "edges": edges, "aggregates": g.aggregates},
        sort_keys=True,
        default=str,
    )

    rows = []
    for nid in node_ids:
        node = g.nodes.get(nid) or {}
        ntype = node.get("type", "")
        flags = []
        if ntype == "component":
            if node.get("sealed"):
                flags.append("sealed")
            size_status = node.get("size_status")
            if size_status:
                flags.append(f"size:{size_status}")
            if node.get("pinned_overrides"):
                flags.append("pinned-overrides")
        search_key = f"{nid} {ntype} {' '.join(flags)}".lower()
        rows.append(
            f'<tr class="node-row" data-search="{esc(search_key)}">'
            f'<td><a href="nodes/{filenames[nid]}">{esc(nid)}</a></td>'
            f"<td>{esc(NODE_TYPE_LABELS.get(ntype, ntype))}</td>"
            f'<td>{esc(", ".join(flags))}</td>'
            "</tr>"
        )

    edge_rows = []
    for edge in edges:
        src, dst, kind = edge.get("from", ""), edge.get("to", ""), edge.get("kind", "")
        src_link = f'<a href="nodes/{filenames[src]}">{esc(src)}</a>' if src in filenames else esc(src)
        dst_link = f'<a href="nodes/{filenames[dst]}">{esc(dst)}</a>' if dst in filenames else esc(dst)
        search_key = f"{src} {dst} {kind}".lower()
        edge_rows.append(
            f'<li class="edge-row" data-search="{esc(search_key)}">{src_link} '
            f'<span class="edge-kind">--[{esc(kind)}]--&gt;</span> {dst_link}</li>'
        )

    body = f"""
<h1>Corpus Graph</h1>
<p>Rendered from <code>verification/corpus-graph.json</code> \u2014
{len(node_ids)} nodes, {len(edges)} edges.</p>
<input type="search" id="search" placeholder="Search nodes and edges\u2026" autocomplete="off">
<section>
  <h2>Nodes</h2>
  <table id="nodes-table">
    <thead><tr><th>ID</th><th>Type</th><th>Flags</th></tr></thead>
    <tbody>
    {''.join(rows)}
    </tbody>
  </table>
</section>
<section>
  <h2>Edges</h2>
  <ul id="edges-list">
  {''.join(edge_rows)}
  </ul>
</section>
<script type="application/json" id="graph-data">{graph_json}</script>
"""
    return _page("Graph", body, depth=0)


# --------------------------------------------------------------------------
# Corpus-health dashboard (R-DOCS-003)
# --------------------------------------------------------------------------


def _render_health(g: CorpusGraph, node_ids) -> str:
    agg_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in sorted(g.aggregates.items())
    )

    type_counts: "dict[str, int]" = {}
    size_status_counts: "dict[str, int]" = {}
    sealed_count = 0
    pinned_override_count = 0
    for nid in node_ids:
        node = g.nodes.get(nid) or {}
        ntype = node.get("type", "unknown")
        type_counts[ntype] = type_counts.get(ntype, 0) + 1
        if ntype == "component":
            status = node.get("size_status") or "unspecified"
            size_status_counts[status] = size_status_counts.get(status, 0) + 1
            if node.get("sealed"):
                sealed_count += 1
            pinned_override_count += len(node.get("pinned_overrides") or [])

    type_rows = "".join(
        f"<tr><td>{esc(NODE_TYPE_LABELS.get(t, t))}</td><td>{n}</td></tr>"
        for t, n in sorted(type_counts.items())
    )
    size_rows = "".join(
        f'<tr><td><span class="size-dot" style="background:'
        f'{SIZE_STATUS_COLORS.get(s, DEFAULT_SIZE_STATUS_COLOR)}"></span>{esc(s)}</td><td>{n}</td></tr>'
        for s, n in sorted(size_status_counts.items())
    )

    body = f"""
<h1>Corpus Health</h1>
<section>
  <h2>Aggregates</h2>
  <table><thead><tr><th>Metric</th><th>Value</th></tr></thead>
  <tbody>{agg_rows}</tbody></table>
</section>
<section>
  <h2>Node type counts</h2>
  <table><thead><tr><th>Type</th><th>Count</th></tr></thead>
  <tbody>{type_rows}</tbody></table>
</section>
<section>
  <h2>Size-cap distribution (components)</h2>
  <table><thead><tr><th>Status</th><th>Count</th></tr></thead>
  <tbody>{size_rows}</tbody></table>
</section>
<section>
  <h2>Sealed / pinned overrides</h2>
  <p>Sealed components: {sealed_count}</p>
  <p>Total pinned-override entries: {pinned_override_count}</p>
</section>
"""
    return _page("Corpus Health", body, depth=0)


# --------------------------------------------------------------------------
# Per-node detail page (R-DOCS-002 for component nodes)
# --------------------------------------------------------------------------


def _render_node(nid: str, node: "dict[str, Any]", outgoing, incoming, filenames) -> str:
    ntype = node.get("type", "")
    sections = [
        f"<h1>{esc(nid)}</h1>",
        f"<p>Type: <strong>{esc(NODE_TYPE_LABELS.get(ntype, ntype))}</strong></p>",
    ]

    if ntype == "component":
        sections.append(_render_component_detail(node))

    sections.append(_render_edges_section("Outgoing (depends_on / realizes / uses_var)", outgoing, filenames, True))
    sections.append(_render_edges_section("Incoming (referenced by)", incoming, filenames, False))

    return _page(nid, "\n".join(sections), depth=1)


def _render_edges_section(title: str, edges, filenames, is_outgoing: bool) -> str:
    if not edges:
        return f"<section><h2>{esc(title)}</h2><p>None.</p></section>"
    items = []
    for edge in edges:
        other = edge.get("to") if is_outgoing else edge.get("from")
        kind = edge.get("kind", "")
        if other in filenames:
            link = f'<a href="{filenames[other]}">{esc(other)}</a>'
        else:
            link = esc(other)
        items.append(f"<li>[{esc(kind)}] {link}</li>")
    return f"<section><h2>{esc(title)}</h2><ul>{''.join(items)}</ul></section>"


def _render_component_detail(node: "dict[str, Any]") -> str:
    return "\n".join(
        [
            _render_spec_content_section(node),
            _render_requirements_section(node),
            _render_acceptance_section(node),
            _render_provenance_section(node),
            _render_size_section(node),
            _render_seal_section(node),
            _render_owners_section(node),
        ]
    )


def _render_absent(title: str) -> str:
    return (
        f"<section><h2>{esc(title)}</h2>"
        "<p><em>Not present in corpus-graph.json for this node.</em></p></section>"
    )


def _extract_spec_content(node: "dict[str, Any]") -> "dict[str, Any]":
    nested_candidates = [node]
    for key in ("spec_bundle", "spec"):
        nested = node.get(key)
        if isinstance(nested, dict):
            nested_candidates.append(nested)
    result: "dict[str, Any]" = {}
    for label, keys in SPEC_CONTENT_FIELD_CANDIDATES:
        value = None
        for source in nested_candidates:
            for k in keys:
                if k in source:
                    value = source[k]
                    break
            if value is not None:
                break
        if value is not None:
            result[label] = value
    return result


def _render_spec_content_section(node: "dict[str, Any]") -> str:
    content = _extract_spec_content(node)
    if not content:
        return _render_absent("Spec bundle content")
    blocks = []
    for label, value in content.items():
        text = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True, default=str)
        blocks.append(f"<h3>{esc(label)}</h3><pre>{esc(text)}</pre>")
    return f"<section><h2>Spec bundle content</h2>{''.join(blocks)}</section>"


def _extract_requirements(node: "dict[str, Any]"):
    verification = node.get("verification")
    source = None
    if isinstance(verification, dict):
        source = verification.get("requirements")
        if source is None:
            source = verification.get("r_ids")
    if source is None:
        source = node.get("r_ids")
    rows = []
    if isinstance(source, list):
        for item in source:
            if isinstance(item, dict):
                rid = item.get("id") or item.get("r_id") or item.get("rid")
                status = item.get("status") or item.get("result")
                rows.append((rid, status))
            else:
                rows.append((item, None))
    elif isinstance(source, dict):
        for rid, status in source.items():
            rows.append((rid, status))
    return rows


def _render_requirements_section(node: "dict[str, Any]") -> str:
    rows = _extract_requirements(node)
    if not rows:
        return _render_absent("Requirements (R-id status)")
    body = "".join(f"<tr><td>{esc(rid)}</td><td>{esc(status)}</td></tr>" for rid, status in rows)
    return (
        "<section><h2>Requirements (R-id status)</h2>"
        f"<table><thead><tr><th>R-id</th><th>Status</th></tr></thead>"
        f"<tbody>{body}</tbody></table></section>"
    )


def _extract_acceptance(node: "dict[str, Any]"):
    verification = node.get("verification")
    source = None
    if isinstance(verification, dict):
        source = verification.get("acceptance")
        if source is None:
            source = verification.get("criteria")
    if source is None:
        source = node.get("acceptance_results")
    rows = []
    if isinstance(source, list):
        for item in source:
            if isinstance(item, dict):
                cid = item.get("id") or item.get("criterion_id") or item.get("name")
                kind = item.get("kind", "unspecified")
                result = item.get("result") or item.get("status")
                rows.append((kind, cid, result))
    elif isinstance(source, dict):
        for kind, items in source.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        cid = item.get("id") or item.get("criterion_id")
                        result = item.get("result") or item.get("status")
                        rows.append((kind, cid, result))
                    else:
                        rows.append((kind, item, None))
    return rows


def _render_acceptance_section(node: "dict[str, Any]") -> str:
    rows = _extract_acceptance(node)
    if not rows:
        return _render_absent("Acceptance criteria (by kind)")
    by_kind: "dict[Any, list[tuple[Any, Any]]]" = {}
    for kind, cid, result in rows:
        by_kind.setdefault(kind, []).append((cid, result))
    blocks = []
    for kind in sorted(by_kind, key=lambda k: str(k)):
        items = "".join(
            f"<tr><td>{esc(cid)}</td><td>{esc(result)}</td></tr>" for cid, result in by_kind[kind]
        )
        blocks.append(
            f"<h3>kind: {esc(kind)}</h3>"
            f"<table><thead><tr><th>Criterion</th><th>Result</th></tr></thead>"
            f"<tbody>{items}</tbody></table>"
        )
    return f"<section><h2>Acceptance criteria (by kind)</h2>{''.join(blocks)}</section>"


def _render_provenance_section(node: "dict[str, Any]") -> str:
    provenance = node.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        return _render_absent("Provenance")
    rows = []
    consumed = set()
    for keys, label in PROVENANCE_FIELD_CANDIDATES:
        for k in keys:
            if k in provenance:
                rows.append((label, provenance[k]))
                consumed.add(k)
                break
    leftover = {k: v for k, v in provenance.items() if k not in consumed}
    body = "".join(f"<tr><td>{esc(label)}</td><td>{esc(value)}</td></tr>" for label, value in rows)
    extra = ""
    if leftover:
        extra = (
            "<h3>Additional provenance fields</h3>"
            f"<pre>{esc(json.dumps(leftover, indent=2, sort_keys=True, default=str))}</pre>"
        )
    return f"<section><h2>Provenance</h2><table><tbody>{body}</tbody></table>{extra}</section>"


def _render_size_section(node: "dict[str, Any]") -> str:
    status = node.get("size_status")
    color = SIZE_STATUS_COLORS.get(status, DEFAULT_SIZE_STATUS_COLOR)
    extra_keys = [k for k in ("size", "size_caps", "size_bytes") if k in node]
    extra_html = ""
    if extra_keys:
        extra = {k: node[k] for k in extra_keys}
        extra_html = f"<pre>{esc(json.dumps(extra, indent=2, sort_keys=True, default=str))}</pre>"
    label = status if status is not None else "unspecified"
    return (
        "<section><h2>Size vs. caps</h2>"
        f'<p><span class="size-dot" style="background:{color}"></span>{esc(label)}</p>'
        f"{extra_html}</section>"
    )


def _render_seal_section(node: "dict[str, Any]") -> str:
    sealed = bool(node.get("sealed"))
    overrides = node.get("pinned_overrides") or []
    items = "".join(f"<li>{esc(o)}</li>" for o in overrides)
    overrides_html = f"<ul>{items}</ul>" if overrides else "<p>None.</p>"
    return (
        "<section><h2>Sealed / pinned overrides</h2>"
        f"<p>Sealed: <strong>{'yes' if sealed else 'no'}</strong></p>"
        f"<h3>Pinned overrides</h3>{overrides_html}</section>"
    )


def _render_owners_section(node: "dict[str, Any]") -> str:
    owners = node.get("owners")
    if owners is None:
        return _render_absent("Owners")
    # R-DOCS-002: D9's owners list, minus the two verification-toggle items
    # this build has no repo-wide toggle to display -- nothing else added,
    # nothing else dropped.
    filtered = [o for o in owners if o not in EXCLUDED_OWNER_ITEMS]
    items = "".join(f"<li>{esc(o)}</li>" for o in filtered)
    return f"<section><h2>Owners</h2><ul>{items}</ul></section>"


# --------------------------------------------------------------------------
# Static assets
# --------------------------------------------------------------------------

_CSS = """
:root { color-scheme: light; }
body { font-family: -apple-system, Segoe UI, sans-serif; margin: 0; background: #fafafa; color: #1b1b1b; }
.site-header { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1.5rem; background: #1b1b1b; color: #fff; }
.site-header a { color: #fff; text-decoration: none; margin-left: 1rem; }
.site-header .brand { font-weight: 700; margin-left: 0; }
main { max-width: 960px; margin: 0 auto; padding: 1.5rem; }
table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; }
th, td { border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #eee; }
pre { background: #f0f0f0; padding: 0.75rem; overflow-x: auto; white-space: pre-wrap; }
input#search { width: 100%; padding: 0.5rem; font-size: 1rem; margin-bottom: 1rem; box-sizing: border-box; }
.size-dot { display: inline-block; width: 0.7em; height: 0.7em; border-radius: 50%; margin-right: 0.4em; }
.hidden { display: none !important; }
ul#edges-list { list-style: none; padding: 0; }
ul#edges-list li { padding: 0.25rem 0; border-bottom: 1px solid #eee; }
.edge-kind { color: #666; margin: 0 0.4em; }
"""

_JS = """
(function () {
  var input = document.getElementById("search");
  if (!input) { return; }
  var rows = Array.prototype.slice.call(document.querySelectorAll("[data-search]"));
  input.addEventListener("input", function () {
    var term = input.value.trim().toLowerCase();
    rows.forEach(function (row) {
      var hay = row.getAttribute("data-search") || "";
      row.classList.toggle("hidden", term.length > 0 && hay.indexOf(term) === -1);
    });
  });
})();
"""