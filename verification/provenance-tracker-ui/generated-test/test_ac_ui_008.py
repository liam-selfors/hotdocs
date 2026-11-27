# hotdocs-criterion: sha256:ad411bc3fc982c0b92fcf6e8a92cc25cc15a90f9cdce5fc8fe7d424e065d6f41
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ATTEMPT_A = "2026-10-01T00:00:00Z-aaaaaa"
ATTEMPT_B = "2026-10-02T00:00:00Z-bbbbbb"


def _verification_report(component_id, overall, req_results):
    criteria = []
    n = 0
    for rid in sorted(req_results):
        n += 1
        res = req_results[rid]
        crit = {
            "id": "AC-FOO-00" + str(n),
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            crit["failure_detail"] = {"message": "failed", "expected": 1, "actual": 2}
            crit["failure_origin"] = "implementation"
        criteria.append(crit)
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(req_results),
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


def _generation(component_id):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:abc",
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
    }


def _attempt(attempt_id):
    return {
        "attempt_id": attempt_id,
        "component_id": "comp-foo",
        "timestamp": attempt_id[:20],
        "spec_bundle_hash": "sha256:abc",
        "generation": _generation("comp-foo"),
        "verification": _verification_report(
            "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
        ),
    }


def _component_graph_node(component_id):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _write_fixture(repo_root, log_path):
    repo_root.mkdir(parents=True, exist_ok=True)

    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(
                    "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
                ),
                "license_scan": {"blocked": False},
                "secret_scan": _secret_scan(),
            },
            "comp-ok": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(
                    "comp-ok", "pass", {"R-OK-001": "pass"}
                ),
                "license_scan": {"blocked": False},
                "secret_scan": _secret_scan(),
            },
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": ["comp-foo: verification failed"],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "import copy\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    if component_id == " + repr("comp-foo") + ":\n"
        "        return [" + repr("R-FOO-002") + "]\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise AssertionError('write_attempt_record must not be called')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")

    graph = {
        "nodes": {
            "comp-foo": _component_graph_node("comp-foo"),
            "comp-ok": _component_graph_node("comp-ok"),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    adir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    adir.mkdir(parents=True, exist_ok=True)
    # Write the newer one first so ordering cannot come from write order.
    for aid in (ATTEMPT_B, ATTEMPT_A):
        (adir / (aid + ".json")).write_text(
            json.dumps(_attempt(aid), indent=2) + "\n", encoding="utf-8"
        )


def _node(snapshot, node_id):
    matches = [n for n in field(snapshot, "nodes") if field(n, "id") == node_id]
    assert len(matches) == 1, "expected exactly one node " + node_id
    return matches[0]


def test_ac_ui_008_attempt_history_and_retry_feedback(tmp_path, browser):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "fake_calls.log"
    _write_fixture(repo_root, log_path)

    out_dir = tmp_path
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Snapshot: comp-foo attempts oldest first, retry_feedback from the fake.
    foo = _node(snapshot, "comp-foo")
    assert field(foo, "status") == "failing"
    attempts = field(foo, "attempts")
    assert [field(a, "attempt_id") for a in attempts] == [ATTEMPT_A, ATTEMPT_B]
    assert list(field(foo, "retry_feedback")) == ["R-FOO-002"]

    ok = _node(snapshot, "comp-ok")
    assert field(ok, "status") == "passing"
    assert list(field(ok, "retry_feedback")) == []
    assert list(field(ok, "attempts")) == []

    # The fake really ran.
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert "last_requirement_failures comp-foo" in log_lines

    index = out_dir / "index.html"
    assert index.is_file()
    page = browser.open(index)

    foo_sel = 'li.node[data-node-id="comp-foo"]'
    ok_sel = 'li.node[data-node-id="comp-ok"]'
    assert page.find(css=foo_sel).count() == 1
    assert page.find(css=ok_sel).count() == 1

    # One data-attempt-id element per attempt.
    assert page.find(css=foo_sel + " [data-attempt-id]").count() == 2
    assert page.find(css=foo_sel + ' [data-attempt-id="' + ATTEMPT_A + '"]').count() == 1
    assert page.find(css=foo_sel + ' [data-attempt-id="' + ATTEMPT_B + '"]').count() == 1

    # Order: oldest first.
    assert page.find(
        css=foo_sel + ' [data-attempt-id="' + ATTEMPT_A + '"] ~ [data-attempt-id="' + ATTEMPT_B + '"]'
    ).count() == 1
    assert page.find(
        css=foo_sel + ' [data-attempt-id="' + ATTEMPT_B + '"] ~ [data-attempt-id="' + ATTEMPT_A + '"]'
    ).count() == 0

    # Retry feedback suggestion.
    fb = page.find(css=foo_sel + " .retry-feedback")
    assert fb.count() == 1
    assert fb.text().strip() == "--retry-feedback=R-FOO-002"
    assert fb.text() == "--retry-feedback=R-FOO-002"

    # Passing component carries no retry-feedback element.
    assert page.find(css=ok_sel + " .retry-feedback").count() == 0

    assert page.console_errors() == []