import json

import provenance_tracker_ui


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_PROVENANCE_TRACKER_TEMPLATE = '''
import json

LOG_FILE = "__LOG_FILE_PATH__"


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(changed_ids) + "\\n")
    scope = "blast-radius" if changed_ids else "whole-corpus"
    return {
        "scope": scope,
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def test_ac_ui_007(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    verification_dir = repo_root / "verification"
    verification_dir.mkdir()
    corpus_graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": {},
                "provenance": {},
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
            }
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (verification_dir / "corpus-graph.json").write_text(json.dumps(corpus_graph))

    log_file = tmp_path / "check_readiness_calls.log"

    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True)
    escaped_log_path = str(log_file).replace("\\", "\\\\")
    source = FAKE_PROVENANCE_TRACKER_TEMPLATE.replace(
        "__LOG_FILE_PATH__", escaped_log_path
    )
    (dep_dir / "provenance_tracker.py").write_text(source)

    out_dir_1 = tmp_path / "out1"
    out_dir_2 = tmp_path / "out2"

    snapshot_1 = provenance_tracker_ui.render_tracker_ui(
        out_dir_1, repo_root, changed_ids=["comp-foo"]
    )
    snapshot_2 = provenance_tracker_ui.render_tracker_ui(
        out_dir_2, repo_root, changed_ids=None
    )

    assert log_file.exists()
    lines = log_file.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == ["comp-foo"]
    assert json.loads(lines[1]) is None

    assert _get(snapshot_1, "scope") == "blast-radius"
    assert _get(snapshot_1, "changed_ids") == ["comp-foo"]
    assert _get(snapshot_2, "scope") == "whole-corpus"
    assert _get(snapshot_2, "changed_ids") is None

    page_1 = (out_dir_1 / "index.html").read_text()
    page_2 = (out_dir_2 / "index.html").read_text()

    assert "blast-radius" in page_1
    assert "comp-foo" in page_1
    assert "whole-corpus" in page_2