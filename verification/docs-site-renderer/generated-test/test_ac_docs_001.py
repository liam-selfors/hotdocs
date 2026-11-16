"""AC-DOCS-001: the rendered DAG view holds one element per node and one per edge.

Given a corpus-graph.json with three nodes and two edges
When render_docs_site runs
Then the rendered site's DAG view contains three node elements and two edge
  elements
"""

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import docs_site_renderer


# --------------------------------------------------------------------------
# Fixture: a CorpusGraph-shaped value (comp-corpus-graph-builder's documented
# shape: a dataclass with nodes/edges/aggregates, to_dict(), to_json_bytes()).
# It is also a dict holding the same keys, so either access style works.
# --------------------------------------------------------------------------

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "realizes: [P-ZERO-EDIT]\n"
    "uses_var: [VAR-FOO-URL]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "A synthetic component.\n"
)

REQUIREMENT_MD = "**R-FOO-001** — MUST do foo.\n"

NODE_IDS = ["P-ZERO-EDIT", "VAR-FOO-URL", "comp-foo"]

EDGES = [
    {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
    {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
]

NODE_TYPES = {"capability", "component", "var"}
EDGE_KINDS = {"depends_on", "realizes", "uses_var"}


@dataclass(eq=False)
class CorpusGraph(dict):
    nodes: dict
    edges: list
    aggregates: dict

    def __post_init__(self):
        dict.update(
            self,
            {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates},
        )

    def to_dict(self):
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "aggregates": self.aggregates,
        }

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
            + "\n"
        ).encode("utf-8")


def _make_graph():
    nodes = {
        "P-ZERO-EDIT": {"type": "capability"},
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": COMPONENT_MD,
                "requirements/R-FOO-001.md": REQUIREMENT_MD,
            },
        },
        "VAR-FOO-URL": {"type": "var"},
    }
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(
        nodes=nodes, edges=[dict(e) for e in EDGES], aggregates=aggregates
    )


