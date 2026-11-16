import docs_site_renderer

import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path


RAW_SCRIPT = "<script>alert(1)</script>"
ALPHA_TEXT = "<script>alert(1)</script> & more"
BETA_MARKER = "BetaDocMarker42"


@dataclass
class CorpusGraph:
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


def _build_graph():
    nodes = {
        "comp-alpha": {
            "type": "component",
            "verification": None,
            "provenance": {
                "model": "anthropic:claude-sonnet-5",
                "prompt_version": "v1",
                "generated_at": "2026-11-01T00:00:00Z",
            },
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["docs-team"],
            "documents": {"component.md": ALPHA_TEXT},
        },
        "comp-beta": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {"component.md": BETA_MARKER + "\n"},
        },
    }
    return CorpusGraph(
        nodes=nodes,
        edges=[],
        aggregates={
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    )


def _read_all(out_dir: Path):
    pages = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file():
            pages[p] = p.read_bytes().decode("utf-8", errors="replace")
    return pages


def test_ac_docs_008_detail_views_escape_and_tolerate_nulls(tmp_path):
    out_dir = tmp_path / "out"
    graph = _build_graph()

    # Must not raise, even with the second node's null/empty fields.
    docs_site_renderer.render_docs_site(graph, out_dir)

    pages = _read_all(out_dir)
    assert pages, "render_docs_site wrote no files"

    # The raw script must never appear anywhere in the rendered site.
    for path, text in pages.items():
        assert RAW_SCRIPT not in text, f"raw script tag found unescaped in {path}"

    # The first node's detail view: the page rendering its document content.
    alpha_pages = [p for p, t in pages.items() if "&amp; more" in t]
    assert alpha_pages, "no page contains the escaped '&amp; more' document text"
    assert any("&lt;script&gt;" in pages[p] for p in alpha_pages), (
        "the page holding comp-alpha's document does not contain '&lt;script&gt;'"
    )
    assert any(
        "&lt;script&gt;" in pages[p] and "&amp; more" in pages[p] for p in alpha_pages
    )

    # The second node's detail view rendered: its document content is present
    # on some page, and that page is not comp-alpha's detail view.
    beta_pages = [p for p, t in pages.items() if BETA_MARKER in t]
    assert beta_pages, "comp-beta's detail view (its document content) was not rendered"
    assert any(p not in alpha_pages for p in beta_pages) or any(
        "comp-beta" in pages[p] for p in beta_pages
    )