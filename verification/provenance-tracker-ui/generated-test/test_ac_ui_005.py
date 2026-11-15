import json
import re
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_TEMPLATE = '''
import json
from pathlib import Path

_LOG = Path({log_path!r})


def _log(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\\n")


def _miss():
    return {{
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{"fn": "check_readiness", "changed_ids": changed_ids, "model": model, "seed": seed}})
    return {{
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {{
            "comp-new": _miss(),
            "comp-old": _miss(),
        }},
        "capabilities": {{}},
        "not_ready_reasons": [
            "comp-new: no provenance for current spec state \\u2014 run hotdocs generate comp-new",
            "comp-old: no provenance for current spec state \\u2014 run hotdocs generate comp-old",
        ],
    }}


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    raise NotImplementedError("not used by this test")


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


def _build_repo(tmp_path, with_hotdocs):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

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
    verification_dir = repo_root / "verification"
    verification_dir.mkdir()
    (verification_dir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    if with_hotdocs:
        attempt_dir = repo_root / ".hotdocs" / "attempts" / "comp-old"
        attempt_dir.mkdir(parents=True)
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
                "files": {"old.py": "x = 1\n"},
                "model_call_error": None,
                "refused": None,
                "retry_feedback": None,
            },
            "verification": {
                "component_id": "comp-old",
                "criteria": [
                    {"id": "AC-OLD-001", "covers": "R-OLD-001", "kind": "compiled", "result": "pass"}
                ],
                "requirement_results": {"R-OLD-001": "pass"},
                "interface_drift": False,
                "mutation_score": 0.9,
                "overall": "pass",
            },
        }
        (attempt_dir / (attempt_id + ".json")).write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )

    return repo_root, log_path


def _statuses(snapshot):
    result = {}
    for node in field(snapshot, "nodes"):
        result[field(node, "id")] = field(node, "status")
    return result


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


class _NodeTextExtractor(HTMLParser):
    def __init__(self, node_id):
        super().__init__(convert_charrefs=True)
        self.node_id = node_id
        self.active = False
        self.li_depth = 0
        self.found = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag != "li":
            return
        if self.active:
            self.li_depth += 1
            return
        if not self.found and dict(attrs).get("data-node-id") == self.node_id:
            self.active = True
            self.found = True
            self.li_depth = 0

    def handle_endtag(self, tag):
        if tag != "li" or not self.active:
            return
        if self.li_depth == 0:
            self.active = False
        else:
            self.li_depth -= 1

    def handle_data(self, data):
        if self.active:
            self.chunks.append(data)

    def text(self):
        return re.sub(r"\s+", " ", " ".join(self.chunks)).strip()


def _node_text(html_text, node_id):
    parser = _NodeTextExtractor(node_id)
    parser.feed(html_text)
    parser.close()
    assert parser.found, f"no <li data-node-id={node_id!r}> element in index.html"
    return parser.text()


def test_never_attempted_component_is_not_attempted_and_labeled(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, with_hotdocs=True)
    out_dir = tmp_path / "ui-out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = [c for c in _read_log(log_path) if c["fn"] == "check_readiness"]
    assert len(calls) == 1

    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "missing"

    index = out_dir / "index.html"
    assert index.is_file()
    html_text = index.read_text(encoding="utf-8")

    new_text = _node_text(html_text, "comp-new")
    assert "not yet attempted" in new_text.lower(), new_text


def test_no_hotdocs_directory_still_writes_page(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, with_hotdocs=False)
    assert not (repo_root / ".hotdocs").exists()
    out_dir = tmp_path / "ui-out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = [c for c in _read_log(log_path) if c["fn"] == "check_readiness"]
    assert len(calls) == 1

    assert (out_dir / "index.html").is_file()

    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "not-attempted"