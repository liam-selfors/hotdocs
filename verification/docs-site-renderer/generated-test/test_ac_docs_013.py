# hotdocs-criterion: sha256:b34d6c4c4f71b31a27fac1c26ae71d5874a0524e48d962b8061e44b42d49470d
import re
from dataclasses import dataclass, field as dc_field
import json
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
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def _component_node(size_status):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": size_status,
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _graph():
    nodes = {
        "comp-alpha": _component_node("ok"),
        "comp-beta": _component_node("over"),
        "P-ALPHA": {"type": "capability"},
    }
    edges = [
        {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
        {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
    ]
    edges.sort(key=lambda e: (e["from"], e["to"], e["kind"]))
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def test_ac_docs_013_every_page_has_single_style_in_head(tmp_path):
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(_graph(), out_dir)

    html_files = sorted(p for p in out_dir.rglob("*.html") if p.is_file())
    assert html_files, "no .html files were written"
    rels = {p.relative_to(out_dir).as_posix() for p in html_files}
    for expected in (
        "index.html",
        "dashboard.html",
        "nodes/comp-alpha.html",
        "nodes/comp-beta.html",
        "nodes/P-ALPHA.html",
    ):
        assert expected in rels, expected + " not written; got " + repr(sorted(rels))

    for path in html_files:
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(out_dir).as_posix()

        assert text.count("<style") == 1, name + ": expected exactly one <style"

        head_match = re.search(r"<head[\s>]", text)
        assert head_match is not None, name + ": no <head"
        head_start = head_match.start()
        head_end = text.find("</head>")
        assert head_end != -1, name + ": no </head>"

        style_start = text.index("<style")
        assert head_start < style_start < head_end, name + ": <style not inside <head>"

        open_end = text.index(">", style_start)
        close = text.find("</style>", open_end)
        assert close != -1, name + ": <style> not closed"
        assert close < head_end, name + ": </style> not inside <head>"
        style_text = text[open_end + 1:close]
        assert ".tone-ok" in style_text, name + ": style lacks .tone-ok"
        assert "--color-bg" in style_text, name + ": style lacks --color-bg"

        assert " style=" not in text, name + ": holds a style= attribute"
        assert "<link" not in text, name + ": holds a <link element"