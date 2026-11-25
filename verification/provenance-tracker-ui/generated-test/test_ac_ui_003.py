# hotdocs-criterion: sha256:6d1a575bc413a16fb6b56ac401360fbc449cdb9cbf4de2b2847f309af6b0345a
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall, req_results):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-" + rid[2:], "covers": rid, "kind": "compiled", "result": res}
            for rid, res in sorted(req_results.items())
        ],
        "requirement_results": dict(req_results),
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def _license_scan():
    return {"blocked": False, "matches": [], "gate_version": "license_scanner@1.0.0"}


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


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = 0
        self.hrefs = []
        self.scripts = []
        self._in_script = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        for name, value in attrs:
            if name.lower() == "href":
                self.hrefs.append(value if value is not None else "")
        if tag == "form":
            self.forms += 1
        if tag == "script":
            self._in_script = {"attrs": dict(attrs), "data": ""}
            self.scripts.append(self._in_script)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() == "script":
            self._in_script = None

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self._in_script = None

    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script["data"] += data


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "fake_calls.log"

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
            "P-X": {"type": "capability"},
        },
        "edges": [
            {"from": "comp-bar", "to": "P-X", "kind": "realizes"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, indent=2), encoding="utf-8"
    )

    foo_report = _verification_report(
        "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
    )
    bar_report = _verification_report("comp-bar", "pass", {"R-BAR-001": "pass"})

    attempt = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": "comp-foo",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:abc",
        "generation": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:abc",
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"foo.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": foo_report,
    }
    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    attempts_dir.mkdir(parents=True)
    (attempts_dir / "2026-10-25T14-32-01Z-a1b2c3.json").write_text(
        json.dumps(attempt, indent=2), encoding="utf-8"
    )

    verify_report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": foo_report,
                "license_scan": _license_scan(),
                "secret_scan": _secret_scan(),
            },
            "comp-bar": {
                "hit": True,
                "reason": None,
                "verification_report": bar_report,
                "license_scan": _license_scan(),
                "secret_scan": _secret_scan(),
            },
        },
        "capabilities": {
            "P-X": {
                "hit": True,
                "capability_scenario_report": {"P-X": {"overall": "pass", "scenarios": []}},
            }
        },
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-foo: verification failed for current spec state - run hotdocs generate comp-foo"
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "VERIFY_REPORT = " + repr(verify_report) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(VERIFY_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + component_id)\n"
        "    if component_id == 'comp-foo':\n"
        "        return ['R-FOO-002']\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise AssertionError('write_attempt_record must not be called')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")
    return repo_root, log_path


def test_ac_ui_003_page_has_no_actions(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Precondition: the fake ran and the snapshot holds a failing node with retry feedback.
    assert log_path.is_file()
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines.count("check_readiness") == 1
    nodes = field(snapshot, "nodes")
    foo = [n for n in nodes if field(n, "id") == "comp-foo"]
    assert len(foo) == 1
    assert field(foo[0], "status") == "failing"
    assert list(field(foo[0], "retry_feedback")) == ["R-FOO-002"]

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    # No <form element.
    assert "<form" not in html.lower()
    parser = _Collector()
    parser.feed(html)
    parser.close()
    assert parser.forms == 0

    # No href other than in-page fragments.
    for href in parser.hrefs:
        assert href.startswith("#"), "href leaves the page: " + repr(href)

    # Exactly two script elements: the JSON data block and the inlined app.js.
    assert len(parser.scripts) == 2, [s["attrs"] for s in parser.scripts]
    data_blocks = [s for s in parser.scripts if s["attrs"].get("id") == "tracker-snapshot"]
    assert len(data_blocks) == 1
    data_block = data_blocks[0]
    assert "src" not in data_block["attrs"]
    parsed = json.loads(data_block["data"])
    assert isinstance(parsed, dict)

    other = [s for s in parser.scripts if s is not data_block][0]
    assert "src" not in other["attrs"]
    app_js = (
        Path(provenance_tracker_ui.__file__).parent / "static" / "app.js"
    ).read_text(encoding="utf-8")
    assert app_js.strip() != ""
    assert app_js.strip() in other["data"]