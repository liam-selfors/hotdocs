# hotdocs-criterion: sha256:66feae667c3fcd6c51c6c461f479c960cd8eb5a46d3b3097a1b118893d58d544
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.form_count = 0
        self.hrefs = []
        self.scripts = []

    def _handle(self, tag, attrs):
        tag = tag.lower()
        if tag == "form":
            self.form_count += 1
        for name, value in attrs:
            if name.lower() == "href":
                self.hrefs.append(value)
        if tag == "script":
            self.scripts.append({k.lower(): v for k, v in attrs})

    def handle_starttag(self, tag, attrs):
        self._handle(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle(tag, attrs)


def _write_fake_tracker(repo_root, log_path):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "x failed", "expected": 5, "actual": 3},
                "failure_origin": "implementation",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "fail",
    }
    secret_scan = {
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
    license_scan = {"blocked": False, "findings": []}
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": license_scan,
                "secret_scan": secret_scan,
            }
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [
            "comp-foo: verification failed \u2014 run hotdocs generate comp-foo"
        ],
    }
    src = (
        "import copy\n"
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
        "    if component_id == 'comp-foo':\n"
        "        return ['R-FOO-002']\n"
        "    return []\n"
    )
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            }
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


def test_ac_ui_003_page_has_no_form_no_external_href_and_two_scripts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Precondition: the snapshot has a failing component with non-empty retry_feedback.
    nodes = field(snapshot, "nodes")
    foo = [n for n in nodes if field(n, "id") == "comp-foo"]
    assert len(foo) == 1
    assert field(foo[0], "status") == "failing"
    assert list(field(foo[0], "retry_feedback")) != []

    log_text = log_path.read_text(encoding="utf-8")
    assert "check_readiness" in log_text

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    collector = _Collector()
    collector.feed(html)
    collector.close()

    # No <form element.
    assert collector.form_count == 0

    # Every href begins with "#".
    for href in collector.hrefs:
        assert href is not None and href.startswith("#"), href

    # Exactly two script elements: the tracker-snapshot data block and one module script.
    assert len(collector.scripts) == 2, collector.scripts
    data_blocks = [s for s in collector.scripts if s.get("id") == "tracker-snapshot"]
    module_scripts = [
        s for s in collector.scripts
        if (s.get("type") or "").strip().lower() == "module" and s.get("id") != "tracker-snapshot"
    ]
    assert len(data_blocks) == 1
    assert len(module_scripts) == 1