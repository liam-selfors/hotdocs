# hotdocs-criterion: sha256:657ae7193273a63ed2a1c1bf23fcd50875a6fb74142cff22d2c068d8b5e8007e
import dataclasses
import html
import json
from html.parser import HTMLParser
from pathlib import Path

import docs_site_renderer


COMPONENT_ID = "comp-zetaquokka"


@dataclasses.dataclass
class FakeCorpusGraph:
    nodes: dict
    edges: list
    aggregates: dict

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def _component_node():
    return {
        "type": "component",
        "verification": {
            "criteria": [
                {
                    "id": "AC-ZETAQ-001",
                    "kind": "compiled",
                    "covers": ["R-ZETAQ-001"],
                    "result": "passing",
                },
                {
                    "id": "AC-ZETAQ-002",
                    "kind": "generated-test",
                    "covers": ["R-ZETAQ-002"],
                    "result": "failing",
                },
            ],
            "requirement_results": {
                "R-ZETAQ-001": "passing",
                "R-ZETAQ-002": "failing",
            },
        },
        "provenance": {
            "model": "anthropic:claude-zetapinmodel-9",
            "prompt_version": "promptver7731",
            "generated_at": "2026-03-04T05:06:07Z",
        },
        "size_status": "over",
        "sealed": True,
        "pinned_overrides": ["src/pinnedoverridemarker4412.py"],
        "owners": ["zetaownerteam5150"],
        "documents": {
            "acceptance/AC-ZETAQ-001.md": "# AC-ZETAQ-001\n\nCovers: R-ZETAQ-001\n\nAcceptanceMarkerOne\n",
            "acceptance/AC-ZETAQ-002.md": "# AC-ZETAQ-002\n\nCovers: R-ZETAQ-002\n\nAcceptanceMarkerTwo\n",
            "component.md": "---\nid: comp-zetaquokka\ntitle: Zeta\nstatus: draft\nowners: [zetaownerteam5150]\n---\n\n# Zeta\n\nComponentDocMarker8801\n",
            "constraints.md": "# Constraints\n\nConstraintsMarker2290\n",
            "interface/library.md": "# Library\n\nInterfaceMarker3317\n",
            "requirements/R-ZETAQ-001.md": "# R-ZETAQ-001\n\nRequirementMarkerOne\n",
            "requirements/R-ZETAQ-002.md": "# R-ZETAQ-002\n\nRequirementMarkerTwo\n",
        },
    }


class _NodeLinkFinder(HTMLParser):
    def __init__(self, target_id):
        super().__init__()
        self.target_id = target_id
        self.inside = False
        self.href = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if "node" in classes and a.get("data-id") == self.target_id:
            self.inside = True
            if tag == "a" and a.get("href") and self.href is None:
                self.href = a["href"]
            return
        if self.inside and tag == "a" and a.get("href") and self.href is None:
            self.href = a["href"]


class _SizeSpanFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.spans = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag != "span":
            return
        if self.current is not None:
            self.depth += 1
            return
        classes = (dict(attrs).get("class") or "").split()
        if "size" in classes:
            self.current = {"classes": classes, "text": ""}
            self.depth = 0

    def handle_endtag(self, tag):
        if tag != "span" or self.current is None:
            return
        if self.depth:
            self.depth -= 1
            return
        self.spans.append(self.current)
        self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data


def _detail_page(out_dir):
    index = (out_dir / "index.html").read_text(encoding="utf-8")
    finder = _NodeLinkFinder(COMPONENT_ID)
    finder.feed(index)
    assert finder.href, "no link to the component's detail page in index.html"
    href = finder.href.split("#")[0].split("?")[0]
    path = (out_dir / href).resolve()
    assert path.is_file(), "detail page not found: " + str(path)
    return path.read_text(encoding="utf-8")


def test_ac_docs_002_detail_view_shows_every_value(tmp_path):
    graph = FakeCorpusGraph(
        nodes={
            COMPONENT_ID: _component_node(),
            "P-ZETACAP": {"type": "capability"},
        },
        edges=[{"from": COMPONENT_ID, "to": "P-ZETACAP", "kind": "realizes"}],
        aggregates={
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    )
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(graph, out_dir)

    raw = _detail_page(out_dir)
    text = html.unescape(raw)

    # documents
    for marker in [
        "ComponentDocMarker8801",
        "RequirementMarkerOne",
        "RequirementMarkerTwo",
        "InterfaceMarker3317",
        "AcceptanceMarkerOne",
        "AcceptanceMarkerTwo",
        "ConstraintsMarker2290",
    ]:
        assert marker in text, marker

    # verification: requirement results and criteria by kind with results
    for value in [
        "R-ZETAQ-001",
        "R-ZETAQ-002",
        "AC-ZETAQ-001",
        "AC-ZETAQ-002",
        "compiled",
        "generated-test",
        "passing",
        "failing",
    ]:
        assert value in text, value

    # provenance
    for value in [
        "anthropic:claude-zetapinmodel-9",
        "promptver7731",
        "2026-03-04T05:06:07Z",
    ]:
        assert value in text, value

    # size_status, in its one size span with the mapped tone
    spans = _SizeSpanFinder()
    spans.feed(raw)
    assert len(spans.spans) == 1
    assert "tone-fail" in spans.spans[0]["classes"]
    assert "over" in html.unescape(spans.spans[0]["text"])

    # sealed / pinned overrides
    assert "sealed" in text.lower()
    assert "src/pinnedoverridemarker4412.py" in text

    # owners
    assert "zetaownerteam5150" in text