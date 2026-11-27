# hotdocs-criterion: sha256:c65642ea6c65e3b87fe8d5068755680e12f56d964649c4a9603f70defe10f1eb
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _call(value):
    return value() if callable(value) else value


def _verification_report(component_id, overall, req_id, req_result):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-" + req_id[2:],
                "covers": req_id,
                "kind": "compiled",
                "result": req_result,
            }
        ],
        "requirement_results": {req_id: req_result},
        "interface_drift": False,
        "mutation_score": None,
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


def _license_scan():
    return {"blocked": False, "findings": []}


def _check_result(component_id, overall, req_id, req_result):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(
            component_id, overall, req_id, req_result
        ),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


def _write_fake_tracker(repo_root, log_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _check_result("comp-foo", "pass", "R-FOO-001", "pass"),
            "comp-bar": _check_result("comp-bar", "fail", "R-BAR-001", "fail"),
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
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    report = copy.deepcopy(_REPORT)\n"
        "    if changed_ids is not None:\n"
        "        report['scope'] = 'blast-radius'\n"
        "    return report\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    if component_id == 'comp-bar':\n"
        "        return ['R-BAR-001']\n"
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
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    v = repo_root / "verification"
    v.mkdir(parents=True, exist_ok=True)
    (v / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _visible_node_texts(page):
    return list(_call(page.find(css="li.node:not([hidden])").texts))


def _node_visible(page, node_id):
    el = page.find(css='li.node[data-node-id="' + node_id + '"]')
    return bool(_call(el.visible))


def test_ac_ui_012_failing_filter_then_all(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_tracker.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    statuses = {field(n, "id"): field(n, "status") for n in field(snapshot, "nodes")}
    assert statuses == {"comp-bar": "failing", "comp-foo": "passing"}

    index = out_dir / "index.html"
    assert index.is_file()

    page = browser.open(index)

    page.find(role="button", name="failing").click()

    visible = _visible_node_texts(page)
    assert len(visible) == 1
    assert "comp-bar" in visible[0]
    assert "comp-foo" not in visible[0]
    assert _node_visible(page, "comp-bar") is True
    assert _node_visible(page, "comp-foo") is False

    page.find(role="button", name="all").click()

    visible = _visible_node_texts(page)
    assert len(visible) == 2
    assert any("comp-bar" in t for t in visible)
    assert any("comp-foo" in t for t in visible)
    assert _node_visible(page, "comp-bar") is True
    assert _node_visible(page, "comp-foo") is True

    assert list(page.console_errors()) == []
    assert list(page.blocked_requests()) == []