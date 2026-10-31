import json
from pathlib import Path

import pytest

import provenance_tracker_ui


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_fake_provenance_tracker(repo_root: Path) -> None:
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "provenance_tracker.py").write_text(
        '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "whole-corpus" if changed_ids is None else "blast-radius",
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
''',
        encoding="utf-8",
    )


def _write_corpus_graph(repo_root: Path) -> None:
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
    (verification_dir / "corpus-graph.json").write_text(
        json.dumps(corpus_graph), encoding="utf-8"
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write_corpus_graph(root)
    _write_fake_provenance_tracker(root)
    return root


def _call_main(argv):
    try:
        result = provenance_tracker_ui.main(argv)
    except SystemExit as exc:
        return exc.code
    return result


def test_rendered_index_html_has_no_server_dependency(repo_root, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    index_path = out_dir / "index.html"
    assert index_path.exists()
    html = index_path.read_text(encoding="utf-8")

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "http://" not in html
    assert "https://" not in html

    assert _get(snapshot, "scope") == "whole-corpus"


def test_module_exposes_no_serve_function():
    assert not hasattr(provenance_tracker_ui, "serve")
    serve_like = [
        name
        for name in dir(provenance_tracker_ui)
        if "serve" in name.lower() and callable(getattr(provenance_tracker_ui, name))
    ]
    assert serve_like == []


def test_main_treats_serve_subcommand_as_usage_error(repo_root, tmp_path):
    out_dir = tmp_path / "serve-out"
    argv = [
        "track",
        "ui",
        "serve",
        "--repo-root=" + str(repo_root),
        "--out=" + str(out_dir),
    ]
    exit_code = _call_main(argv)
    assert exit_code == 2
    assert not out_dir.exists() or not (out_dir / "index.html").exists()