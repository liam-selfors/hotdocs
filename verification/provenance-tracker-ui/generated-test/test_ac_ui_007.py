import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_TEMPLATE = '''
import json

_LOG_PATH = {log_path!r}


def _passing_component_result():
    return {{
        "hit": True,
        "verification_report": {{
            "component_id": "comp-bar",
            "criteria": [
                {{"id": "AC-BAR-001", "covers": "R-BAR-001", "kind": "compiled", "result": "pass"}}
            ],
            "requirement_results": {{"R-BAR-001": "pass"}},
            "interface_drift": False,
            "mutation_score": None,
            "overall": "pass",
        }},
        "license_scan": {{"blocked": False, "findings": []}},
        "secret_scan": {{"flagged": False, "findings": []}},
    }}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(None if changed_ids is None else list(changed_ids)) + "\\n")
    scope = "blast-radius" if changed_ids else "whole-corpus"
    return {{
        "scope": scope,
        "ready": True,
        "components": {{"comp-bar": _passing_component_result()}},
        "capabilities": {{}},
        "not_ready_reasons": [],
    }}


def last_requirement_failures(component_id, repo_root):
    return []
'''


def _write_corpus_graph(repo_root: Path):
    verification = repo_root / "verification"
    verification.mkdir(parents=True, exist_ok=True)
    graph = {
        "nodes": {
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["test-team"],
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
    (verification / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _write_fake_tracker(repo_root: Path, log_path: Path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.format(log_path=str(log_path)), encoding="utf-8"
    )


def test_each_render_calls_check_readiness_afresh_and_states_scope(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "check_readiness_calls.log"

    _write_corpus_graph(repo_root)
    _write_fake_tracker(repo_root, log_path)

    out_first = tmp_path / "out_first"
    out_second = tmp_path / "out_second"

    snap_first = provenance_tracker_ui.render_tracker_ui(
        out_first, repo_root, changed_ids=["comp-foo"]
    )
    snap_second = provenance_tracker_ui.render_tracker_ui(out_second, repo_root)

    # The log shows exactly two calls: ["comp-foo"] then null.
    assert log_path.exists(), "faked check_readiness was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2, f"expected exactly two check_readiness calls, got {lines!r}"
    assert json.loads(lines[0]) == ["comp-foo"]
    assert json.loads(lines[1]) is None

    # Returned snapshots reflect each call's own scope.
    assert field(snap_first, "scope") == "blast-radius"
    assert list(field(snap_first, "changed_ids")) == ["comp-foo"]
    assert field(snap_second, "scope") == "whole-corpus"
    assert field(snap_second, "changed_ids") is None

    # Pages state their own scope visibly.
    first_html = (out_first / "index.html").read_text(encoding="utf-8")
    second_html = (out_second / "index.html").read_text(encoding="utf-8")

    assert "blast-radius" in first_html
    assert "comp-foo" in first_html
    assert "whole-corpus" in second_html