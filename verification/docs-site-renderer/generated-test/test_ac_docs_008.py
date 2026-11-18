# hotdocs-criterion: sha256:94ff90ba5945d0aab68fac561574d6b827fdc59df1f3982a95b4d052eb5997f8
import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import docs_site_renderer


RAW = "<script>alert(1)</script>"
DOC_TEXT = RAW + " & more"
ALPHA = "comp-alpha"
BETA = "comp-beta"
BETA_MARKER = "BetaDocMarkerText"


@dataclass
class FakeCorpusGraph:
    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

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


def make_graph():
    nodes = {
        ALPHA: {
            "type": "component",
            "verification": {
                "requirement_results": {},
                "criteria": [],
            },
            "provenance": {
                "model": "anthropic:claude-sonnet-5",
                "prompt_version": "v1",
                "generated_at": "2026-01-01T00:00:00Z",
            },
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["alpha-team"],
            "documents": {"component.md": DOC_TEXT},
        },
        BETA: {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {"component.md": BETA_MARKER},
        },
    }
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 1.0,
        "orphan_var_rate": 0.0,
    }
    return FakeCorpusGraph(nodes=nodes, edges=[], aggregates=aggregates)


def all_files(out_dir):
    result = {}
    for p in sorted(Path(out_dir).rglob("*")):
        if p.is_file():
            result[p] = p.read_text(encoding="utf-8", errors="replace")
    return result


def detail_pages(files, out_dir, node_id, other_id):
    slug = node_id[len("comp-"):]
    other_slug = other_id[len("comp-"):]
    by_path = [
        p
        for p in files
        if p.suffix.lower() in (".html", ".htm")
        and (
            node_id in str(p.relative_to(out_dir))
            or slug in str(p.relative_to(out_dir))
        )
        and other_slug not in str(p.relative_to(out_dir))
    ]
    if by_path:
        return by_path
    return [
        p
        for p, text in files.items()
        if p.suffix.lower() in (".html", ".htm")
        and node_id in text
        and other_id not in text
    ]


def test_ac_docs_008_escapes_values_and_tolerates_null_fields(tmp_path):
    out_dir = tmp_path / "site"
    graph = make_graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    files = all_files(out_dir)
    assert files, "render_docs_site wrote no files"

    # The raw script tag never appears anywhere in the rendered site.
    for p, text in files.items():
        assert RAW not in text, "raw unescaped script found in " + str(p)

    alpha_pages = detail_pages(files, out_dir, ALPHA, BETA)
    assert alpha_pages, "no detail view found for " + ALPHA
    alpha_hits = [
        p
        for p in alpha_pages
        if "&lt;script&gt;" in files[p] and "&amp; more" in files[p]
    ]
    assert alpha_hits, (
        "first node's detail view lacks escaped document text: "
        + repr([str(p) for p in alpha_pages])
    )
    for p in alpha_hits:
        assert RAW not in files[p]

    beta_pages = detail_pages(files, out_dir, BETA, ALPHA)
    assert beta_pages, "no detail view found for " + BETA
    assert any(BETA_MARKER in files[p] for p in beta_pages), (
        "second node's detail view did not render its content"
    )