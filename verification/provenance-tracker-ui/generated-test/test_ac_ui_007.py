# hotdocs-criterion: sha256:e3c692d2de12485150f783ec7e6957591775a2976e9c722bb4a7db8b0f15f8ca
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _text_of(element):
    t = element.text
    return t() if callable(t) else t


def _write_fake_tracker(repo_root, log_path):
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
    verification_report = {
        "component_id": "comp-bar",
        "criteria": [
            {"id": "AC-BAR-001", "covers": "R-BAR-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-BAR-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }
    provenance_result = {
        "hit": True,
        "reason": None,
        "verification_report": verification_report,
        "license_scan": {"blocked": False},
        "secret_scan": secret_scan,
    }
    src = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "PROVENANCE_RESULT = json.loads(" + repr(json.dumps(provenance_result)) + ")\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(None if changed_ids is None else list(changed_ids)) + '\\n')\n"
        "    scope = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return {\n"
        "        'scope': scope,\n"
        "        'ready': True,\n"
        "        'components': {'comp-bar': json.loads(json.dumps(PROVENANCE_RESULT))},\n"
        "        'capabilities': {},\n"
        "        'secret_scan': None,\n"
        "        'not_ready_reasons': [],\n"
        "    }\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    mod_dir = repo_root / "gen" / "provenance-tracker"
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            }
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


def test_ac_ui_007_each_build_calls_check_readiness_afresh_and_states_scope(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    snap1 = provenance_tracker_ui.render_tracker_ui(out1, repo_root, changed_ids=["comp-foo"])
    snap2 = provenance_tracker_ui.render_tracker_ui(out2, repo_root)

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0]) == ["comp-foo"]
    assert json.loads(lines[1]) is None

    assert field(snap1, "scope") == "blast-radius"
    assert field(snap1, "changed_ids") == ["comp-foo"]
    assert field(snap2, "scope") == "whole-corpus"
    assert field(snap2, "changed_ids") is None

    page1 = browser.open(out1 / "index.html")
    text1 = _text_of(page1.find(css="body"))
    assert "blast-radius" in text1
    assert "comp-foo" in text1
    assert page1.console_errors() == []

    page2 = browser.open(out2 / "index.html")
    text2 = _text_of(page2.find(css="body"))
    assert "whole-corpus" in text2
    assert page2.console_errors() == []