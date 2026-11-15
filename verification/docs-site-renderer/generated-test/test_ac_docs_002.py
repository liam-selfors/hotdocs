import docs_site_renderer

import html
import json
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class FakeCorpusGraph:
    """Matches the documented CorpusGraph shape: nodes, edges, aggregates,
    to_dict(), to_json_bytes()."""

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

    def __getitem__(self, key):
        return self.to_dict()[key]


COMP_ID = "comp-zedwidget"

DOC_COMPONENT = "zorblaxcomponenttext"
DOC_REQ = "womblerequirementtext"
DOC_IFACE = "quibbleinterfacetext"
DOC_ACC = "frindleacceptancetext"
DOC_CONSTRAINTS = "glorpconstraintstext"

REQ_ID = "R-ZEDWIDGET-001"
REQ_STATUS = "snarflestatus"

CRIT_ID = "AC-ZEDWIDGET-001"
CRIT_KIND = "generated-test"
CRIT_RESULT = "blorptresult"

MODEL_PIN = "anthropic:claude-zorbmodel-9"
PROMPT_VERSION = "pvquixotic42"
GENERATED_AT = "2031-02-03T04:05:06Z"

PINNED_FILE = "frobnicatorpinned.py"

OWNER_A = "teamwomblefrost"
OWNER_B = "teamquibberly"


def _graph():
    documents = {
        "acceptance/AC-ZEDWIDGET-001.md": (
            "# AC-ZEDWIDGET-001\n\nCovers: R-ZEDWIDGET-001\n\n"
            + DOC_ACC
            + "\n"
        ),
        "component.md": (
            "---\nid: comp-zedwidget\ntitle: Zed widget\nstatus: draft\n"
            "owners: [teamwomblefrost, teamquibberly]\n---\n\n# Zed widget\n\n"
            + DOC_COMPONENT
            + "\n"
        ),
        "constraints.md": "# Constraints\n\n" + DOC_CONSTRAINTS + "\n",
        "interface/library.md": "# Library\n\n" + DOC_IFACE + "\n",
        "requirements/R-ZEDWIDGET-001.md": (
            "# R-ZEDWIDGET-001\n\nThe widget MUST work. " + DOC_REQ + "\n"
        ),
    }
    nodes = {
        COMP_ID: {
            "type": "component",
            "verification": {
                "criteria": [
                    {
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
            "size_status": "over",
            "sealed": True,
            "pinned_overrides": [PINNED_FILE],
            "owners": [OWNER_A, OWNER_B],
            "documents": documents,
        },
    }
    return FakeCorpusGraph(
        nodes=nodes,
        edges=[],
        aggregates={
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 1.0,
            "orphan_var_rate": 0.0,
        },
    )


def _read_pages(out_dir: Path):
    pages = {}
    for p in out_dir.rglob("*"):
        if p.is_file():
            try:
                raw = p.read_bytes().decode("utf-8", errors="replace")
            except OSError:
                continue
            pages[p] = html.unescape(raw)
    return pages


def test_ac_docs_002_detail_view_shows_every_field(tmp_path):
    out_dir = tmp_path / "site"
    graph = _graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    assert out_dir.exists(), "render_docs_site did not create the output directory"
    pages = _read_pages(out_dir)
    assert pages, "render_docs_site wrote no files"

    candidates = {p: t for p, t in pages.items() if DOC_COMPONENT in t}
    assert candidates, (
        "no rendered page contains the component's component.md content; "
        f"files: {sorted(str(p.relative_to(out_dir)) for p in pages)}"
    )

    substring_expectations = {
        "documents component.md": DOC_COMPONENT,
        "documents requirements/": DOC_REQ,
        "documents interface/": DOC_IFACE,
        "documents acceptance/": DOC_ACC,
        "documents constraints.md": DOC_CONSTRAINTS,
        "requirement id": REQ_ID,
        "requirement live status": REQ_STATUS,
        "criterion id": CRIT_ID,
        "criterion kind": CRIT_KIND,
        "criterion result": CRIT_RESULT,
        "provenance model pin": MODEL_PIN,
        "provenance prompt version": PROMPT_VERSION,
        "provenance generated_at": GENERATED_AT,
        "pinned override": PINNED_FILE,
        "owner A": OWNER_A,
        "owner B": OWNER_B,
    }

    def missing_for(text):
        missing = [
            label for label, value in substring_expectations.items() if value not in text
        ]
        if not re.search(r"\bover\b", text, re.IGNORECASE):
            missing.append("size_status 'over'")
        if not re.search(r"\bsealed\b", text, re.IGNORECASE):
            missing.append("sealed exemption status")
        return missing

    results = {p: missing_for(t) for p, t in candidates.items()}
    complete = [p for p, m in results.items() if not m]
    assert complete, "no single detail page shows every value; missing per page: " + "; ".join(
        f"{p.relative_to(out_dir)}: {m}" for p, m in results.items()
    )