import json
import re
from pathlib import Path

import provenance_tracker_ui


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _node_to_plain(node):
    return {
        "id": _field(node, "id"),
        "kind": _field(node, "kind"),
        "status": _field(node, "status"),
        "attempts": list(_field(node, "attempts") or []),
        "retry_feedback": list(_field(node, "retry_feedback") or []),
    }


def _edge_to_plain(edge):
    return {
        "from": _field(edge, "from"),
        "to": _field(edge, "to"),
        "kind": _field(edge, "kind"),
    }


def snapshot_to_plain(snapshot):
    nodes = _field(snapshot, "nodes") or []
    edges = _field(snapshot, "edges") or []
    return {
        "scope": _field(snapshot, "scope"),
        "changed_ids": _field(snapshot, "changed_ids"),
        "ready": _field(snapshot, "ready"),
        "not_ready_reasons": list(_field(snapshot, "not_ready_reasons") or []),
        "nodes": [_node_to_plain(n) for n in nodes],
        "edges": [_edge_to_plain(e) for e in edges],
    }


def make_fake_provenance_tracker(ready, not_ready_reasons):
    return (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {\n"
        "        'scope': 'whole-corpus' if changed_ids is None else 'blast-radius',\n"
        f"        'ready': {ready!r},\n"
        "        'components': {\n"
        "            'comp-foo': {\n"
        "                'hit': True,\n"
        "                'verification_report': {\n"
        "                    'component_id': 'comp-foo',\n"
        "                    'criteria': [],\n"
        "                    'requirement_results': {},\n"
        "                    'interface_drift': False,\n"
        "                    'mutation_score': 1.0,\n"
        "                    'overall': 'pass',\n"
        "                },\n"
        "                'license_scan': {'blocked': False},\n"
        "                'secret_scan': {'flagged': False},\n"
        "            },\n"
        "        },\n"
        "        'capabilities': {},\n"
        f"        'not_ready_reasons': {not_ready_reasons!r},\n"
        "    }\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": {
                    "component_id": "comp-foo",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "provenance": {},
                "size_status": "ok",
                "sealed": False,
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
    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / "corpus-graph.json").write_text(json.dumps(graph))


def build_repo(tmp_path, name, ready, not_ready_reasons):
    repo_root = tmp_path / name
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True)
    (dep_dir / "provenance_tracker.py").write_text(
        make_fake_provenance_tracker(ready, not_ready_reasons)
    )
    write_corpus_graph(repo_root)
    return repo_root


def extract_snapshot_json_text(html):
    match = re.search(
        r'<script type="application/json" id="tracker-snapshot">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None, "tracker-snapshot script element not found"
    return match.group(1)


def test_render_tracker_ui_writes_self_contained_single_file(tmp_path):
    repo_root = build_repo(tmp_path, "repo1", ready=True, not_ready_reasons=[])
    out_dir = tmp_path / "out1"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    entries = list(out_dir.iterdir())
    assert entries == [out_dir / "index.html"]

    html = (out_dir / "index.html").read_text()

    parsed = json.loads(extract_snapshot_json_text(html))
    assert parsed == snapshot_to_plain(snapshot)

    assert 'data-node-id="comp-foo"' in html

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "WebAssembly" not in html

    for m in re.finditer(r'(?:src|href)="([^"]*)"', html):
        value = m.group(1)
        assert not value.startswith("http://")
        assert not value.startswith("https://")
        assert not value.startswith("//")
        assert not value.startswith("ftp:")


def test_render_tracker_ui_escapes_closing_script_tag_inside_snapshot(tmp_path):
    reason = "comp-foo: anomaly </script> detected in provenance record"
    repo_root = build_repo(
        tmp_path, "repo2", ready=False, not_ready_reasons=[reason]
    )
    out_dir = tmp_path / "out2"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    html = (out_dir / "index.html").read_text()

    parsed = json.loads(extract_snapshot_json_text(html))
    assert parsed == snapshot_to_plain(snapshot)
    assert reason in parsed["not_ready_reasons"]