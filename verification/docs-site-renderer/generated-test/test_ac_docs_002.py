# hotdocs-criterion: sha256:0ff6f223686dccbc5c9f5db7dc4b02fed3ca45c10194385d2648c89d0843d0f8
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import docs_site_renderer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        import json

        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
            + "\n"
        ).encode("utf-8")


COMPONENT_ID = "comp-zqwidget"

DOC_COMPONENT = "zqcomponenttext4411"
DOC_REQUIREMENT = "zqrequirementtext4412"
DOC_INTERFACE = "zqinterfacetext4413"
DOC_ACCEPTANCE = "zqacceptancetext4414"
DOC_CONSTRAINTS = "zqconstraintstext4415"

REQ_ID = "R-ZQWIDGET-001"
REQ_STATUS = "zqreqstatus4421"
CRIT_ID = "AC-ZQWIDGET-001"
CRIT_KIND = "generated-test"
CRIT_RESULT = "zqcritresult4422"

MODEL_PIN = "anthropic:zqmodelpin4431"
PROMPT_VERSION = "zqpromptversion4432"
GENERATED_AT = "2026-03-04T05:06:07Z"

SIZE_STATUS = "over"
PINNED_OVERRIDE = "zqpinnedoverride4441"
OWNER = "zqownerteam4451"


def build_graph():
    component_md = (
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Zq Widget\n"
        "status: draft\n"
        "owners: [" + OWNER + "]\n"
        "sealed: true\n"
        "source_path: legacy/zqwidget/\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "---\n"
        "\n"
        "# Zq Widget\n"
        "\n"
        "Purpose " + DOC_COMPONENT + " here.\n"
    )
    documents = {
        "acceptance/AC-ZQWIDGET-001.md": (
            "# " + CRIT_ID + "\n\nCovers: " + REQ_ID + "\n\nText " + DOC_ACCEPTANCE + " here.\n"
        ),
        "component.md": component_md,
        "constraints.md": "# Constraints\n\nText " + DOC_CONSTRAINTS + " here.\n",
        "interface/library.md": "# Library\n\nText " + DOC_INTERFACE + " here.\n",
        "requirements/R-ZQWIDGET-001.md": (
            "**" + REQ_ID + "** - Text " + DOC_REQUIREMENT + " here.\n"
        ),
    }
    node = {
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
        "size_status": SIZE_STATUS,
        "sealed": True,
        "pinned_overrides": [PINNED_OVERRIDE],
        "owners": [OWNER],
        "documents": documents,
    }
    return FakeCorpusGraph(
        nodes={COMPONENT_ID: node},
        edges=[],
        aggregates={
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    )


def _read_text_files(out_dir):
    result = {}
    for p in sorted(Path(out_dir).rglob("*")):
        if p.is_file():
            try:
                result[p] = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
    return result


def test_detail_view_includes_every_component_field_value(tmp_path):
    graph = build_graph()
    out_dir = tmp_path / "out"

    docs_site_renderer.render_docs_site(graph, out_dir)

    assert out_dir.is_dir(), "render_docs_site did not create out_dir"
    files = _read_text_files(out_dir)
    assert files, "render_docs_site wrote no files"

    plain_values = [
        DOC_COMPONENT,
        DOC_REQUIREMENT,
        DOC_INTERFACE,
        DOC_ACCEPTANCE,
        DOC_CONSTRAINTS,
        REQ_ID,
        REQ_STATUS,
        CRIT_ID,
        CRIT_KIND,
        CRIT_RESULT,
        MODEL_PIN,
        PROMPT_VERSION,
        GENERATED_AT,
        PINNED_OVERRIDE,
        OWNER,
    ]

    def missing_in(text):
        missing = [v for v in plain_values if v not in text]
        if not re.search(r"\b" + re.escape(SIZE_STATUS) + r"\b", text):
            missing.append("size_status=" + SIZE_STATUS)
        if "sealed" not in text.lower():
            missing.append("sealed")
        return missing

    candidates = {p: t for p, t in files.items() if DOC_COMPONENT in t}
    assert candidates, (
        "no rendered file contains the component's component.md content; files: "
        + repr([str(p.relative_to(out_dir)) for p in files])
    )

    report = {}
    for p, text in candidates.items():
        missing = missing_in(text)
        if not missing:
            return
        report[str(p.relative_to(out_dir))] = missing

    raise AssertionError(
        "no detail view for " + COMPONENT_ID + " includes every value; missing per file: "
        + repr(report)
    )