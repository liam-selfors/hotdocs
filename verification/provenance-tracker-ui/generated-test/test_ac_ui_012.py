# hotdocs-criterion: sha256:18cd7bc162cdc15f53d7db3f94da446deaa0100b3d5cacda49083bfcfa0ad47c
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall):
    result = "pass" if overall == "pass" else "fail"
    criterion = {
        "id": "AC-X-001",
        "covers": "R-X-001",
        "kind": "compiled",
        "result": result,
    }
    if result == "fail":
        criterion["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
        "requirement_results": {"R-X-001": result},
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


def _provenance_hit(component_id, overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": {"blocked": False, "flagged": False, "matches": []},
        "secret_scan": _secret_scan(),
    }


def _write_fake_tracker(repo_root, log_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-bar": _provenance_hit("comp-bar", "fail"),
            "comp-foo": _provenance_hit("comp-foo", "pass"),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": ["comp-bar: verification failed"],
    }
    src = (
        "import copy\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    report = copy.deepcopy(_REPORT)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return report\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
    )
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    (d / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _component_node():
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


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-bar": _component_node(),
            "comp-foo": _component_node(),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 1.0,
            "orphan_var_rate": 0.0,
        },
    }
    d = repo_root / "verification"
    d.mkdir(parents=True, exist_ok=True)
    (d / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _visible_node_texts(page, ids):
    visible = []
    for node_id in ids:
        el = page.find(css='li.node[data-node-id="' + node_id + '"]')
        if el.visible():
            visible.append(el.text())
    return visible


def test_ac_ui_012_failing_filter_then_all(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "tracker_calls.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake ran exactly once for check_readiness.
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    statuses = {field(n, "id"): field(n, "status") for n in field(snapshot, "nodes")}
    assert statuses == {"comp-bar": "failing", "comp-foo": "passing"}

    index = out_dir / "index.html"
    assert index.is_file()

    page = browser.open(index)
    ids = ["comp-foo", "comp-bar"]

    assert page.find(css="li.node").count() == 2

    # On load every node is shown.
    assert len(_visible_node_texts(page, ids)) == 2

    page.find(role="button", name="failing").click()

    visible = _visible_node_texts(page, ids)
    assert len(visible) == 1
    assert "comp-bar" in visible[0]
    assert "comp-foo" not in visible[0]
    assert page.find(css='li.node[data-node-id="comp-foo"]').visible() is False
    assert page.find(css='li.node[data-node-id="comp-bar"]').visible() is True

    page.find(role="button", name="all").click()

    visible = _visible_node_texts(page, ids)
    assert len(visible) == 2
    assert any("comp-foo" in t for t in visible)
    assert any("comp-bar" in t for t in visible)

    assert page.console_errors() == []
    assert page.blocked_requests() == []