# --------------------------------------------------------------------------
# Minimal HTML tree builder (stdlib only).
# --------------------------------------------------------------------------

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class _El:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children = []
        self.text_parts = []

    def text(self):
        out = list(self.text_parts)
        for c in self.children:
            out.append(c.text())
        return " ".join(out)

    def attr_text(self):
        return " ".join(v for _, v in self.attrs)

    def ancestors(self):
        n = self.parent
        while n is not None:
            yield n
            n = n.parent


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _El("#root", [], None)
        self.cur = self.root
        self.all = []

    def _new(self, tag, attrs):
        el = _El(tag.lower(), [(k.lower(), v or "") for k, v in attrs], self.cur)
        self.cur.children.append(el)
        self.all.append(el)
        return el

    def handle_starttag(self, tag, attrs):
        el = self._new(tag, attrs)
        if el.tag not in VOID_TAGS:
            self.cur = el

    def handle_startendtag(self, tag, attrs):
        self._new(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.text_parts.append(data)


def _parse(html_text):
    b = _Builder()
    b.feed(html_text)
    b.close()
    return b.all


# --------------------------------------------------------------------------
# Locating node and edge elements.
# --------------------------------------------------------------------------

def _refs(s):
    low = s.lower()
    return {nid for nid in NODE_IDS if nid.lower() in low}


def _class_tokens(el):
    toks = []
    for k, v in el.attrs:
        if k == "class":
            toks.extend(t.lower() for t in v.split())
    return toks


def _token_marks(token, word):
    return (
        token == word
        or token.endswith("-" + word)
        or token.endswith("_" + word)
    )


def _attr(el, name):
    for k, v in el.attrs:
        if k == name:
            return v
    return None


def _is_edge_marked(el):
    if any(_token_marks(t, "edge") for t in _class_tokens(el)):
        return True
    names = {k for k, _ in el.attrs}
    if any(n.startswith("data-edge") for n in names):
        return True
    has_from = bool(names & {"data-from", "data-source", "data-src"})
    has_to = bool(names & {"data-to", "data-target", "data-dst"})
    if has_from and has_to:
        return True
    kind = _attr(el, "data-kind")
    if kind is not None and kind.strip() in EDGE_KINDS:
        return True
    return False


def _is_node_marked(el):
    if _is_edge_marked(el):
        return False
    if any(_token_marks(t, "node") for t in _class_tokens(el)):
        return True
    names = {k for k, _ in el.attrs}
    if any(n.startswith("data-node") for n in names):
        return True
    for n in ("data-type", "data-kind", "data-node-type"):
        v = _attr(el, n)
        if v is not None and v.strip() in NODE_TYPES:
            return True
    return False


def _edges_referenced(ids):
    return {
        (e["from"], e["to"], e["kind"])
        for e in EDGES
        if e["from"] in ids and e["to"] in ids
    }


def _outermost(els):
    s = set(map(id, els))
    return [e for e in els if not any(id(a) in s for a in e.ancestors())]


def _marker_strategy(all_els):
    edge_els = []
    for el in all_els:
        if _is_edge_marked(el):
            ids = _refs(el.attr_text() + " " + el.text())
            if _edges_referenced(ids):
                edge_els.append(el)
    edge_els = _outermost(edge_els)
    edge_ids = set(map(id, edge_els))

    node_els = []
    for el in all_els:
        if any(id(a) in edge_ids for a in el.ancestors()) or id(el) in edge_ids:
            continue
        if _is_node_marked(el):
            if _refs(el.attr_text() + " " + el.text()):
                node_els.append(el)
    node_els = _outermost(node_els)
    return node_els, edge_els


def _fallback_strategy(all_els):
    edge_els = []
    for el in all_els:
        if el.tag == "a":
            continue
        if _edges_referenced(_refs(el.attr_text())):
            edge_els.append(el)
    edge_els = _outermost(edge_els)
    edge_ids = set(map(id, edge_els))

    node_els = []
    for el in all_els:
        if el.tag != "a":
            continue
        if any(id(a) in edge_ids for a in el.ancestors()):
            continue
        href = _attr(el, "href") or ""
        if len(_refs(href)) == 1:
            node_els.append(el)
    return node_els, edge_els


def _analyse(html_text):
    all_els = _parse(html_text)
    nodes, edges = _marker_strategy(all_els)
    if not nodes and not edges:
        nodes, edges = _fallback_strategy(all_els)
    return nodes, edges


def _find_dag_page(out_dir):
    pages = sorted(p for p in Path(out_dir).rglob("*") if p.is_file() and p.suffix.lower() in (".html", ".htm"))
    assert pages, f"no HTML pages rendered under {out_dir}"

    best = None
    for p in pages:
        text = p.read_text(encoding="utf-8", errors="replace")
        low = text.lower()
        if not all(nid.lower() in low for nid in NODE_IDS):
            continue
        nodes, edges = _analyse(text)
        name = p.name.lower()
        preferred = (
            name in ("index.html", "index.htm")
            or "dag" in name
            or "graph" in name
        )
        score = (len(nodes) + len(edges) > 0, bool(edges), preferred, len(edges), len(nodes))
        if best is None or score > best[0]:
            best = (score, p, text, nodes, edges)
    assert best is not None, (
        "no rendered HTML page mentions all three node ids: "
        + ", ".join(str(p.relative_to(out_dir)) for p in pages)
    )
    return best[1], best[2], best[3], best[4]


# --------------------------------------------------------------------------
# The test.
# --------------------------------------------------------------------------

def test_ac_docs_001_dag_view_has_three_nodes_and_two_edges(tmp_path):
    graph = _make_graph()

    # Given: a corpus-graph.json with three nodes and two edges.
    verification_dir = tmp_path / "repo" / "verification"
    verification_dir.mkdir(parents=True)
    graph_path = verification_dir / "corpus-graph.json"
    graph_path.write_bytes(graph.to_json_bytes())
    on_disk = json.loads(graph_path.read_text(encoding="utf-8"))
    assert len(on_disk["nodes"]) == 3
    assert len(on_disk["edges"]) == 2

    out_dir = tmp_path / "site"

    # When: render_docs_site runs.
    result = docs_site_renderer.render_docs_site(graph, out_dir)
    assert result is None

    # Then: the DAG view contains three node elements and two edge elements.
    page, text, node_els, edge_els = _find_dag_page(out_dir)

    detail = (
        f"page={page.relative_to(out_dir)}; "
        f"node elements={[ (e.tag, e.attrs) for e in node_els ]}; "
        f"edge elements={[ (e.tag, e.attrs) for e in edge_els ]}"
    )

    assert len(node_els) == 3, f"expected 3 node elements, got {len(node_els)}: {detail}"
    assert len(edge_els) == 2, f"expected 2 edge elements, got {len(edge_els)}: {detail}"

    node_ids_seen = set()
    for el in node_els:
        node_ids_seen |= _refs(el.attr_text() + " " + el.text())
    assert node_ids_seen == set(NODE_IDS), detail

    edges_seen = set()
    for el in edge_els:
        edges_seen |= _edges_referenced(_refs(el.attr_text() + " " + el.text()))
    assert edges_seen == {(e["from"], e["to"], e["kind"]) for e in EDGES}, detail