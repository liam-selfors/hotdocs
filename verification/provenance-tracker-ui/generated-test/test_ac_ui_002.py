# hotdocs-criterion: sha256:a0635e41972096b43558224eeed433365c345d5b5dc317b8b150bd6c68936023
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_SOURCE = '''
import json
from pathlib import Path

LOG_PATH = __LOG_PATH__


def _log(line):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\\n")


def _vr(component_id, overall):
    fail = overall != "pass"
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-X-001",
                "covers": "R-X-001",
                "kind": "generated-test",
                "result": "fail" if fail else "pass",
            }
        ],
        "requirement_results": {"R-X-001": "fail" if fail else "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": overall,
    }


def _hit(component_id, overall, blocked, flagged):
    return {
        "hit": True,
        "verification_report": _vr(component_id, overall),
        "license_scan": {"blocked": blocked, "findings": []},
        "secret_scan": {"flagged": flagged, "findings": []},
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _hit("comp-foo", "pass", False, False),
            "comp-bar": _hit("comp-bar", "fail", False, False),
            "comp-qux": _hit("comp-qux", "pass", True, False),
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
    _log("last_requirement_failures " + str(component_id))
    return []


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-000000",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": verification_report,
    }
'''


def _corpus_graph():
    def comp():
        return {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["team"],
            "documents": {},
        }

    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-bar": comp(),
            "comp-foo": comp(),
            "comp-qux": comp(),
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _StatusCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.stack = []

    def _record(self, tag, attrs):
        attr_map = {k: (v if v is not None else "") for k, v in attrs}
        el = None
        if "data-status" in attr_map:
            el = {"tag": tag, "attrs": attr_map, "text": ""}
            self.elements.append(el)
        return el

    def handle_starttag(self, tag, attrs):
        el = self._record(tag, attrs)
        if tag in VOID_TAGS:
            return
        self.stack.append((tag, el))

    def handle_startendtag(self, tag, attrs):
        self._record(tag, attrs)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for _, el in self.stack:
            if el is not None:
                el["text"] += data


def _elements_for(elements, node_id):
    by_attr = [
        el for el in elements
        if any(k != "data-status" and v == node_id for k, v in el["attrs"].items())
    ]
    if by_attr:
        return by_attr
    by_attr_token = [
        el for el in elements
        if any(
            k not in ("data-status", "class") and node_id in v.split()
            for k, v in el["attrs"].items()
        )
    ]
    if by_attr_token:
        return by_attr_token
    by_text = [el for el in elements if node_id in el["text"]]
    if not by_text:
        return []
    # prefer the innermost (shortest-text) matching elements
    min_len = min(len(el["text"]) for el in by_text)
    return [el for el in by_text if len(el["text"]) == min_len]


def test_ac_ui_002_statuses_map_report_fields(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker-calls.log"

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = FAKE_TRACKER_SOURCE.replace("__LOG_PATH__", repr(str(log_path)))
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    expected = {
        "comp-foo": "passing",
        "comp-bar": "failing",
        "comp-qux": "failing",
        "P-ZERO-EDIT": "failing",
    }

    nodes = field(snapshot, "nodes")
    statuses = {field(n, "id"): field(n, "status") for n in nodes}
    assert set(statuses) == set(expected)
    for node_id, status in expected.items():
        assert statuses[node_id] == status, (node_id, statuses[node_id])

    html_path = Path(out_dir) / "index.html"
    assert html_path.is_file()
    parser = _StatusCollector()
    parser.feed(html_path.read_text(encoding="utf-8"))
    parser.close()
    assert parser.elements, "no element carries a data-status attribute"

    for node_id, snap_status in statuses.items():
        els = _elements_for(parser.elements, node_id)
        assert els, "no node element with data-status found for " + node_id
        for el in els:
            assert el["attrs"]["data-status"] == snap_status, (node_id, el["attrs"])
            classes = el["attrs"].get("class", "").split()
            assert "status-" + snap_status in classes, (node_id, classes)