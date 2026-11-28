# hotdocs-criterion: sha256:f7a7dca463a324403e060aca0eaf4d55149f44c2fff6745eb570b2fe9df6fdf0
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


NODES = [
    {"id": "a", "status": "passing"},
    {"id": "b", "status": "failing"},
    {"id": "c", "status": "missing"},
    {"id": "d", "status": "not-attempted"},
    {"id": "e", "status": "passing"},
]


@pytest.mark.parametrize(
    "flt, expected",
    [
        ("all", {"a": False, "b": False, "c": False, "d": False, "e": False}),
        ("passing", {"a": False, "b": True, "c": True, "d": True, "e": False}),
        ("failing", {"a": True, "b": False, "c": True, "d": True, "e": True}),
        ("missing", {"a": True, "b": True, "c": False, "d": True, "e": True}),
        ("not-attempted", {"a": True, "b": True, "c": True, "d": False, "e": True}),
        ("Passing", {"a": True, "b": True, "c": True, "d": True, "e": True}),
        ("bogus", {"a": True, "b": True, "c": True, "d": True, "e": True}),
    ],
)
def test_hidden_by_status_table(asset_runner, flt, expected):
    run = asset_runner("static/app.js")
    assert run("hiddenByStatus", [NODES, flt]) == expected


def test_hidden_by_status_empty_nodes(asset_runner):
    run = asset_runner("static/app.js")
    assert run("hiddenByStatus", [[], "all"]) == {}
    assert run("hiddenByStatus", [[], "passing"]) == {}


VERIFICATION_PASS = {
    "component_id": "comp-a",
    "criteria": [
        {"id": "AC-A-001", "covers": "R-A-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-A-001": "pass"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "pass",
}

VERIFICATION_FAIL = {
    "component_id": "comp-b",
    "criteria": [
        {
            "id": "AC-B-001",
            "covers": "R-B-001",
            "kind": "compiled",
            "result": "fail",
            "failure_detail": {"message": "x failed", "expected": 1, "actual": 2},
            "failure_origin": "implementation",
        }
    ],
    "requirement_results": {"R-B-001": "fail"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "fail",
}

LICENSE_OK = {"blocked": False}

SECRET_OK = {
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


def hit(report):
    return {
        "hit": True,
        "reason": None,
        "verification_report": report,
        "license_scan": LICENSE_OK,
        "secret_scan": SECRET_OK,
    }


def miss(reason):
    return {
        "hit": False,
        "reason": reason,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


VERIFY_REPORT = {
    "scope": "whole-corpus",
    "ready": False,
    "components": {
        "comp-a": hit(VERIFICATION_PASS),
        "comp-b": hit(VERIFICATION_FAIL),
        "comp-c": miss("no manifest"),
        "comp-d": miss("no manifest"),
    },
    "capabilities": {},
    "secret_scan": SECRET_OK,
    "not_ready_reasons": [
        "comp-b: verification failed",
        "comp-c: no provenance for current spec state — run hotdocs generate comp-c",
        "comp-d: no provenance for current spec state — run hotdocs generate comp-d",
    ],
}


def build_repo(repo_root):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "import copy\n"
        "REPORT = " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")

    graph = {
        "nodes": {
            cid: {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            }
            for cid in ["comp-a", "comp-b", "comp-c", "comp-d"]
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, indent=2), encoding="utf-8"
    )

    attempts = repo_root / ".hotdocs" / "attempts" / "comp-c"
    attempts.mkdir(parents=True)
    record = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": "comp-c",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:abc",
        "generation": {
            "component_id": "comp-c",
            "spec_bundle_hash": "sha256:abc",
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "boom"},
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": None,
    }
    (attempts / "2026-10-25T14-32-01Z-a1b2c3.json").write_text(
        json.dumps(record), encoding="utf-8"
    )


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.filters = []
        self.node_elements = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "button" and "data-filter" in d:
            self.filters.append(d["data-filter"])
        classes = (d.get("class") or "").split()
        if "node" in classes or "data-node-id" in d:
            self.node_elements.append((tag, d))

    handle_startendtag = handle_starttag


def test_rendered_page_filter_buttons_and_nothing_hidden(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
    statuses = sorted(field(n, "status") for n in field(snapshot, "nodes"))
    assert statuses == sorted(["passing", "failing", "missing", "not-attempted"])

    index = out_dir / "index.html"
    html = index.read_text(encoding="utf-8")
    collector = _Collector()
    collector.feed(html)
    assert collector.filters == ["all", "passing", "failing", "missing", "not-attempted"]
    assert collector.node_elements, "expected node elements on the page"
    for tag, attrs in collector.node_elements:
        assert "hidden" not in attrs, (tag, attrs)

    page = browser.open(index)
    assert page.find(css="button[data-filter]").count() == 5
    assert page.find(css="li.node").count() == 4
    assert page.find(css="li.node[hidden]").count() == 0
    assert page.console_errors() == []