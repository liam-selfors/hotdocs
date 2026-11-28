# hotdocs-criterion: sha256:ea9663a201242ee06719930f37e6f6c47f97b2135b144ca08e4167dfa0311119
"""AC-DOCS-002: a component's detail view shows every one of its node's values."""

import dataclasses
import html
import json
from html.parser import HTMLParser
from pathlib import Path

import docs_site_renderer


COMPONENT_ID = "comp-zqalpha"

DOC_TOKENS = {
    "component.md": "zqcomponentbodytoken",
    "requirements/R-ZQX-901.md": "zqrequirementbodytoken",
    "interface/library.md": "zqinterfacebodytoken",
    "acceptance/AC-ZQX-901.md": "zqacceptancebodytoken",
    "constraints.md": "zqconstraintsbodytoken",
}

DOCUMENTS = {
    "acceptance/AC-ZQX-901.md": "# AC-ZQX-901\n\nCovers: R-ZQX-901\n\nThe zqacceptancebodytoken holds.\n",
    "component.md": "---\nid: comp-zqalpha\ntitle: Zq Alpha\nstatus: draft\nowners: [zqowner-team, zqsecond-owner]\n---\n\n# Zq Alpha\n\nThe zqcomponentbodytoken describes it.\n",
    "constraints.md": "# Constraints\n\nThe zqconstraintsbodytoken applies.\n",
    "interface/library.md": "# Library\n\nThe zqinterfacebodytoken is exported.\n",
    "requirements/R-ZQX-901.md": "# R-ZQX-901\n\nThe zqrequirementbodytoken MUST hold.\n",
}

REQUIREMENT_RESULTS = {"R-ZQX-901": "passing", "R-ZQX-902": "failing"}

CRITERIA = [
    {"criterion_id": "AC-ZQX-901", "kind": "generated-test", "result": "passing", "covers": ["R-ZQX-901"]},
    {"criterion_id": "AC-ZQX-902", "kind": "compiled", "result": "failing", "covers": ["R-ZQX-902"]},
]

PROVENANCE = {
    "model": "anthropic:claude-zqpin-77",
    "prompt_version": "zqprompt-4242",
    "generated_at": "2031-07-19T03:04:05Z",
}

PINNED_OVERRIDES = ["zqpinnedfile.py"]
OWNERS = ["zqowner-team", "zqsecond-owner"]


@dataclasses.dataclass
class FakeCorpusGraph:
    nodes: dict
    edges: list
    aggregates: dict

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def make_graph():
    nodes = {
        "P-ZQCAP": {"type": "capability"},
        COMPONENT_ID: {
            "type": "component",
            "verification": {
                "criteria": [dict(c) for c in CRITERIA],
                "requirement_results": dict(REQUIREMENT_RESULTS),
            },
            "provenance": dict(PROVENANCE),
            "size_status": "over",
            "sealed": True,
            "pinned_overrides": list(PINNED_OVERRIDES),
            "owners": list(OWNERS),
            "documents": dict(sorted(DOCUMENTS.items())),
        },
    }
    edges = [{"from": COMPONENT_ID, "to": "P-ZQCAP", "kind": "realizes"}]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return FakeCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


class _NodeLinkFinder(HTMLParser):
    """Finds the href of the `a` inside the `li` whose data-id is the target."""

    def __init__(self, target):
        super().__init__()
        self.target = target
        self.in_target_li = 0
        self.href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li":
            if self.in_target_li:
                self.in_target_li += 1
            elif attrs.get("data-id") == self.target:
                self.in_target_li = 1
        elif tag == "a" and self.in_target_li and self.href is None:
            self.href = attrs.get("href")

    def handle_endtag(self, tag):
        if tag == "li" and self.in_target_li:
            self.in_target_li -= 1


class _PageReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texts = []
        self.attr_values = []
        self.size_spans = []
        self._span_stack = []
        self.tone_elements = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for v in attrs.values():
            if v:
                self.attr_values.append(v)
        classes = (attrs.get("class") or "").split()
        if any(c.startswith("tone-") for c in classes):
            self.tone_elements.append((tag, classes))
        if tag == "span":
            is_size = "size" in classes
            if is_size:
                self.size_spans.append({"classes": classes, "text": ""})
            self._span_stack.append(is_size)

    def handle_endtag(self, tag):
        if tag == "span" and self._span_stack:
            self._span_stack.pop()

    def handle_data(self, data):
        self.texts.append(data)
        if self._span_stack and any(self._span_stack) and self.size_spans:
            self.size_spans[-1]["text"] += data


def find_detail_page(out_dir):
    index = out_dir / "index.html"
    assert index.is_file(), "index.html not written"
    finder = _NodeLinkFinder(COMPONENT_ID)
    finder.feed(index.read_text(encoding="utf-8"))
    assert finder.href, "no link to the component's detail page in index.html"
    href = html.unescape(finder.href).split("#")[0].split("?")[0]
    page = (index.parent / href).resolve()
    assert page.is_file(), "detail page " + repr(str(page)) + " does not exist"
    return page


def test_ac_docs_002_detail_view_includes_every_value(tmp_path):
    out_dir = tmp_path / "site"
    graph = make_graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    page_path = find_detail_page(out_dir)
    raw = page_path.read_text(encoding="utf-8")
    reader = _PageReader()
    reader.feed(raw)
    text = " ".join(reader.texts)
    shown = text + " " + " ".join(reader.attr_values)

    # documents: each document's rendered content
    for doc, token in DOC_TOKENS.items():
        assert token in text, "content of " + doc + " missing from detail view"

    # verification.requirement_results: each R-id with its live status
    for rid, status in REQUIREMENT_RESULTS.items():
        assert rid in text, rid + " missing from detail view"
    assert "passing" in text
    assert "failing" in text

    # verification.criteria: each criterion, its kind and its result
    for crit in CRITERIA:
        assert crit["criterion_id"] in text, crit["criterion_id"] + " missing"
        assert crit["kind"] in text, "kind " + crit["kind"] + " missing"
        assert crit["result"] in text

    # provenance: model pin, prompt version, last cold-regen timestamp
    for key, value in PROVENANCE.items():
        assert value in shown, "provenance " + key + " value missing"

    # size_status: one span.size carrying the tone mapped from "over"
    assert len(reader.size_spans) == 1, reader.size_spans
    span = reader.size_spans[0]
    assert "tone-fail" in span["classes"], span
    assert "over" in span["text"], span
    assert len(reader.tone_elements) == 1, reader.tone_elements

    # sealed exemption status
    assert "sealed" in text.lower()

    # pinned_overrides
    for item in PINNED_OVERRIDES:
        assert item in text, "pinned override " + item + " missing"

    # owners
    for owner in OWNERS:
        assert owner in text, "owner " + owner + " missing"