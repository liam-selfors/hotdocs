# hotdocs-criterion: sha256:815ef2cad6c3616df56c7032e7b5a25dace3f0ff81b70a18917bea60453c03f8
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
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


def _base_report():
    return {
        "scope": "whole-corpus",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": _secret_scan(),
            }
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [],
    }


def _write_fake_tracker(repo_root, log_path):
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import copy\n"
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "BASE = " + repr(_base_report()) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(changed_ids) + '\\n')\n"
        "    report = copy.deepcopy(BASE)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    report['ready'] = True\n"
        "    return report\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (dep_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


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


def test_ac_ui_007_fresh_check_per_build_and_scope_shown(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    snap1 = provenance_tracker_ui.render_tracker_ui(
        out1, repo_root, changed_ids=["comp-foo"]
    )
    page1 = (out1 / "index.html").read_text(encoding="utf-8")

    snap2 = provenance_tracker_ui.render_tracker_ui(out2, repo_root)
    page2 = (out2 / "index.html").read_text(encoding="utf-8")

    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    calls = [json.loads(l) for l in lines]
    assert calls == [["comp-foo"], None]

    assert field(snap1, "scope") == "blast-radius"
    assert list(field(snap1, "changed_ids")) == ["comp-foo"]
    assert field(snap2, "scope") == "whole-corpus"
    assert field(snap2, "changed_ids") is None

    assert "blast-radius" in page1
    assert "comp-foo" in page1
    assert "whole-corpus" in page2