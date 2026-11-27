# hotdocs-criterion: sha256:5d5b459558f158b31b92a69672e245c795d8ea9bd1d8132a183aeb7cf0a6f3fc
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall, req_id):
    result = "pass" if overall == "pass" else "fail"
    criterion = {
        "id": "AC-" + req_id[2:],
        "covers": req_id,
        "kind": "compiled",
        "result": result,
    }
    if result == "fail":
        criterion["failure_detail"] = {"message": "failed", "expected": 1, "actual": 0}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
        "requirement_results": {req_id: result},
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


def _license_scan():
    return {"blocked": False, "findings": [], "cache_hit": False}


def _check_result(component_id, overall, req_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall, req_id),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


def _write_fake_tracker(repo_root, log_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _check_result("comp-foo", "pass", "R-FOO-001"),
            "comp-bar": _check_result("comp-bar", "fail", "R-BAR-001"),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": ["comp-bar: verification failed"],
    }
    source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT_JSON = " + repr(json.dumps(report)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(REPORT_JSON)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    if component_id == 'comp-bar':\n"
        "        return ['R-BAR-001']\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise RuntimeError('not used in this test')\n"
    )
    target = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


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
    path = repo_root / "verification" / "corpus-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _node(page, node_id):
    return page.find(css='li.node[data-node-id="' + node_id + '"]')


def test_ac_ui_012_failing_filter_shows_only_failing_then_all_shows_both(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_calls.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    index = out_dir / "index.html"
    assert index.is_file()

    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines.count("check_readiness") == 1

    statuses = {field(n, "id"): field(n, "status") for n in field(snapshot, "nodes")}
    assert statuses == {"comp-bar": "failing", "comp-foo": "passing"}

    page = browser.open(index)

    assert page.find(css="li.node").count() == 2
    foo = _node(page, "comp-foo")
    bar = _node(page, "comp-bar")
    assert "comp-foo" in foo.text()
    assert "comp-bar" in bar.text()

    # On load every node is shown.
    assert foo.visible() is True
    assert bar.visible() is True

    page.find(role="button", name="failing").click()
    assert bar.visible() is True
    assert foo.visible() is False
    visible_texts = [
        el.text() for el in (_node(page, "comp-foo"), _node(page, "comp-bar")) if el.visible()
    ]
    assert len(visible_texts) == 1
    assert "comp-bar" in visible_texts[0]
    assert "comp-foo" not in visible_texts[0]

    page.find(role="button", name="all").click()
    assert _node(page, "comp-foo").visible() is True
    assert _node(page, "comp-bar").visible() is True

    assert page.console_errors() == []
    assert page.blocked_requests() == []