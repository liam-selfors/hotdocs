# hotdocs-criterion: sha256:71f3ff3235c6c5bb28b57bda98cc9affe93ecf8b3644e1d925c2d4ff23689fb3
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


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


def _verify_report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False, "matches": []},
                "secret_scan": _secret_scan(),
            },
            "comp-bar": {
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
            },
        },
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state — run hotdocs generate comp-bar"
        ],
    }


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + component_id)\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _write_corpus_graph(repo_root):
    graph = {
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
            "comp-bar": {
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
            {"from": "comp-bar", "to": "comp-foo", "kind": "depends_on"},
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)
    return repo_root, log_path


def test_rendered_index_needs_no_server(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
    assert snapshot is not None
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")
    assert html.strip() != ""

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "http://" not in html
    assert "https://" not in html


def test_module_exposes_no_serve_function():
    assert not hasattr(provenance_tracker_ui, "serve")


def test_main_serve_subcommand_is_usage_error(tmp_path, capsys):
    repo_root, _log = _build_repo(tmp_path)
    rc = provenance_tracker_ui.main(["track", "ui", "serve"])
    assert rc == 2
    rc = provenance_tracker_ui.main(
        ["track", "ui", "serve", "--repo-root=" + str(repo_root)]
    )
    assert rc == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err