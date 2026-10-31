import json
import shutil
import tempfile
from pathlib import Path

import provenance_tracker_ui


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_FAKE_PROVENANCE_TRACKER_SRC = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "whole-corpus" if changed_ids is None else "blast-radius",
        "ready": False,
        "components": {
            "comp-new": {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
            "comp-old": {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-new: no provenance for current spec state -- run hotdocs generate comp-new",
            "comp-old: no provenance for current spec state -- run hotdocs generate comp-old",
        ],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


_CORPUS_GRAPH_JSON = {
    "nodes": {
        "comp-new": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
        },
        "comp-old": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
        },
    },
    "edges": [],
    "aggregates": {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    },
}


_OLD_ATTEMPT_RECORD = {
    "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
    "component_id": "comp-old",
    "timestamp": "2026-10-25T14:32:01Z",
    "spec_bundle_hash": "sha256:deadbeef",
    "generation": {
        "component_id": "comp-old",
        "spec_bundle_hash": "sha256:deadbeef",
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"comp_old.py": "# pass"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    },
    "verification": {
        "component_id": "comp-old",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    },
}


def _build_repo_root(tmp_root, with_hotdocs):
    repo_root = tmp_root / "repo"
    repo_root.mkdir()

    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True)
    (dep_dir / "provenance_tracker.py").write_text(_FAKE_PROVENANCE_TRACKER_SRC)

    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True)
    (verification_dir / "corpus-graph.json").write_text(json.dumps(_CORPUS_GRAPH_JSON))

    if with_hotdocs:
        old_attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-old"
        old_attempts_dir.mkdir(parents=True)
        attempt_file = old_attempts_dir / (_OLD_ATTEMPT_RECORD["attempt_id"] + ".json")
        attempt_file.write_text(json.dumps(_OLD_ATTEMPT_RECORD))

    return repo_root


def test_miss_with_attempt_is_missing_miss_without_attempt_is_not_attempted():
    tmp_root = Path(tempfile.mkdtemp())
    try:
        repo_root = _build_repo_root(tmp_root, with_hotdocs=True)
        assert not (repo_root / ".hotdocs" / "attempts" / "comp-new").exists()

        out_dir = tmp_root / "ui-out"
        out_dir.mkdir()

        snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

        nodes = _get(snapshot, "nodes")
        by_id = {_get(n, "id"): n for n in nodes}

        assert _get(by_id["comp-new"], "status") == "not-attempted"
        assert _get(by_id["comp-old"], "status") == "missing"

        index_html = out_dir / "index.html"
        assert index_html.exists()
        html_text = index_html.read_text()
        assert "not yet attempted" in html_text
    finally:
        shutil.rmtree(tmp_root)


def test_missing_hotdocs_directory_renders_without_raising():
    tmp_root = Path(tempfile.mkdtemp())
    try:
        repo_root = _build_repo_root(tmp_root, with_hotdocs=False)
        assert not (repo_root / ".hotdocs").exists()

        out_dir = tmp_root / "ui-out"
        out_dir.mkdir()

        snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

        nodes = _get(snapshot, "nodes")
        by_id = {_get(n, "id"): n for n in nodes}

        assert _get(by_id["comp-new"], "status") == "not-attempted"
        assert _get(by_id["comp-old"], "status") == "not-attempted"

        index_html = out_dir / "index.html"
        assert index_html.exists()
        html_text = index_html.read_text()
        assert "not yet attempted" in html_text
    finally:
        shutil.rmtree(tmp_root)