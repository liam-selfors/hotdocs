import json
import re
from html.parser import HTMLParser

import provenance_tracker_ui


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _ElementCollector(HTMLParser):
    """Collects every element (attrs + aggregated inner text) in the page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._stack = []
        self.elements = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in _VOID_ELEMENTS:
            self.elements.append({"attrs": dict(attrs), "text": ""})
            return
        self._stack.append({"attrs": dict(attrs), "text": []})

    def handle_startendtag(self, tag, attrs):
        self.elements.append({"attrs": dict(attrs), "text": ""})

    def handle_endtag(self, tag):
        if not self._stack:
            return
        frame = self._stack.pop()
        text = "".join(frame["text"])
        self.elements.append({"attrs": frame["attrs"], "text": text})
        if self._stack:
            self._stack[-1]["text"].append(text)

    def handle_data(self, data):
        if self._stack:
            self._stack[-1]["text"].append(data)


def _element_mentions_id(element, node_id):
    pattern = re.compile(r"\b{}\b".format(re.escape(node_id)))
    for value in element["attrs"].values():
        if value and pattern.search(value):
            return True
    return bool(pattern.search(element["text"]))


_FAKE_TRACKER_TEMPLATE = '''
import json

_INVOCATIONS_FILE = __INVOCATIONS_FILE_REPR__


def _record(call, **fields):
    with open(_INVOCATIONS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": call, **fields}) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _record("check_readiness", changed_ids=changed_ids)
    return {
        "scope": "whole-corpus",
        "ready": False,
        "not_ready_reasons": [
            "comp-bar: verification overall is fail",
            "comp-qux: license_scan blocked",
            "P-ZERO-EDIT: capability scenario overall is fail",
        ],
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-bar": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-bar",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 0.4,
                    "overall": "fail",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-qux": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-qux",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": True},
                "secret_scan": {"flagged": False},
            },
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {"overall": "fail"},
            },
        },
    }


def last_requirement_failures(component_id, repo_root):
    _record("last_requirement_failures", component_id=component_id)
    return []
'''


def test_ac_ui_002_statuses_and_dom_attributes(tmp_path):
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "out"
    invocations_file = tmp_path / "invocations.jsonl"

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    tracker_source = _FAKE_TRACKER_TEMPLATE.replace(
        "__INVOCATIONS_FILE_REPR__", repr(str(invocations_file))
    )
    (tracker_dir / "provenance_tracker.py").write_text(tracker_source, encoding="utf-8")

    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True)
    corpus_graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
            },
            "comp-qux": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
            },
            "P-ZERO-EDIT": {"type": "capability"},
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (verification_dir / "corpus-graph.json").write_text(
        json.dumps(corpus_graph), encoding="utf-8"
    )

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert invocations_file.exists()
    invocation_calls = [
        json.loads(line)
        for line in invocations_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(c["call"] == "check_readiness" for c in invocation_calls)

    expected_statuses = {
        "comp-foo": "passing",
        "comp-bar": "failing",
        "comp-qux": "failing",
        "P-ZERO-EDIT": "failing",
    }

    nodes = _get(snapshot, "nodes")
    actual_statuses = {}
    for node in nodes:
        actual_statuses[_get(node, "id")] = _get(node, "status")

    for node_id, expected_status in expected_statuses.items():
        assert actual_statuses.get(node_id) == expected_status, (
            "unexpected status for {}: {!r}".format(node_id, actual_statuses.get(node_id))
        )

    index_html = out_dir / "index.html"
    assert index_html.exists()
    html_text = index_html.read_text(encoding="utf-8")

    collector = _ElementCollector()
    collector.feed(html_text)

    for node_id, expected_status in expected_statuses.items():
        candidates = [
            el
            for el in collector.elements
            if "data-status" in el["attrs"] and _element_mentions_id(el, node_id)
        ]
        assert candidates, "no rendered element found for node {}".format(node_id)
        assert any(
            el["attrs"].get("data-status") == expected_status
            and "status-{}".format(expected_status)
            in el["attrs"].get("class", "").split()
            for el in candidates
        ), "node {} has no element with matching data-status and status-<status> class".format(
            node_id
        )