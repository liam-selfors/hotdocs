# hotdocs-criterion: sha256:3cd465fe1f707002fbbd10fba9a635d334ec4c49618dbf98fe608cdc7265182f
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_TEMPLATE_HEAD = (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
)

FAKE_TRACKER_TEMPLATE_BODY = (
    "\n"
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
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
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures ' + str(component_id))\n"
    "    return []\n"
)


def write_fake_tracker(repo_root, log_path):
    target = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        FAKE_TRACKER_TEMPLATE_HEAD
        + "LOG_PATH = " + repr(str(log_path)) + "\n"
        + FAKE_TRACKER_TEMPLATE_BODY
    )
    target.write_text(source, encoding="utf-8")


def component_node():
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


def write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-new": component_node(),
            "comp-old": component_node(),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    path = repo_root / "verification" / "corpus-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def write_attempt_record(repo_root):
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
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"old.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": {
            "component_id": "comp-old",
            "criteria": [
                {"id": "AC-OLD-001", "covers": "R-OLD-001", "kind": "compiled",
                 "result": "fail", "failure_origin": "implementation",
                 "failure_detail": {"message": "x failed", "expected": 1, "actual": 2}},
            ],
            "requirement_results": {"R-OLD-001": "fail"},
            "interface_drift": False,
            "mutation_score": 0.5,
            "mutation_error": None,
            "assets": [],
            "overall": "fail",
        },
    }
    d = repo_root / ".hotdocs" / "attempts" / "comp-old"
    d.mkdir(parents=True, exist_ok=True)
    (d / (attempt_id.replace(":", "") + ".json")).write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )


class NodeTextParser(HTMLParser):
    def __init__(self, node_id):
        super().__init__(convert_charrefs=True)
        self.node_id = node_id
        self.depth = 0
        self.found = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if self.depth > 0:
            if tag == "li":
                self.depth += 1
            return
        if tag == "li" and dict(attrs).get("data-node-id") == self.node_id:
            self.found = True
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth > 0 and tag == "li":
            self.depth -= 1

    def handle_data(self, data):
        if self.depth > 0:
            self.chunks.append(data)


def node_text(html_text, node_id):
    parser = NodeTextParser(node_id)
    parser.feed(html_text)
    parser.close()
    assert parser.found, "no li with data-node-id " + repr(node_id)
    return " ".join("".join(parser.chunks).split())


def statuses(snapshot):
    result = {}
    for node in field(snapshot, "nodes"):
        result[field(node, "id")] = field(node, "status")
    return result


def test_not_attempted_vs_missing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    write_fake_tracker(repo_root, log_path)
    write_corpus_graph(repo_root)
    write_attempt_record(repo_root)
    assert not (repo_root / ".hotdocs" / "attempts" / "comp-new").exists()

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    st = statuses(snapshot)
    assert st["comp-new"] == "not-attempted"
    assert st["comp-old"] == "missing"

    index = out_dir / "index.html"
    assert index.is_file()
    html_text = index.read_text(encoding="utf-8")
    text = node_text(html_text, "comp-new")
    assert "not yet attempted" in text.lower()


def test_no_hotdocs_dir_still_writes_page(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    write_fake_tracker(repo_root, log_path)
    write_corpus_graph(repo_root)
    assert not (repo_root / ".hotdocs").exists()

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert (out_dir / "index.html").is_file()
    st = statuses(snapshot)
    assert st["comp-new"] == "not-attempted"
    assert st["comp-old"] == "not-attempted"