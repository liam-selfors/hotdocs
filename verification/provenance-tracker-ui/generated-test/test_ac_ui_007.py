# hotdocs-criterion: sha256:e231032a170b5c1f2aaf8553abcde440ad6a49cdc96ba5de6e437291e17579a2
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    path = repo_root / "verification" / "corpus-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def _write_fake_tracker(repo_root, log_path):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }
    secret_scan = {
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
    license_scan = {
        "gate_version": "license_scanner@1.0.0",
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    component_result = {
        "hit": True,
        "reason": None,
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }

    source = (
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "COMPONENT_RESULT = json.loads(" + repr(json.dumps(component_result)) + ")\n"
        "SECRET_SCAN = json.loads(" + repr(json.dumps(secret_scan)) + ")\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(None if changed_ids is None else list(changed_ids)) + '\\n')\n"
        "    scope = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return {\n"
        "        'scope': scope,\n"
        "        'ready': True,\n"
        "        'components': {'comp-foo': json.loads(json.dumps(COMPONENT_RESULT))},\n"
        "        'capabilities': {},\n"
        "        'secret_scan': json.loads(json.dumps(SECRET_SCAN)),\n"
        "        'not_ready_reasons': [],\n"
        "    }\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    path = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_ac_ui_007_scope_rebuilt_fresh_each_call(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "check_readiness_calls.log"
    _write_corpus_graph(repo_root)
    _write_fake_tracker(repo_root, log_path)

    out1 = tmp_path / "out_blast"
    out2 = tmp_path / "out_whole"

    snap1 = provenance_tracker_ui.render_tracker_ui(out1, repo_root, changed_ids=["comp-foo"])
    snap2 = provenance_tracker_ui.render_tracker_ui(out2, repo_root)

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0]) == ["comp-foo"]
    assert json.loads(lines[1]) is None

    assert field(snap1, "scope") == "blast-radius"
    assert list(field(snap1, "changed_ids")) == ["comp-foo"]
    assert field(snap2, "scope") == "whole-corpus"
    assert field(snap2, "changed_ids") is None

    page1 = browser.open(out1 / "index.html")
    body1 = page1.find(css="body").text()
    assert "blast-radius" in body1
    assert "comp-foo" in body1

    page2 = browser.open(out2 / "index.html")
    body2 = page2.find(css="body").text()
    assert "whole-corpus" in body2