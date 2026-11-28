# hotdocs-criterion: sha256:9fa0d2b19a05cd7eea15f06380aacfa654c3b0174e26998b74065f7ff64ac379
"""AC-UI-006: the rendered index.html needs no server, and no serve
entry point exists (R-UI-006)."""

import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _verification_report(component_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


def _verify_report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-foo"),
                "license_scan": {"blocked": False, "matches": []},
                "secret_scan": _secret_scan(),
            },
            "comp-baz": {
                "hit": False,
                "reason": "no manifest",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ZERO-EDIT": {"overall": "pass", "scenarios": []}
                },
            }
        },
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-baz: no provenance for current spec state - run hotdocs generate comp-baz"
        ],
    }


def _corpus_graph():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-baz": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"}
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "import copy\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2), encoding="utf-8"
    )
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    return repo_root, log_path


def test_rendered_page_requires_no_server(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake stood in for provenance-tracker.
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert ids == sorted(["comp-foo", "comp-baz", "P-ZERO-EDIT"])

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")
    assert "comp-foo" in html

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "http://" not in html
    assert "https://" not in html


def test_module_exposes_no_serve_function():
    assert not hasattr(provenance_tracker_ui, "serve")
    for name in dir(provenance_tracker_ui):
        if name.startswith("_"):
            continue
        obj = getattr(provenance_tracker_ui, name)
        if not callable(obj):
            continue
        lowered = name.lower()
        assert not (
            lowered == "serve"
            or lowered.startswith("serve_")
            or lowered.endswith("_serve")
            or "_serve_" in lowered
        ), "unexpected serve entry point: " + name


def test_main_serve_subcommand_is_usage_error(tmp_path, capsys):
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_main_serve_subcommand_with_flags_is_usage_error(tmp_path, capsys):
    repo_root, _ = _build_repo(tmp_path)
    out_dir = tmp_path / "out"
    rc = provenance_tracker_ui.main(
        ["track", "ui", "serve", "--repo-root", str(repo_root), "--out=" + str(out_dir)]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "Traceback" not in captured.err
    assert not (out_dir / "index.html").exists()