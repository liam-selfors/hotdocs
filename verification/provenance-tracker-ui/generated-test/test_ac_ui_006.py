# hotdocs-criterion: sha256:a1e80a6b764cdcdb380e9d73961ceb5977bd9f9f0639fb07772f1e8f58ca36a7
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "overall": "pass",
    }


def _write_fake_tracker(repo_root, log_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report("comp-foo"),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
            "comp-bar": {
                "hit": False,
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
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state - run hotdocs generate comp-bar"
        ],
    }
    src = (
        "import copy\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise AssertionError('write_attempt_record must not be called')\n"
    )
    target = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(src, encoding="utf-8")


def _component_node(component_id, verification):
    return {
        "type": "component",
        "verification": verification,
        "provenance": None if verification is None else {"gate_version": "x@1.0.0"},
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {"component.md": "A plain component description."},
    }


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-bar": _component_node("comp-bar", None),
            "comp-foo": _component_node("comp-foo", _verification_report("comp-foo")),
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
    path = repo_root / "verification" / "corpus-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, sort_keys=True, indent=2), encoding="utf-8")


def _setup(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)
    return repo_root, log_path


def test_rendered_index_html_needs_no_server(tmp_path):
    repo_root, log_path = _setup(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake dependency was really used.
    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    node_ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert "comp-foo" in node_ids

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")
    assert html.strip()

    # Data is inlined, so it is present in the page itself.
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
        if name.lower().startswith("serve"):
            assert not callable(getattr(provenance_tracker_ui, name)), name


def test_serve_subcommand_is_usage_error(tmp_path):
    repo_root, _ = _setup(tmp_path)
    assert provenance_tracker_ui.main(["track", "ui", "serve"]) == 2
    assert (
        provenance_tracker_ui.main(
            ["track", "ui", "serve", "--repo-root=" + str(repo_root)]
        )
        == 2
    )
    # Nothing was written by the rejected subcommand.
    assert not (repo_root / ".hotdocs" / "ui" / "index.html").exists()