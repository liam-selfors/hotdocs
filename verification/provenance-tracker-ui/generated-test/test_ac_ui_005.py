# hotdocs-criterion: sha256:3ca388c78ac76c55b4ea712045210342ad336bff575845027c21d5df5c6e7218
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_TEMPLATE = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "LOG_PATH = __LOG_PATH__\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def _miss():\n"
    "    return {\n"
    "        'hit': False,\n"
    "        'reason': 'no manifest',\n"
    "        'verification_report': None,\n"
    "        'license_scan': None,\n"
    "        'secret_scan': None,\n"
    "    }\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness')\n"
    "    return {\n"
    "        'scope': 'blast-radius' if changed_ids is not None else 'whole-corpus',\n"
    "        'ready': False,\n"
    "        'components': {'comp-new': _miss(), 'comp-old': _miss()},\n"
    "        'capabilities': {},\n"
    "        'secret_scan': None,\n"
    "        'not_ready_reasons': [\n"
    "            'comp-new: no provenance for current spec state \\u2014 run hotdocs generate comp-new',\n"
    "            'comp-old: no provenance for current spec state \\u2014 run hotdocs generate comp-old',\n"
    "        ],\n"
    "    }\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures ' + str(component_id))\n"
    "    return []\n"
    "\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    raise NotImplementedError('not used by this test')\n"
)


def _write_fake_tracker(repo_root, log_path):
    src = FAKE_TRACKER_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path)))
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _component_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
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


def _write_attempt_record(repo_root):
    record = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
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
            "model_call_error": {"category": "environment", "message": "no model"},
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
    (adir / "2026-10-25T14:32:01Z-a1b2c3.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def _statuses(snapshot):
    return {field(n, "id"): field(n, "status") for n in field(snapshot, "nodes")}


def test_not_attempted_distinct_from_missing(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)
    _write_attempt_record(repo_root)
    assert not (repo_root / ".hotdocs" / "attempts" / "comp-new").exists()

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "missing"

    index = out_dir / "index.html"
    assert index.is_file()
    page = browser.open(index)
    node = page.find(css='li[data-node-id="comp-new"]')
    assert "not yet attempted" in node.text()
    old_node = page.find(css='li[data-node-id="comp-old"]')
    assert "not yet attempted" not in old_node.text()


def test_no_hotdocs_dir_is_normal(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)
    assert not (repo_root / ".hotdocs").exists()

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert (out_dir / "index.html").is_file()
    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "not-attempted"