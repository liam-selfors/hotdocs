import json
import sys
from pathlib import Path

import pytest

import provenance_tracker_ui


FORBIDDEN = ["fetch(", "XMLHttpRequest", "http://", "https://"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_PROVENANCE_TRACKER = r'''
import json
from pathlib import Path


def _log(repo_root, record):
    log_path = Path(repo_root) / "fake_provenance_tracker_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log(repo_root, {
        "fn": "check_readiness",
        "changed_ids": list(changed_ids) if changed_ids is not None else None,
        "model": model,
        "seed": seed,
    })
    verification_report = {
        "component_id": "comp-alpha",
        "criteria": [
            {"id": "AC-ALPHA-001", "covers": "R-ALPHA-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-ALPHA-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "overall": "pass",
    }
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {
            "comp-alpha": {
                "hit": True,
                "verification_report": verification_report,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
            "comp-beta": {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {
            "P-ALPHA-CAP": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ALPHA-CAP": {"overall": "pass", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [
            "comp-beta: no provenance for current spec state - run hotdocs generate comp-beta"
        ],
    }


def last_requirement_failures(component_id, repo_root):
    _log(repo_root, {"fn": "last_requirement_failures", "component_id": component_id})
    return []
'''


def _build_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER, encoding="utf-8")

    graph = {
        "nodes": {
            "P-ALPHA-CAP": {"type": "capability"},
            "comp-alpha": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["test-team"],
                "documents": {"component.md": "alpha component"},
            },
            "comp-beta": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["test-team"],
                "documents": {"component.md": "beta component"},
            },
        },
        "edges": [
            {"from": "comp-alpha", "to": "P-ALPHA-CAP", "kind": "realizes"},
            {"from": "comp-beta", "to": "comp-alpha", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True)
    (verification_dir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return repo_root


def _read_log(repo_root: Path):
    log_path = repo_root / "fake_provenance_tracker_log.jsonl"
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("changed_ids", [None, ["comp-alpha"]])
def test_rendered_index_html_requires_no_server(tmp_path, changed_ids):
    repo_root = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root, changed_ids)

    # The fake dependency was actually used.
    log = _read_log(repo_root)
    readiness_calls = [r for r in log if r["fn"] == "check_readiness"]
    assert len(readiness_calls) == 1

    # The snapshot was built from the fake's report.
    node_ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert "comp-alpha" in node_ids

    index_html = out_dir / "index.html"
    assert index_html.is_file()
    html = index_html.read_text(encoding="utf-8")
    assert html.strip(), "index.html is empty"

    for needle in FORBIDDEN:
        assert needle not in html, f"index.html contains {needle!r}, which requires a server/network"


def test_module_exposes_no_serve_function():
    assert not hasattr(provenance_tracker_ui, "serve")
    for name in dir(provenance_tracker_ui):
        if name.startswith("_"):
            continue
        if name.lower().startswith("serve"):
            assert not callable(getattr(provenance_tracker_ui, name)), (
                f"module exposes a serve-like callable {name!r}"
            )


def _run_main(argv):
    try:
        return provenance_tracker_ui.main(argv)
    except SystemExit as exc:
        return exc.code


def test_main_serve_subcommand_is_usage_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _run_main(["track", "ui", "serve"]) == 2


def test_main_serve_subcommand_with_flags_is_usage_error(tmp_path, monkeypatch):
    repo_root = _build_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    code = _run_main(["track", "ui", "serve", "--repo-root", str(repo_root)])
    assert code == 2
    # A usage error starts nothing: no page was written to the default location.
    assert not (repo_root / ".hotdocs" / "ui" / "index.html").exists()
    assert not (tmp_path / ".hotdocs" / "ui" / "index.html").exists()