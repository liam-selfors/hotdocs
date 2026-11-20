# hotdocs-criterion: sha256:ec44f13e822400b04247792af881d2810683c5a9b5ffb02ab359ceedb05a6b8e
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

import provenance_tracker_ui


NODES = [
    {"id": "a", "status": "passing"},
    {"id": "b", "status": "failing"},
    {"id": "c", "status": "missing"},
    {"id": "d", "status": "not-attempted"},
    {"id": "e", "status": "passing"},
]

TABLE = [
    ("all", {"a": False, "b": False, "c": False, "d": False, "e": False}),
    ("passing", {"a": False, "b": True, "c": True, "d": True, "e": False}),
    ("failing", {"a": True, "b": False, "c": True, "d": True, "e": True}),
    ("missing", {"a": True, "b": True, "c": False, "d": True, "e": True}),
    ("not-attempted", {"a": True, "b": True, "c": True, "d": False, "e": True}),
    ("Passing", {"a": True, "b": True, "c": True, "d": True, "e": True}),
    ("bogus", {"a": True, "b": True, "c": True, "d": True, "e": True}),
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.mark.parametrize("filter_value,expected", TABLE)
def test_hidden_by_status_table(asset_runner, filter_value, expected):
    run = asset_runner("static/app.js")
    result = run("hiddenByStatus", [NODES, filter_value])
    assert result == expected


@pytest.mark.parametrize("filter_value", ["all", "passing"])
def test_hidden_by_status_empty_nodes(asset_runner, filter_value):
    run = asset_runner("static/app.js")
    result = run("hiddenByStatus", [[], filter_value])
    assert result == {}


def _verification_report(component_id, overall):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-X-001",
                "covers": "R-X-001",
                "kind": "compiled",
                "result": "pass" if overall == "pass" else "fail",
            }
        ],
        "requirement_results": {"R-X-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def _hit(component_id, overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": {"blocked": False},
        "secret_scan": {"flagged": False},
    }


def _miss():
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.node_elements = []

    def handle_starttag(self, tag, attrs):
        self._record(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._record(tag, attrs)

    def _record(self, tag, attrs):
        d = {}
        for k, v in attrs:
            d[k] = v
        if tag == "button" and "data-filter" in d:
            self.buttons.append(d)
        classes = (d.get("class") or "").split()
        if "node" in classes or "data-node-id" in d:
            self.node_elements.append((tag, d))


def test_rendered_page_filter_buttons(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-pass": _hit("comp-pass", "pass"),
            "comp-fail": _hit("comp-fail", "fail"),
            "comp-miss": _miss(),
            "comp-none": _miss(),
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-fail: verification failed",
            "comp-miss: no provenance for current spec state — run hotdocs generate comp-miss",
            "comp-none: no provenance for current spec state — run hotdocs generate comp-none",
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        "import json\n"
        "\n"
        "_REPORT = " + repr(json.dumps(report)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    report = json.loads(_REPORT)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return report\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    def comp_node():
        return {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {},
        }

    graph = {
        "nodes": {
            "comp-pass": comp_node(),
            "comp-fail": comp_node(),
            "comp-miss": comp_node(),
            "comp-none": comp_node(),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempt_dir = repo_root / ".hotdocs" / "attempts" / "comp-miss"
    attempt_dir.mkdir(parents=True)
    attempt = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": "comp-miss",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "generation": {
            "component_id": "comp-miss",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"foo.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": _verification_report("comp-miss", "fail"),
    }
    (attempt_dir / "2026-10-25T14:32:01Z-a1b2c3.json").write_text(
        json.dumps(attempt), encoding="utf-8"
    )

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    statuses = {}
    for node in field(snapshot, "nodes"):
        statuses[field(node, "id")] = field(node, "status")
    assert statuses == {
        "comp-fail": "failing",
        "comp-miss": "missing",
        "comp-none": "not-attempted",
        "comp-pass": "passing",
    }

    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    parser = _Collector()
    parser.feed(html_text)
    parser.close()

    filters = [b["data-filter"] for b in parser.buttons]
    assert filters == ["all", "passing", "failing", "missing", "not-attempted"]

    assert parser.node_elements, "expected node elements in the page"
    node_ids = set()
    for tag, attrs in parser.node_elements:
        assert "hidden" not in attrs, (tag, attrs)
        if "data-node-id" in attrs:
            node_ids.add(attrs["data-node-id"])
    assert {"comp-pass", "comp-fail", "comp-miss", "comp-none"} <= node_ids