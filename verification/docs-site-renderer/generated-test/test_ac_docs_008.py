import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import docs_site_renderer


RAW = "<script>alert(1)</script>"
FIRST_ID = "comp-xssalpha"
FIRST_SLUG = "xssalpha"
SECOND_ID = "comp-nullbeta"
SECOND_SLUG = "nullbeta"


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
        FIRST_ID: {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["docs-team"],
            "documents": {
                "component.md": RAW + " & more",
            },
        },
        SECOND_ID: {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {
                "component.md": "Plain beta component text.",
            },
        },
    }
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=[], aggregates=aggregates)


def _read_all(out_dir: Path):
    files = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file():
            try:
                files[p] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return files


def _detail_pages(files, out_dir, own_id, own_slug, other_id, other_slug):
    by_name = [
        p
        for p in files
        if own_slug in str(p.relative_to(out_dir)) and other_slug not in str(p.relative_to(out_dir))
    ]
    if by_name:
        return by_name
    return [
        p
        for p, text in files.items()
        if own_id in text and other_id not in text
    ]


def test_ac_docs_008_escapes_values_and_tolerates_null_fields(tmp_path):
    graph = _build_graph()
    out_dir = tmp_path / "site"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Second node has null verification/provenance and empty owners: must not raise.
    docs_site_renderer.render_docs_site(graph, out_dir)

    files = _read_all(out_dir)
    assert files, "render_docs_site wrote no files"

    first_pages = _detail_pages(
        files, out_dir, FIRST_ID, FIRST_SLUG, SECOND_ID, SECOND_SLUG
    )
    assert first_pages, (
        "no detail view found for %s among %r"
        % (FIRST_ID, [str(p.relative_to(out_dir)) for p in files])
    )

    for p in first_pages:
        assert RAW not in files[p], (
            "raw script tag found unescaped in %s" % p.relative_to(out_dir)
        )

    assert any("&lt;script&gt;" in files[p] for p in first_pages), (
        "first node's detail view lacks escaped '&lt;script&gt;'"
    )
    assert any("&amp; more" in files[p] for p in first_pages), (
        "first node's detail view lacks escaped '&amp; more'"
    )

    second_pages = _detail_pages(
        files, out_dir, SECOND_ID, SECOND_SLUG, FIRST_ID, FIRST_SLUG
    )
    assert second_pages, (
        "no detail view rendered for %s among %r"
        % (SECOND_ID, [str(p.relative_to(out_dir)) for p in files])
    )
    assert any(files[p].strip() for p in second_pages), (
        "second node's detail view is empty"
    )