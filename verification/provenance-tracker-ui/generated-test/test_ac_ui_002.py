import json
import re

import provenance_tracker_ui


FAKE_PROVENANCE_TRACKER = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    def verification_report(component_id, overall):
        return {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": overall,
        }

    return {
        "scope": "whole-corpus",
        "ready": False,
        "not_ready_reasons": [],
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report("comp-foo", "pass"),
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-bar": {
                "hit": True,
                "verification_report": verification_report("comp-bar", "fail"),
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-qux": {
                "hit": True,
                "verification_report": verification_report("comp-qux", "pass"),
                "license_scan": {"blocked": True},
                "secret_scan": {"flagged": False},
            },
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ZERO-EDIT": {"overall": "fail", "scenarios": []},
                },
            },
        },
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _find_node_tag(html, node_id):
    pattern = re.compile(r'<[^>]+\bid=["\']%s["\'][^>]*>' % re.escape(node_id))
    return pattern.search(html)


def _attr(tag, name):
    match = re.search(r'%s=["\']([^"\']*)["\']' % re.escape(name), tag)
    return match.group(1) if match else None


def test_ac_ui_002_statuses_and_node_attributes(tmp_path):
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "out"

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER)

    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True)
    corpus_graph = {
        "nodes": {
            "comp-foo": {"type": "component"},
            "comp-bar": {"type": "component"},
            "comp-qux": {"type": "component"},
            "P-ZERO-EDIT": {"type": "capability"},
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (verification_dir / "corpus-graph.json").write_text(json.dumps(corpus_graph))

    out_dir.mkdir(parents=True)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    expected_statuses = {
        "comp-foo": "passing",
        "comp-bar": "failing",
        "comp-qux": "failing",
        "P-ZERO-EDIT": "failing",
    }

    nodes = _get(snapshot, "nodes")
    assert nodes is not None

    actual_statuses = {}
    for node in nodes:
        node_id = _get(node, "id")
        if node_id in expected_statuses:
            actual_statuses[node_id] = _get(node, "status")

    assert actual_statuses == expected_statuses

    index_html = out_dir / "index.html"
    assert index_html.exists()
    html = index_html.read_text()

    for node_id, status in expected_statuses.items():
        tag_match = _find_node_tag(html, node_id)
        assert tag_match is not None, f"no element found with id={node_id!r}"
        tag = tag_match.group(0)

        data_status = _attr(tag, "data-status")
        assert data_status == status, (
            f"node {node_id!r} data-status was {data_status!r}, expected {status!r}"
        )

        class_attr = _attr(tag, "class")
        assert class_attr is not None, f"node {node_id!r} has no class attribute"
        classes = class_attr.split()
        assert f"status-{status}" in classes, (
            f"node {node_id!r} classes {classes!r} missing status-{status!r}"
        )