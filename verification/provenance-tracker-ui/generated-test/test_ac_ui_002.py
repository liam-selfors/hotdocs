import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


NODE_IDS = ["P-ZERO-EDIT", "comp-bar", "comp-foo", "comp-qux"]

EXPECTED_STATUSES = {
    "comp-foo": "passing",
    "comp-bar": "failing",
    "comp-qux": "failing",
    "P-ZERO-EDIT": "failing",
}


FAKE_TRACKER_TEMPLATE = r'''
import json
from pathlib import Path

_LOG = __LOG_PATH__


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _verification_report(component_id, overall, requirement_results):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-" + component_id[len("comp-"):].upper() + "-001",
                "covers": list(requirement_results)[0],
                "kind": "compiled",
                "result": "pass" if overall == "pass" else "fail",
            }
        ],
        "requirement_results": dict(requirement_results),
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": overall,
    }


def _license_scan(blocked):
    return {"blocked": blocked, "findings": []}


def _secret_scan(flagged):
    return {"flagged": flagged, "findings": []}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({
        "fn": "check_readiness",
        "repo_root": str(repo_root),
        "changed_ids": changed_ids,
        "model": model,
        "seed": seed,
        "llm_backend_is_none": llm_backend is None,
    })
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(
                    "comp-foo", "pass", {"R-FOO-001": "pass"}
                ),
                "license_scan": _license_scan(False),
                "secret_scan": _secret_scan(False),
            },
            "comp-bar": {
                "hit": True,
                "verification_report": _verification_report(
                    "comp-bar", "fail", {"R-BAR-001": "fail"}
                ),
                "license_scan": _license_scan(False),
                "secret_scan": _secret_scan(False),
            },
            "comp-qux": {
                "hit": True,
                "verification_report": _verification_report(
                    "comp-qux", "pass", {"R-QUX-001": "pass"}
                ),
                "license_scan": _license_scan(True),
                "secret_scan": _secret_scan(False),
            },
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ZERO-EDIT": {"overall": "fail", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [
            "comp-bar: verification failed",
            "comp-qux: license scan blocked",
            "P-ZERO-EDIT: capability scenarios failed",
        ],
    }


def last_requirement_failures(component_id, repo_root):
    _log({
        "fn": "last_requirement_failures",
        "component_id": component_id,
        "repo_root": str(repo_root),
    })
    return []


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    raise AssertionError("write_attempt_record must not be called by the UI")


def main(argv=None):
    return 2
'''


def _component_graph_node(component_id):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["test-team"],
        "documents": {"component.md": "---\nid: " + component_id + "\n---\n"},
    }


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-bar": _component_graph_node("comp-bar"),
            "comp-foo": _component_graph_node("comp-foo"),
            "comp-qux": _component_graph_node("comp-qux"),
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
    path = repo_root / "verification" / "corpus-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = FAKE_TRACKER_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path)))
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class _StatusElementCollector(HTMLParser):
    """Collects every element carrying a data-status attribute, with its
    attributes and its full text content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.elements = []
        self._raw_text_depth = 0

    def _open(self, tag, attrs, self_closing):
        attr_dict = {}
        for name, value in attrs:
            attr_dict[name.lower()] = value if value is not None else ""
        record = {"tag": tag, "attrs": attr_dict, "text": []}
        if "data-status" in attr_dict:
            self.elements.append(record)
        if tag in VOID_TAGS or self_closing:
            return
        self.stack.append(record)
        if tag in ("script", "style"):
            self._raw_text_depth += 1

    def handle_starttag(self, tag, attrs):
        self._open(tag.lower(), attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._open(tag.lower(), attrs, True)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                for rec in self.stack[i:]:
                    if rec["tag"] in ("script", "style"):
                        self._raw_text_depth -= 1
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self._raw_text_depth:
            return
        for rec in self.stack:
            rec["text"].append(data)


_ID_PREFIXES = ("#", "node-", "node_", "node:")


def _attr_node_id(attrs):
    for name, value in attrs.items():
        if name in ("class", "data-status", "style"):
            continue
        candidate = value.strip()
        if candidate in NODE_IDS:
            return candidate
        for prefix in _ID_PREFIXES:
            if candidate.startswith(prefix) and candidate[len(prefix):] in NODE_IDS:
                return candidate[len(prefix):]
    return None


def _text_node_id(text):
    present = [nid for nid in NODE_IDS if nid in text]
    if len(present) == 1:
        return present[0]
    return None


def test_ac_ui_002_statuses_map_report_fields_and_mark_node_elements(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    log_path = tmp_path / "fake_tracker_calls.jsonl"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake provenance-tracker was the one consulted.
    assert log_path.exists(), "fake provenance-tracker was never invoked"
    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    readiness_calls = [c for c in calls if c["fn"] == "check_readiness"]
    assert len(readiness_calls) == 1

    # Snapshot statuses are the direct mapping of the VerifyReport fields.
    nodes = field(snapshot, "nodes")
    statuses = {field(n, "id"): field(n, "status") for n in nodes}
    assert statuses == EXPECTED_STATUSES

    # Each node element's data-status and status-<status> class match.
    index_html = out_dir / "index.html"
    assert index_html.is_file()
    html = index_html.read_text(encoding="utf-8")

    collector = _StatusElementCollector()
    collector.feed(html)
    collector.close()

    assert collector.elements, "no element carries a data-status attribute"

    matched = {nid: [] for nid in NODE_IDS}
    for el in collector.elements:
        nid = _attr_node_id(el["attrs"])
        if nid is None:
            nid = _text_node_id("".join(el["text"]))
        if nid is not None:
            matched[nid].append(el)

    for nid, expected_status in EXPECTED_STATUSES.items():
        elements = matched[nid]
        assert elements, "no node element with data-status found for %s" % nid
        for el in elements:
            assert el["attrs"]["data-status"] == expected_status, (
                "%s: data-status %r != %r"
                % (nid, el["attrs"]["data-status"], expected_status)
            )
            classes = el["attrs"].get("class", "").split()
            assert "status-" + expected_status in classes, (
                "%s: class %r lacks status-%s" % (nid, classes, expected_status)
            )
            for other in ("passing", "failing", "missing", "not-attempted"):
                if other != expected_status:
                    assert "status-" + other not in classes, (
                        "%s: unexpected class status-%s" % (nid, other)
                    )