# hotdocs-criterion: sha256:188d43aaac2e30b49ad72255c636f61c824b301b3f0409327e810ac56d3191f3
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ATTEMPT_ID = "2026-10-25T14:32:01Z-a1b2c3"


def _miss():
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def _report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-new": _miss(),
            "comp-old": _miss(),
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [
            "comp-new: no provenance for current spec state \u2014 run hotdocs generate comp-new",
            "comp-old: no provenance for current spec state \u2014 run hotdocs generate comp-old",
        ],
    }


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "import copy\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(_report()) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    report = copy.deepcopy(REPORT)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return report\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise RuntimeError('not used in this test')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _component_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "unknown",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-new": _component_node(),
            "comp-old": _component_node(),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 1.0,
            "orphan_var_rate": 0.0,
        },
    }
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _write_attempt(repo_root):
    record = {
        "attempt_id": ATTEMPT_ID,
        "component_id": "comp-old",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "generation": {
            "component_id": "comp-old",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "environment", "message": "fake failure"},
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": None,
    }
    adir = repo_root / ".hotdocs" / "attempts" / "comp-old"
    adir.mkdir(parents=True, exist_ok=True)
    (adir / (ATTEMPT_ID + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")


def _build_repo(tmp_path, with_attempt):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)
    if with_attempt:
        _write_attempt(repo_root)
    return repo_root, log_path


def _statuses(snapshot):
    result = {}
    for node in field(snapshot, "nodes"):
        result[field(node, "id")] = field(node, "status")
    return result


def test_not_attempted_distinct_from_missing(tmp_path, browser):
    repo_root, log_path = _build_repo(tmp_path, with_attempt=True)
    assert not (repo_root / ".hotdocs" / "attempts" / "comp-new").exists()

    out_dir = tmp_path
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "missing"

    assert (out_dir / "index.html").is_file()
    page = browser.open(out_dir / "index.html")
    new_text = page.find(css='li[data-node-id="comp-new"]').text()
    assert "not yet attempted" in new_text


def test_no_hotdocs_directory_still_writes_page(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, with_attempt=False)
    assert not (repo_root / ".hotdocs").exists()

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert (out_dir / "index.html").is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "not-attempted"