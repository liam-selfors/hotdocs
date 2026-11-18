# hotdocs-criterion: sha256:5fe710d065c15d792e212e9451eb94e43195ac8990dfc5d175e3baf5baef338e
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def _miss():\n"
        "    return {\n"
        "        'hit': False,\n"
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
        "        'components': {\n"
        "            'comp-new': _miss(),\n"
        "            'comp-old': _miss(),\n"
        "        },\n"
        "        'capabilities': {},\n"
        "        'not_ready_reasons': [\n"
        "            " + repr("comp-new: no provenance for current spec state \u2014 run hotdocs generate comp-new") + ",\n"
        "            " + repr("comp-old: no provenance for current spec state \u2014 run hotdocs generate comp-old") + ",\n"
        "        ],\n"
        "    }\n"
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
        "owners": ["test-team"],
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
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _write_attempt_record(repo_root):
    adir = repo_root / ".hotdocs" / "attempts" / "comp-old"
    adir.mkdir(parents=True, exist_ok=True)
    attempt_id = "2026-10-25T14:32:01Z-a1b2c3"
    record = {
        "attempt_id": attempt_id,
        "component_id": "comp-old",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "generation": {
            "component_id": "comp-old",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "anthropic:claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {},
            "model_call_error": "simulated API failure",
            "refused": None,
            "retry_feedback": None,
        },
        "verification": None,
    }
    (adir / (attempt_id + ".json")).write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def _build_repo(tmp_path, with_attempts):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)
    if with_attempts:
        _write_attempt_record(repo_root)
    return repo_root, log_path


class _NodeTextCollector(HTMLParser):
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
        attr_map = dict(attrs)
        if attr_map.get("data-node-id") == self.node_id:
            self.depth = 1
            self.found += 1

    def handle_endtag(self, tag):
        if tag.lower() == "li" and self.depth > 0:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth > 0:
            self.chunks.append(data)


def _node_text(html_text, node_id):
    parser = _NodeTextCollector(node_id)
    parser.feed(html_text)
    parser.close()
    return parser.found, " ".join(parser.chunks)


def _statuses(snapshot):
    nodes = field(snapshot, "nodes")
    return {field(n, "id"): field(n, "status") for n in nodes}


def _calls(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def test_never_attempted_component_renders_not_attempted(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, with_attempts=True)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert _calls(log_path).count("check_readiness") == 1

    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "missing"

    index = out_dir / "index.html"
    assert index.is_file()
    html_text = index.read_text(encoding="utf-8")

    found, text = _node_text(html_text, "comp-new")
    assert found >= 1, "no li element with data-node-id='comp-new'"
    assert "not yet attempted" in text.lower()

    found_old, text_old = _node_text(html_text, "comp-old")
    assert found_old >= 1, "no li element with data-node-id='comp-old'"
    assert "not yet attempted" not in text_old.lower()


def test_no_hotdocs_directory_still_writes_page(tmp_path):
    repo_root, log_path = _build_repo(tmp_path, with_attempts=False)
    assert not (repo_root / ".hotdocs").exists()
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert (out_dir / "index.html").is_file()
    assert _calls(log_path).count("check_readiness") == 1

    statuses = _statuses(snapshot)
    assert statuses["comp-new"] == "not-attempted"
    assert statuses["comp-old"] == "not-attempted"