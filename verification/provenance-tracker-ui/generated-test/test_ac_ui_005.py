# hotdocs-criterion: sha256:e28f1837e66466299d611df740d8dbfbaa31c96ce5058dc05a7bc20de62b03ee
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
    "LOG_PATH = "
)

FAKE_TRACKER_TEMPLATE_BODY = (
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
    "        'components': {\n"
    "            'comp-new': _miss(),\n"
    "            'comp-old': _miss(),\n"
    "        },\n"
    "        'capabilities': {},\n"
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
)


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


def _build_repo(repo_root, log_path, with_old_attempt):
    repo_root.mkdir(parents=True, exist_ok=True)

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = FAKE_TRACKER_TEMPLATE_HEAD + repr(str(log_path)) + FAKE_TRACKER_TEMPLATE_BODY
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    graph = {
        "nodes": {
            "comp-new": _component_node(),
            "comp-old": _component_node(),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    ver = repo_root / "verification"
    ver.mkdir(parents=True, exist_ok=True)
    (ver / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    if with_old_attempt:
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
                "files": {},
                "model_call_error": {"category": "environment", "message": "no backend"},
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
        attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-old"
        attempts_dir.mkdir(parents=True, exist_ok=True)
        (attempts_dir / (attempt_id + ".json")).write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )


class _NodeTextParser(HTMLParser):
    def __init__(self, node_id):
        super().__init__(convert_charrefs=True)
        self.node_id = node_id
        self.depth = 0
        self.capturing = False
        self.found = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag != "li":
            return
        if self.capturing:
            self.depth += 1
            return
        attr_map = dict(attrs)
        if attr_map.get("data-node-id") == self.node_id:
            self.capturing = True
            self.depth = 1
            self.found += 1

    def handle_endtag(self, tag):
        if tag != "li" or not self.capturing:
            return
        self.depth -= 1
        if self.depth == 0:
            self.capturing = False

    def handle_data(self, data):
        if self.capturing:
            self.parts.append(data)


def _node_text(html_text, node_id):
    parser = _NodeTextParser(node_id)
    parser.feed(html_text)
    parser.close()
    assert parser.found >= 1, "no li with data-node-id " + repr(node_id)
    return " ".join("".join(parser.parts).split())


def _statuses(snapshot):
    out = {}
    for node in field(snapshot, "nodes"):
        out[field(node, "id")] = field(node, "status")
    return out


def test_never_attempted_component_is_not_attempted_and_labeled(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "fake_calls.log"
    _build_repo(repo_root, log_path, with_old_attempt=True)
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
    html_text = index.read_text(encoding="utf-8")
    text = _node_text(html_text, "comp-new")
    assert "not yet attempted" in text.lower()


def test_no_hotdocs_directory_still_writes_page(tmp_path):
    repo_root = tmp_path / "repo2"
    log_path = tmp_path / "fake_calls2.log"
    _build_repo(repo_root, log_path, with_old_attempt=False)
    assert not (repo_root / ".hotdocs").exists()

    out_dir = tmp_path / "out2"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert (out_dir / "index.html").is_file()
    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "not-attempted"