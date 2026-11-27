# hotdocs-criterion: sha256:7534f2c861dd6b10f5baa30c386ca525e42b7d8a398e90f043a9daf5d79601d3
import html
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import docs_site_renderer


@dataclass
class CorpusGraph:
    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        import json

        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


COMPONENT_ID = "comp-zedwidget"

DOCUMENTS = {
    "acceptance/AC-ZED-001.md": "# AC-ZED-001\n\nCovers: R-ZED-001\n\nAcceptancetextquokka4417\n",
    "acceptance/AC-ZED-002.md": "# AC-ZED-002\n\nCovers: R-ZED-002\n\nAcceptancetextwombat8832\n",
    "component.md": "---\nid: comp-zedwidget\ntitle: Zed Widget\nstatus: draft\nowners: [ownerteamalpha, ownerteambeta]\n---\n\n# Zed Widget\n\nComponenttextpangolin2291\n",
    "constraints.md": "# Constraints\n\nConstrainttextnarwhal5563\n",
    "interface/library.md": "# Library\n\nInterfacetextaxolotl7718\n",
    "requirements/R-ZED-001.md": "# R-ZED-001\n\nRequirementtextokapi3394\n",
    "requirements/R-ZED-002.md": "# R-ZED-002\n\nRequirementtextcapybara6620\n",
}

VERIFICATION = {
    "requirement_results": {
        "R-ZED-001": "reqstatusalpha91",
        "R-ZED-002": "reqstatusbeta92",
    },
    "criteria": [
        {"id": "AC-ZED-001", "kind": "generated-test", "result": "critresultgamma93"},
        {"id": "AC-ZED-002", "kind": "compiled", "result": "critresultdelta94"},
    ],
}

PROVENANCE = {
    "model": "anthropic:claude-zebramodel-77",
    "prompt_version": "promptversionqx41",
    "generated_at": "2031-04-05T06:07:08Z",
    "last_cold_regen_at": "2032-09-10T11:12:13Z",
}

PINNED = ["pinnedfilezq83.py"]
OWNERS = ["ownerteamalpha", "ownerteambeta"]


def _graph():
    nodes = {
        "P-ZEDCAP": {"type": "capability"},
        COMPONENT_ID: {
            "type": "component",
            "verification": VERIFICATION,
            "provenance": PROVENANCE,
            "size_status": "over",
            "sealed": True,
            "pinned_overrides": PINNED,
            "owners": OWNERS,
            "documents": DOCUMENTS,
        },
        "VAR-ZED-URL": {"type": "var"},
    }
    edges = [
        {"from": COMPONENT_ID, "to": "P-ZEDCAP", "kind": "realizes"},
        {"from": COMPONENT_ID, "to": "VAR-ZED-URL", "kind": "uses_var"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def _expected_values():
    values = [
        "Componenttextpangolin2291",
        "Requirementtextokapi3394",
        "Requirementtextcapybara6620",
        "Interfacetextaxolotl7718",
        "Acceptancetextquokka4417",
        "Acceptancetextwombat8832",
        "Constrainttextnarwhal5563",
        "R-ZED-001",
        "R-ZED-002",
        "reqstatusalpha91",
        "reqstatusbeta92",
        "AC-ZED-001",
        "AC-ZED-002",
        "generated-test",
        "compiled",
        "critresultgamma93",
        "critresultdelta94",
        "anthropic:claude-zebramodel-77",
        "promptversionqx41",
        "2031-04-05T06:07:08Z",
        "2032-09-10T11:12:13Z",
        "over",
        "sealed",
        "pinnedfilezq83.py",
        "ownerteamalpha",
        "ownerteambeta",
    ]
    return values


def test_ac_docs_002_detail_view_shows_every_field(tmp_path):
    out_dir = tmp_path / "site"
    result = docs_site_renderer.render_docs_site(_graph(), out_dir)
    assert result is None

    pages = sorted(p for p in Path(out_dir).rglob("*.html") if p.is_file())
    assert pages, "no HTML pages were rendered"

    expected = _expected_values()
    best_missing = None
    for page in pages:
        text = html.unescape(page.read_text(encoding="utf-8"))
        if COMPONENT_ID not in text:
            continue
        missing = [v for v in expected if v not in text]
        if not missing:
            return
        if best_missing is None or len(missing) < len(best_missing):
            best_missing = missing

    assert best_missing is not None, "no page mentions " + COMPONENT_ID
    assert best_missing == [], (
        "the detail view of " + COMPONENT_ID + " is missing values: " + repr(best_missing)
    )