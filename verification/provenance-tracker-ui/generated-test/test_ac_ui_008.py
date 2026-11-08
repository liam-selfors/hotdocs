import json
import re
from pathlib import Path

import provenance_tracker_ui


FAKE_PROVENANCE_TRACKER = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "whole-corpus" if changed_ids is None else "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [],
                    "requirement_results": {"R-FOO-002": "fail"},
                    "interface_drift": False,
                    "mutation_score": 0.5,
                    "overall": "fail",
                },
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
            "comp-passing": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-passing",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
        },
        "capabilities": {},
        "not_ready_reasons": ["comp-foo: verification failed"],
    }


def last_requirement_failures(component_id, repo_root):
    if component_id == "comp-foo":
        return ["R-FOO-002"]
    return []
'''


def _write_fake_provenance_tracker(repo_root):
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER)


def _write_corpus_graph(repo_root):
    graph_dir = repo_root / "verification"
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph = {
        "nodes": {
            "comp-foo": {"type": "component"},
            "comp-passing": {"type": "component"},
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (graph_dir / "corpus-graph.json").write_text(json.dumps(graph))


def _attempt_record(attempt_id, timestamp, overall, requirement_results):
    return {
        "attempt_id": attempt_id,
        "component_id": "comp-foo",
        "timestamp": timestamp,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "generation": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"spec_linter.py": "x"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification": {
            "component_id": "comp-foo",
            "criteria": [],
            "requirement_results": requirement_results,
            "interface_drift": False,
            "mutation_score": 0.5,
            "overall": overall,
        },
    }


def _write_attempt_records(repo_root):
    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    records = [
        _attempt_record(
            "2026-10-01T00:00:00Z-aaaaaa",
            "2026-10-01T00:00:00Z",
            "fail",
            {"R-FOO-002": "fail"},
        ),
        _attempt_record(
            "2026-10-02T00:00:00Z-bbbbbb",
            "2026-10-02T00:00:00Z",
            "fail",
            {"R-FOO-002": "fail"},
        ),
    ]
    for record in records:
        path = attempts_dir / f"{record['attempt_id']}.json"
        path.write_text(json.dumps(record))


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def test_ac_ui_008(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fake_provenance_tracker(repo_root)
    _write_corpus_graph(repo_root)
    _write_attempt_records(repo_root)

    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    nodes = _get(snapshot, "nodes")
    nodes_by_id = {_get(n, "id"): n for n in nodes}

    foo_node = nodes_by_id["comp-foo"]
    passing_node = nodes_by_id["comp-passing"]

    assert _get(foo_node, "status") == "failing"
    assert _get(passing_node, "status") == "passing"

    foo_attempts = _get(foo_node, "attempts")
    attempt_ids = [_get(a, "attempt_id") for a in foo_attempts]
    assert attempt_ids == [
        "2026-10-01T00:00:00Z-aaaaaa",
        "2026-10-02T00:00:00Z-bbbbbb",
    ]

    assert _get(foo_node, "retry_feedback") == ["R-FOO-002"]
    assert _get(passing_node, "retry_feedback") == []

    index_html = (out_dir / "index.html").read_text()

    data_attempt_ids = re.findall(r'data-attempt-id="([^"]+)"', index_html)
    assert data_attempt_ids == [
        "2026-10-01T00:00:00Z-aaaaaa",
        "2026-10-02T00:00:00Z-bbbbbb",
    ]

    retry_feedback_texts = re.findall(
        r'<[a-zA-Z][^>]*class="[^"]*retry-feedback[^"]*"[^>]*>([^<]*)',
        index_html,
    )
    assert retry_feedback_texts == ["--retry-feedback=R-FOO-002"]