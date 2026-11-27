# hotdocs-criterion: sha256:418f461b3aab85b0d83a23d8f476f764295b04c4861ed6f6f4a3d5bdf3594484
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.mark.parametrize("filt,expected", EXPECTED)
def test_hidden_by_status_table(asset_runner, filt, expected):
    run = asset_runner("static/app.js")
    nodes = [dict(n) for n in NODES]
    result = run("hiddenByStatus", [nodes, filt])
    assert result == expected


def test_hidden_by_status_empty_nodes(asset_runner):
    run = asset_runner("static/app.js")
    assert run("hiddenByStatus", [[], "all"]) == {}
    assert run("hiddenByStatus", [[], "passing"]) == {}


# ---------------------------------------------------------------------------
# Rendered page: filter buttons and initial node visibility
# ---------------------------------------------------------------------------


def _verification_report(component_id, overall):
    result = "pass" if overall == "pass" else "fail"
    r_id = "R-" + component_id.upper().replace("COMP-", "") + "-001"
    ac_id = "AC-" + component_id.upper().replace("COMP-", "") + "-001"
    criterion = {
        "id": ac_id,
        "covers": r_id,
        "kind": "compiled",
        "result": result,
    }
    if result == "fail":
        criterion["failure_detail"] = {"message": "failed", "expected": 1, "actual": 0}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
        "requirement_results": {r_id: result},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


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


def _hit(component_id, overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": {"blocked": False},
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


def _build_repo(repo_root):
    components = {
        "comp-a": _hit("comp-a", "pass"),
        "comp-b": _hit("comp-b", "fail"),
        "comp-c": _miss(),
        "comp-d": _miss(),
    }
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": components,
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-b: verification failed",
            "comp-c: no provenance for current spec state — run hotdocs generate comp-c",
            "comp-d: no provenance for current spec state — run hotdocs generate comp-d",
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used')\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")

    graph = {
        "nodes": {},
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    for cid in ["comp-a", "comp-b", "comp-c", "comp-d"]:
        graph["nodes"][cid] = {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {},
        }
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempt_dir = repo_root / ".hotdocs" / "attempts" / "comp-c"
    attempt_dir.mkdir(parents=True)
    attempt_id = "2026-10-25T14:32:01Z-a1b2c3"
    record = {
        "attempt_id": attempt_id,
        "component_id": "comp-c",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "generation": {
            "component_id": "comp-c",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"c.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": _verification_report("comp-c", "fail"),
    }
    (attempt_dir / (attempt_id + ".json")).write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.filter_buttons = []
        self.node_elements = []

    def handle_starttag(self, tag, attrs):
        attr_map = {}
        for k, v in attrs:
            attr_map[k] = v
        if tag == "button" and "data-filter" in attr_map:
            self.filter_buttons.append(attr_map)
        classes = (attr_map.get("class") or "").split()
        if tag == "li" and "node" in classes:
            self.node_elements.append(attr_map)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def test_rendered_page_has_five_filter_buttons_in_order_and_no_hidden_nodes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    nodes = field(snapshot, "nodes")
    statuses = sorted(field(n, "status") for n in nodes)
    assert statuses == sorted(["passing", "failing", "missing", "not-attempted"])

    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    parser = _PageParser()
    parser.feed(html_text)
    parser.close()

    assert len(parser.filter_buttons) == 5
    assert [b["data-filter"] for b in parser.filter_buttons] == [
        "all",
        "passing",
        "failing",
        "missing",
        "not-attempted",
    ]

    assert len(parser.node_elements) == 4
    for el in parser.node_elements:
        assert "hidden" not in el