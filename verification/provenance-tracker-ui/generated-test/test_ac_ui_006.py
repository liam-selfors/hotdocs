# hotdocs-criterion: sha256:710b50e52efb39154243e3f8bc331f9c613c5adaafd98bc913cee7bc0826609b
import inspect
import json
from pathlib import Path

import pytest

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _passing_check_result():
    return {
        "hit": True,
        "reason": None,
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": None,
            "mutation_error": None,
            "assets": [],
            "drivers": [],
            "overall": "pass",
        },
        "license_scan": {"blocked": False},
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def _miss_check_result():
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def _build_repo(repo_root):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _passing_check_result(),
            "comp-bar": _miss_check_result(),
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state \u2014 run hotdocs generate comp-bar"
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        "from pathlib import Path\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used in this test')\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
        },
        "edges": [{"from": "comp-bar", "to": "comp-foo", "kind": "depends_on"}],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    ver = repo_root / "verification"
    ver.mkdir(parents=True)
    (ver / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def test_rendered_page_needs_no_server(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
    assert snapshot is not None
    ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert ids == ["comp-bar", "comp-foo"]

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "http://" not in html
    assert "https://" not in html


def test_module_exposes_no_serve_function():
    serve = getattr(provenance_tracker_ui, "serve", None)
    assert not callable(serve)
    public_serve_functions = [
        name
        for name, obj in vars(provenance_tracker_ui).items()
        if not name.startswith("_")
        and name.lower().startswith("serve")
        and (inspect.isfunction(obj) or callable(obj))
    ]
    assert public_serve_functions == []


def test_serve_subcommand_is_usage_error(tmp_path, capsys):
    code = provenance_tracker_ui.main(["track", "ui", "serve"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "usage error" in captured.err


def test_serve_subcommand_with_flags_is_usage_error(tmp_path, capsys):
    code = provenance_tracker_ui.main(
        ["track", "ui", "serve", "--repo-root=" + str(tmp_path)]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert not (tmp_path / ".hotdocs" / "ui" / "index.html").exists()