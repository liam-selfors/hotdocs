import json
import re

import pytest

import provenance_tracker_ui


FAKE_MODULE_TEMPLATE = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "whole-corpus" if changed_ids is None else "blast-radius",
        "ready": __READY__,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "covers": "R-FOO-001",
                            "kind": "compiled",
                            "result": "pass",
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": __NOT_READY_REASONS__,
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


_EXTERNAL_RESOURCE_RE = re.compile(
    r'''(?:src|href)\s*=\s*["\'](?:https?:)?//''', re.IGNORECASE
)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _node_to_plain(node):
    return {
        "id": _get(node, "id"),
        "kind": _get(node, "kind"),
        "status": _get(node, "status"),
        "attempts": _get(node, "attempts"),
        "retry_feedback": _get(node, "retry_feedback"),
    }


def _edge_to_plain(edge):
    return {
        "from": _get(edge, "from"),
        "to": _get(edge, "to"),
        "kind": _get(edge, "kind"),
    }


def _snapshot_to_plain(snapshot):
    return {
        "scope": _get(snapshot, "scope"),
        "changed_ids": _get(snapshot, "changed_ids"),
        "ready": _get(snapshot, "ready"),
        "not_ready_reasons": _get(snapshot, "not_ready_reasons"),
        "nodes": [_node_to_plain(n) for n in _get(snapshot, "nodes")],
        "edges": [_edge_to_plain(e) for e in _get(snapshot, "edges")],
    }


def _extract_snapshot_json(html):
    marker = '<script type="application/json" id="tracker-snapshot">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    return html[start:end]


def _write_fake_provenance_tracker(repo_root, ready, not_ready_reasons):
    gen_dir = repo_root / "gen" / "provenance-tracker"
    gen_dir.mkdir(parents=True, exist_ok=True)
    module_path = gen_dir / "provenance_tracker.py"
    source = FAKE_MODULE_TEMPLATE.replace("__READY__", repr(ready)).replace(
        "__NOT_READY_REASONS__", repr(not_ready_reasons)
    )
    module_path.write_text(source, encoding="utf-8")


def _write_corpus_graph(repo_root):
    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    corpus_graph = {
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
                "provenance": {"model": "claude-sonnet-5", "prompt_version": "v1"},
                "size_status": "ok",
                "sealed": False,
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
    (verification_dir / "corpus-graph.json").write_text(
        json.dumps(corpus_graph), encoding="utf-8"
    )


def _setup_repo(tmp_path, ready=True, not_ready_reasons=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fake_provenance_tracker(repo_root, ready, not_ready_reasons or [])
    _write_corpus_graph(repo_root)
    return repo_root


def test_render_tracker_ui_writes_self_contained_html(tmp_path):
    repo_root = _setup_repo(tmp_path, ready=True, not_ready_reasons=[])
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    entries = list(out_dir.iterdir())
    assert [p.name for p in entries] == ["index.html"]

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    parsed = json.loads(_extract_snapshot_json(html))
    assert parsed == _snapshot_to_plain(snapshot)

    assert 'data-node-id="comp-foo"' in html

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "WebAssembly" not in html
    assert not _EXTERNAL_RESOURCE_RE.search(html)


def test_render_tracker_ui_escapes_closing_script_tag_in_snapshot(tmp_path):
    reasons = ["comp-foo: blocked by </script> injection attempt"]
    repo_root = _setup_repo(tmp_path, ready=False, not_ready_reasons=reasons)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    parsed = json.loads(_extract_snapshot_json(html))

    assert parsed == _snapshot_to_plain(snapshot)
    assert parsed["not_ready_reasons"] == reasons