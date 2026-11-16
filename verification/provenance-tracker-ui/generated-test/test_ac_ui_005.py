import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_TEMPLATE = '''
import json
from pathlib import Path

_LOG = Path({log_path!r})


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{"fn": "check_readiness",
           "changed_ids": list(changed_ids) if changed_ids is not None else None,
           "model": model, "seed": seed}})
    miss = {{"hit": False, "verification_report": None,
             "license_scan": None, "secret_scan": None}}
    return {{
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {{"comp-new": dict(miss), "comp-old": dict(miss)}},
        "capabilities": {{}},
        "not_ready_reasons": [
            "comp-new: no provenance for current spec state \\u2014 run hotdocs generate comp-new",
            "comp-old: no provenance for current spec state \\u2014 run hotdocs generate comp-old",
        ],
    }}


def last_requirement_failures(component_id, repo_root):
    _log({{"fn": "last_requirement_failures", "component_id": component_id}})
    return []
'''


def _component_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "unknown",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["test-team"],
        "documents": {},
    }


def _setup_repo(repo_root: Path, log_path: Path):
    repo_root.mkdir(parents=True, exist_ok=True)
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.format(log_path=str(log_path)), encoding="utf-8"
    )
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
    ver = repo_root / "verification"
    ver.mkdir(parents=True)
    (ver / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _write_attempt(repo_root: Path):
    attempt_id = "2026-10-25T14:32:01Z-a1b2c3"
    record = {
        "attempt_id": attempt_id,
        "component_id": "comp-old",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "generation": {
            "component_id": "comp-old",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"comp_old.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification": {
            "component_id": "comp-old",
            "criteria": [
                {"id": "AC-OLD-001", "covers": "R-OLD-001", "kind": "compiled",
                 "result": "fail",
                 "failure_detail": {"message": "x equals 2 failed",
                                    "expected": 2, "actual": 1}},
            ],
            "requirement_results": {"R-OLD-001": "fail"},
            "interface_drift": False,
            "mutation_score": 0.5,
            "overall": "fail",
        },
    }
    d = repo_root / ".hotdocs" / "attempts" / "comp-old"
    d.mkdir(parents=True)
    (d / f"{attempt_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


class _LiTextExtractor(HTMLParser):
    def __init__(self, node_id):
        super().__init__(convert_charrefs=True)
        self.node_id = node_id
        self.depth = 0
        self.found = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "li":
            return
        if self.depth > 0:
            self.depth += 1
            return
        if dict(attrs).get("data-node-id") == self.node_id:
            self.found += 1
            self.depth = 1

    def handle_endtag(self, tag):
        if tag.lower() == "li" and self.depth > 0:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth > 0:
            self.chunks.append(data)


def _li_text(html_text, node_id):
    p = _LiTextExtractor(node_id)
    p.feed(html_text)
    p.close()
    assert p.found >= 1, f"no <li data-node-id={node_id!r}> in index.html"
    return " ".join(" ".join(p.chunks).split())


def _statuses(snapshot):
    nodes = field(snapshot, "nodes")
    return {field(n, "id"): field(n, "status") for n in nodes}


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_never_attempted_component_is_labeled_not_attempted(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "fake_log.jsonl"
    out_dir = tmp_path / "out"
    _setup_repo(repo_root, log_path)
    _write_attempt(repo_root)
    assert not (repo_root / ".hotdocs" / "attempts" / "comp-new").exists()

    snapshot = provenance_tracker_ui.render_tracker_ui(
        out_dir=out_dir, repo_root=repo_root, changed_ids=None
    )

    calls = [r for r in _read_log(log_path) if r["fn"] == "check_readiness"]
    assert len(calls) == 1, "fake provenance-tracker check_readiness was not used exactly once"

    statuses = _statuses(snapshot)
    assert statuses.get("comp-new") == "not-attempted"
    assert statuses.get("comp-old") == "missing"

    index = out_dir / "index.html"
    assert index.is_file()
    html_text = index.read_text(encoding="utf-8")
    text = _li_text(html_text, "comp-new").lower()
    assert "not yet attempted" in text, f"comp-new node text was: {text!r}"


def test_no_hotdocs_directory_still_writes_page(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "fake_log.jsonl"
    out_dir = tmp_path / "out"
    _setup_repo(repo_root, log_path)
    assert not (repo_root / ".hotdocs").exists()

    snapshot = provenance_tracker_ui.render_tracker_ui(
        out_dir=out_dir, repo_root=repo_root, changed_ids=None
    )

    calls = [r for r in _read_log(log_path) if r["fn"] == "check_readiness"]
    assert len(calls) == 1, "fake provenance-tracker check_readiness was not used exactly once"

    assert (out_dir / "index.html").is_file()
    statuses = _statuses(snapshot)
    assert statuses.get("comp-new") == "not-attempted"
    assert statuses.get("comp-old") == "not-attempted"