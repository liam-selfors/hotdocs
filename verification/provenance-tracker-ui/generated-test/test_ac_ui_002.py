import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


NODE_IDS = ["P-ZERO-EDIT", "comp-bar", "comp-foo", "comp-qux"]

EXPECTED = {
    "comp-foo": "passing",
    "comp-bar": "failing",
    "comp-qux": "failing",
    "P-ZERO-EDIT": "failing",
}


FAKE_TRACKER_TEMPLATE = r'''
import json
from pathlib import Path

_LOG = Path(__LOG_PATH__)


def _log(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _verification_report(component_id, r_id, overall):
    result = "pass" if overall == "pass" else "fail"
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-" + r_id[2:], "covers": r_id, "kind": "compiled", "result": result}
        ],
        "requirement_results": {r_id: result},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": overall,
    }


def _hit(component_id, r_id, overall, license_blocked=False, secret_flagged=False):
    return {
        "hit": True,
        "verification_report": _verification_report(component_id, r_id, overall),
        "license_scan": {"blocked": license_blocked, "findings": []},
        "secret_scan": {"flagged": secret_flagged, "findings": []},
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({
        "fn": "check_readiness",
        "repo_root": str(repo_root),
        "changed_ids": changed_ids,
        "model": model,
        "seed": seed,
    })
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _hit("comp-foo", "R-FOO-001", "pass"),
            "comp-bar": _hit("comp-bar", "R-BAR-001", "fail"),
            "comp-qux": _hit("comp-qux", "R-QUX-001", "pass", license_blocked=True),
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
    _log({"fn": "last_requirement_failures", "component_id": component_id})
    return []


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    raise AssertionError("write_attempt_record must not be called by the UI")
'''


def _component_graph_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["test-team"],
        "documents": {},
    }


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.jsonl"

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path))),
        encoding="utf-8",
    )

    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-bar": _component_graph_node(),
            "comp-foo": _component_graph_node(),
            "comp-qux": _component_graph_node(),
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
    vdir = repo_root / "verification"
    vdir.mkdir()
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return repo_root, log_path


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class _StatusElementCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []  # list of (tag, record_or_None)
        self.records = []

    def handle_starttag(self, tag, attrs):
        attr_map = {k: (v if v is not None else "") for k, v in attrs}
        record = None
        if "data-status" in attr_map:
            record = {"tag": tag, "attrs": attr_map, "text": []}
            self.records.append(record)
        if tag in VOID_TAGS:
            return
        self.stack.append((tag, record))

    def handle_startendtag(self, tag, attrs):
        attr_map = {k: (v if v is not None else "") for k, v in attrs}
        if "data-status" in attr_map:
            self.records.append({"tag": tag, "attrs": attr_map, "text": []})

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for _, record in self.stack:
            if record is not None:
                record["text"].append(data)


def _ids_by_attr(record):
    found = set()
    for name, value in record["attrs"].items():
        if name in ("class", "data-status"):
            continue
        for node_id in NODE_IDS:
            if value == node_id or value.endswith(node_id):
                found.add(node_id)
    return found


def _ids_by_text(record):
    text = "".join(record["text"])
    return {node_id for node_id in NODE_IDS if node_id in text}


def test_ac_ui_002_statuses_map_directly_and_render_matching_attributes(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The faked provenance-tracker was actually consulted, exactly once.
    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    readiness_calls = [c for c in calls if c["fn"] == "check_readiness"]
    assert len(readiness_calls) == 1

    # Snapshot statuses.
    nodes = field(snapshot, "nodes")
    statuses = {field(n, "id"): field(n, "status") for n in nodes}
    assert set(statuses) == set(EXPECTED)
    for node_id, expected_status in EXPECTED.items():
        assert statuses[node_id] == expected_status, (node_id, statuses[node_id])

    # Rendered page: each node element's data-status and status-<status> class.
    index = Path(out_dir) / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    parser = _StatusElementCollector()
    parser.feed(html)
    parser.close()
    records = parser.records
    assert records, "no element carrying a data-status attribute was rendered"

    use_attrs = any(_ids_by_attr(r) for r in records)
    by_node = {node_id: [] for node_id in NODE_IDS}
    for record in records:
        if use_attrs:
            ids = _ids_by_attr(record)
        else:
            ids = _ids_by_text(record)
            if len(ids) != 1:
                continue
        for node_id in ids:
            by_node[node_id].append(record)

    for node_id in NODE_IDS:
        elements = by_node[node_id]
        assert elements, "no node element with data-status found for %s" % node_id
        snapshot_status = statuses[node_id]
        for element in elements:
            assert element["attrs"]["data-status"] == snapshot_status, (
                node_id, element["attrs"]
            )
            classes = element["attrs"].get("class", "").split()
            assert "status-" + snapshot_status in classes, (node_id, element["attrs"])