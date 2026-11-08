import json
import re
from pathlib import Path

import provenance_tracker_ui


FAKE_PROVENANCE_TRACKER_SRC = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "blast-radius" if changed_ids else "whole-corpus",
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
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _find_node(nodes, node_id):
    for node in nodes:
        if _get(node, "id") == node_id:
            return node
    return None


def _write_corpus_graph(repo_root):
    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    graph = {
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
    (verification_dir / "corpus-graph.json").write_text(json.dumps(graph))


def _write_fake_provenance_tracker(repo_root):
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER_SRC)


def _write_attempt_record_for_comp_old(repo_root):
    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-old"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    bundle_hash = "sha256:" + "0" * 64
    record = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": "comp-old",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": bundle_hash,
        "generation": {
            "component_id": "comp-old",
            "spec_bundle_hash": bundle_hash,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {},
            "model_call_error": "simulated API failure",
            "refused": None,
            "retry_feedback": None,
        },
        "verification": None,
    }
    (attempts_dir / "2026-10-25T14-32-01Z-a1b2c3.json").write_text(json.dumps(record))


def test_miss_with_no_attempt_record_is_not_attempted_not_missing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_corpus_graph(repo_root)
    _write_fake_provenance_tracker(repo_root)
    _write_attempt_record_for_comp_old(repo_root)

    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    nodes = _get(snapshot, "nodes")
    assert nodes is not None

    comp_new_node = _find_node(nodes, "comp-new")
    comp_old_node = _find_node(nodes, "comp-old")
    assert comp_new_node is not None
    assert comp_old_node is not None

    assert _get(comp_new_node, "status") == "not-attempted"
    assert _get(comp_old_node, "status") == "missing"

    html_path = out_dir / "index.html"
    assert html_path.exists()
    html_text = html_path.read_text()

    match = re.search(
        r'<li[^>]*data-node-id="comp-new"[^>]*>(.*?)</li>',
        html_text,
        re.DOTALL,
    )
    assert match is not None, "no li element with data-node-id=comp-new found"
    assert "not yet attempted" in match.group(1)


def test_missing_hotdocs_directory_entirely_still_writes_page(tmp_path):
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    _write_corpus_graph(repo_root)
    _write_fake_provenance_tracker(repo_root)
    # Deliberately no .hotdocs/ directory of any kind under repo_root.

    out_dir = tmp_path / "out2"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    html_path = out_dir / "index.html"
    assert html_path.exists()

    nodes = _get(snapshot, "nodes")
    assert nodes is not None

    comp_new_node = _find_node(nodes, "comp-new")
    comp_old_node = _find_node(nodes, "comp-old")
    assert comp_new_node is not None
    assert comp_old_node is not None

    assert _get(comp_new_node, "status") == "not-attempted"
    assert _get(comp_old_node, "status") == "not-attempted"