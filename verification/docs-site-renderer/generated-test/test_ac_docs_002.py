"""AC-DOCS-002: a component's detail view shows every field of its node.

Given a component node whose documents, verification (with criteria and
requirement_results), provenance, size_status, sealed, pinned_overrides and
owners each hold a distinctive value, when render_docs_site runs, then that
component's detail view includes every one of those values.
"""

import html
import json
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import docs_site_renderer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class CorpusGraph:
    """Stand-in matching corpus-graph-builder's documented CorpusGraph shape:
    a dataclass with nodes, edges, aggregates, to_dict() and to_json_bytes()."""

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

    # Tolerate dict-style access as well.
    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)


SLUG = "zqwidget"
COMP_ID = "comp-" + SLUG

DOC_COMPONENT = "Zqcomponentbodymarker71"
DOC_REQUIREMENT = "Zqrequirementbodymarker72"
DOC_INTERFACE = "Zqinterfacebodymarker73"
DOC_ACCEPTANCE = "Zqacceptancebodymarker74"
DOC_CONSTRAINTS = "Zqconstraintsbodymarker75"

REQ_ID = "R-ZQWIDGET-001"
REQ_STATUS = "zqreqstatus81"
CRIT_ID = "AC-ZQWIDGET-001"
CRIT_KIND = "generated-test"
CRIT_RESULT = "zqcritresult82"

MODEL_PIN = "anthropic:zqmodelpin83"
PROMPT_VERSION = "zqpromptversion84"
GENERATED_AT = "2026-03-04T05:06:07Z"

SIZE_STATUS = "over"
PINNED_OVERRIDE = "zqpinnedfile85.py"
OWNER = "zqownerteam86"


def _build_graph():
    documents = {
        "acceptance/AC-ZQWIDGET-001.md": (
            "# AC-ZQWIDGET-001\n\nCovers: R-ZQWIDGET-001\n\n" + DOC_ACCEPTANCE + "\n"
        ),
        "component.md": (
            "---\nid: comp-zqwidget\ntitle: Zq Widget\nstatus: draft\n"
            "owners: [zqownerteam86]\nsealed: true\n---\n\n# Zq Widget\n\n"
            + DOC_COMPONENT
            + "\n"
        ),
        "constraints.md": "# Constraints\n\n" + DOC_CONSTRAINTS + "\n",
        "interface/library.md": "# Library\n\n" + DOC_INTERFACE + "\n",
        "requirements/R-ZQWIDGET-001.md": (
            "**R-ZQWIDGET-001** - " + DOC_REQUIREMENT + "\n"
        ),
    }
    component_node = {
        "type": "component",
        "verification": {
            "criteria": [
                {
                    "id": CRIT_ID,
                    "criterion_id": CRIT_ID,
                    "kind": CRIT_KIND,
                    "result": CRIT_RESULT,
                }
            ],
            "requirement_results": {REQ_ID: REQ_STATUS},
        },
        "provenance": {
            "model": MODEL_PIN,
            "prompt_version": PROMPT_VERSION,
            "generated_at": GENERATED_AT,
        },
        "size_status": SIZE_STATUS,
        "sealed": True,
        "pinned_overrides": [PINNED_OVERRIDE],
        "owners": [OWNER],
        "documents": documents,
    }
    nodes = {
        "P-ZQCAP": {"type": "capability"},
        COMP_ID: component_node,
    }
    edges = [{"from": COMP_ID, "to": "P-ZQCAP", "kind": "realizes"}]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def _detail_view_text(out_dir: Path) -> str:
    pages = [p for p in out_dir.rglob("*") if p.is_file()]
    html_pages = [p for p in pages if p.suffix.lower() in (".html", ".htm")]
    assert html_pages, f"no HTML pages rendered under {out_dir}: {pages}"

    by_name = [
        p
        for p in html_pages
        if SLUG in str(p.relative_to(out_dir)).lower()
    ]
    candidates = by_name
    if not candidates:
        candidates = [
            p
            for p in html_pages
            if DOC_COMPONENT in p.read_text(encoding="utf-8", errors="replace")
        ]
    assert candidates, (
        "could not locate the detail page for "
        + COMP_ID
        + f" among {[str(p) for p in html_pages]}"
    )
    raw = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in candidates)
    return html.unescape(raw)


def test_ac_docs_002_detail_view_includes_every_node_value(tmp_path):
    graph = _build_graph()
    out_dir = tmp_path / "site"

    docs_site_renderer.render_docs_site(graph, out_dir)

    assert out_dir.is_dir(), "render_docs_site did not create the output directory"
    text = _detail_view_text(out_dir)

    # documents: rendered component.md / requirements / interface / acceptance / constraints
    for marker in (
        DOC_COMPONENT,
        DOC_REQUIREMENT,
        DOC_INTERFACE,
        DOC_ACCEPTANCE,
        DOC_CONSTRAINTS,
    ):
        assert marker in text, f"document content {marker!r} missing from detail view"

    # verification.requirement_results: each R-id with its live status
    assert REQ_ID in text, "requirement id missing from detail view"
    assert REQ_STATUS in text, "requirement live status missing from detail view"

    # verification.criteria: criteria broken out by kind with their results
    assert CRIT_ID in text, "criterion id missing from detail view"
    assert CRIT_KIND in text, "criterion kind missing from detail view"
    assert CRIT_RESULT in text, "criterion result missing from detail view"

    # provenance: model pin, prompt version, last cold-regen timestamp
    assert MODEL_PIN in text, "provenance model pin missing from detail view"
    assert PROMPT_VERSION in text, "provenance prompt version missing from detail view"
    assert GENERATED_AT in text, "provenance timestamp missing from detail view"

    # size_status
    assert re.search(r"\bover\b", text, re.IGNORECASE), (
        "size_status value 'over' missing from detail view"
    )

    # sealed / pinned-override exemption status
    assert re.search(r"sealed", text, re.IGNORECASE), (
        "sealed exemption status missing from detail view"
    )
    assert PINNED_OVERRIDE in text, "pinned override missing from detail view"

    # owners
    assert OWNER in text, "owner missing from detail view"