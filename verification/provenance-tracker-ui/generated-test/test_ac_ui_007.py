import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TEMPLATE = '''
import json
from pathlib import Path

_LOG_PATH = Path({log_path!r})


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(changed_ids if changed_ids is None else list(changed_ids)) + "\\n")
    scope = "blast-radius" if changed_ids else "whole-corpus"
    return {{
        "scope": scope,
        "ready": True,
        "components": {{
            "comp-bar": {{
                "hit": True,
                "verification_report": {{
                    "component_id": "comp-bar",
                    "criteria": [],
                    "requirement_results": {{}},
                    "interface_drift": False,
                    "mutation_score": None,
                    "overall": "pass",
                }},
                "license_scan": {{"blocked": False}},
                "secret_scan": {{"flagged": False}},
            }}
        }},
        "capabilities": {{}},
        "not_ready_reasons": [],
    }}


def last_requirement_failures(component_id, repo_root):
    return []
'''


def _setup_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "check_readiness_calls.log"

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TEMPLATE.format(log_path=str(log_path)), encoding="utf-8"
    )

    verification = repo_root / "verification"
    verification.mkdir()
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
    return repo_root, log_path


def test_each_build_calls_check_readiness_afresh_and_states_scope(tmp_path):
    repo_root, log_path = _setup_repo(tmp_path)

    out_first = tmp_path / "out-first"
    out_second = tmp_path / "out-second"

    snap_first = provenance_tracker_ui.render_tracker_ui(
        out_first, repo_root, changed_ids=["comp-foo"]
    )
    first_html = (Path(out_first) / "index.html").read_text(encoding="utf-8")

    snap_second = provenance_tracker_ui.render_tracker_ui(out_second, repo_root)
    second_html = (Path(out_second) / "index.html").read_text(encoding="utf-8")

    # Log shows exactly two calls: ["comp-foo"] then null.
    assert log_path.exists(), "faked check_readiness was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2, f"expected exactly two check_readiness calls, got {lines!r}"
    assert json.loads(lines[0]) == ["comp-foo"]
    assert json.loads(lines[1]) is None

    # First page: blast-radius scope together with its changed_ids.
    assert "blast-radius" in first_html
    assert "comp-foo" in first_html

    # Second page: whole-corpus scope.
    assert "whole-corpus" in second_html

    # Returned snapshots agree with the pages they inlined.
    assert field(snap_first, "scope") == "blast-radius"
    assert list(field(snap_first, "changed_ids")) == ["comp-foo"]
    assert field(snap_second, "scope") == "whole-corpus"
    assert field(snap_second, "changed_ids") is None