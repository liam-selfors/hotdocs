# hotdocs-criterion: sha256:a0bf5ad040410e0acd2552aefdefd676fdf4b0520e7e0e133ea2db846f1b37bc
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

EXPECTED = [
    ("all", {"a": False, "b": False, "c": False, "d": False, "e": False}),
    ("passing", {"a": False, "b": True, "c": True, "d": True, "e": False}),
    ("failing", {"a": True, "b": False, "c": True, "d": True, "e": True}),
    ("missing", {"a": True, "b": True, "c": False, "d": True, "e": True}),
    ("not-attempted", {"a": True, "b": True, "c": True, "d": False, "e": True}),
    ("Passing", {"a": True, "b": True, "c": True, "d": True, "e": True}),
    ("bogus", {"a": True, "b": True, "c": True, "d": True, "e": True}),
]


@pytest.mark.parametrize("flt,expected", EXPECTED)
def test_hidden_by_status_table(asset_runner, flt, expected):
    run = asset_runner("static/app.js")
    nodes = [dict(n) for n in NODES]
    result = run("hiddenByStatus", [nodes, flt])
    assert result == expected


def test_hidden_by_status_empty_nodes(asset_runner):
    run = asset_runner("static/app.js")
    assert run("hiddenByStatus", [[], "all"]) == {}
    assert run("hiddenByStatus", [[], "passing"]) == {}


# ---------------------------------------------------------------------------
# Rendered page: filter buttons and initial visibility
# ---------------------------------------------------------------------------

PASSING_ID = "comp-alpha"
FAILING_ID = "comp-bravo"
MISSING_ID = "comp-charlie"
NOT_ATTEMPTED_ID = "comp-delta"


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _verification_report(component_id, overall):
    rid = "R-" + component_id.upper().replace("COMP-", "") + "-001"
    result = "pass" if overall == "pass" else "fail"
    criterion = {
        "id": "AC-" + component_id.upper().replace("COMP-", "") + "-001",
        "covers": rid,
        "kind": "compiled",
        "result": result,
    }
    if result == "fail":
        criterion["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
        "requirement_results": {rid: result},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def _hit(component_id, overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": {"blocked": False, "flagged": False, "matches": []},
        "secret_scan": _secret_scan(),
    }


def _miss():
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def _verify_report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            PASSING_ID: _hit(PASSING_ID, "pass"),
            FAILING_ID: _hit(FAILING_ID, "fail"),
            MISSING_ID: _miss(),
            NOT_ATTEMPTED_ID: _miss(),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            FAILING_ID + ": verification failed",
            MISSING_ID + ": no provenance for current spec state — run hotdocs generate " + MISSING_ID,
            NOT_ATTEMPTED_ID + ": no provenance for current spec state — run hotdocs generate " + NOT_ATTEMPTED_ID,
        ],
    }


def _attempt_record(component_id):
    return {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": component_id,
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "generation": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"x.py": "print(1)\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": _verification_report(component_id, "fail"),
    }


def _component_graph_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "unknown",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _build_repo(repo_root):
    # Fake provenance-tracker dependency (flat module shape).
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    report_json = json.dumps(_verify_report())
    source = (
        "import json\n"
        "_REPORT = " + repr(report_json) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return json.loads(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    # Corpus graph topology.
    graph = {
        "nodes": {
            PASSING_ID: _component_graph_node(),
            FAILING_ID: _component_graph_node(),
            MISSING_ID: _component_graph_node(),
            NOT_ATTEMPTED_ID: _component_graph_node(),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    ver = repo_root / "verification"
    ver.mkdir(parents=True)
    (ver / "corpus-graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")

    # Attempt history: only the "missing" component has an attempt.
    attempts = repo_root / ".hotdocs" / "attempts" / MISSING_ID
    attempts.mkdir(parents=True)
    (attempts / "2026-10-25T14:32:01Z-a1b2c3.json").write_text(
        json.dumps(_attempt_record(MISSING_ID), indent=2), encoding="utf-8"
    )


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.filter_buttons = []
        self.node_elements = []

    def handle_starttag(self, tag, attrs):
        attr_map = {}
        for name, value in attrs:
            attr_map[name] = value
        if tag == "button" and "data-filter" in attr_map:
            self.filter_buttons.append(attr_map)
        classes = (attr_map.get("class") or "").split()
        if tag == "li" and "node" in classes:
            self.node_elements.append(attr_map)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def test_rendered_page_has_five_filter_buttons_and_nothing_hidden(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    out_dir = tmp_path / "out"

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    parser = _PageParser()
    parser.feed(html_text)
    parser.close()

    filters = [b["data-filter"] for b in parser.filter_buttons]
    assert filters == ["all", "passing", "failing", "missing", "not-attempted"]

    # One node element per status, none hidden on load.
    statuses = sorted(n.get("data-status") for n in parser.node_elements)
    assert statuses == sorted(["passing", "failing", "missing", "not-attempted"])
    for node in parser.node_elements:
        assert "hidden" not in node, node