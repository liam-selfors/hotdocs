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

_LOG = {log_path!r}


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{"fn": "check_readiness", "changed_ids": changed_ids, "model": model, "seed": seed}})
    return {{
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {{
            "comp-foo": {{
                "hit": True,
                "verification_report": {{
                    "component_id": "comp-foo",
                    "criteria": [
                        {{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}}
                    ],
                    "requirement_results": {{"R-FOO-001": "pass"}},
                    "interface_drift": False,
                    "mutation_score": None,
                    "overall": "pass",
                }},
                "license_scan": {{"blocked": False, "findings": []}},
                "secret_scan": {{"flagged": False, "findings": []}},
            }},
            "comp-bar": {{
                "hit": True,
                "verification_report": {{
                    "component_id": "comp-bar",
                    "criteria": [
                        {{"id": "AC-BAR-001", "covers": "R-BAR-001", "kind": "compiled", "result": "pass"}},
                        {{"id": "AC-BAR-002", "covers": "R-BAR-002", "kind": "compiled", "result": "fail",
                          "failure_detail": {{"message": "value equals 5 failed", "expected": 5, "actual": 3}}}}
                    ],
                    "requirement_results": {{"R-BAR-001": "pass", "R-BAR-002": "fail"}},
                    "interface_drift": False,
                    "mutation_score": None,
                    "overall": "fail",
                }},
                "license_scan": {{"blocked": False, "findings": []}},
                "secret_scan": {{"flagged": False, "findings": []}},
            }},
        }},
        "capabilities": {{}},
        "not_ready_reasons": [
            "comp-bar: verification failed for current spec state - run hotdocs generate comp-bar --retry-feedback=R-BAR-002"
        ],
    }}


def last_requirement_failures(component_id, repo_root):
    _log({{"fn": "last_requirement_failures", "component_id": component_id}})
    if component_id == "comp-bar":
        return ["R-BAR-002"]
    return []
'''


class _PageScanner(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.form_tags = 0
        self.scripts = []  # list of (id, text)
        self._in_script = False
        self._script_id = None
        self._script_buf = []

    def _attrs(self, tag, attrs):
        if tag == "form":
            self.form_tags += 1
        for name, value in attrs:
            if name.lower() == "href":
                self.hrefs.append(value)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self._attrs(tag, attrs)
        if tag == "script":
            self._in_script = True
            self._script_id = dict(attrs).get("id")
            self._script_buf = []

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        self._attrs(tag, attrs)
        if tag == "script":
            self.scripts.append((dict(attrs).get("id"), ""))

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._in_script:
            self.scripts.append((self._script_id, "".join(self._script_buf)))
            self._in_script = False
            self._script_id = None
            self._script_buf = []

    def handle_data(self, data):
        if self._in_script:
            self._script_buf.append(data)


def _write_fixture(repo_root: Path, log_path: Path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.format(log_path=str(log_path)), encoding="utf-8"
    )

    graph = {
        "nodes": {
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
        },
        "edges": [{"from": "comp-bar", "to": "comp-foo", "kind": "depends_on"}],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-bar"
    attempts_dir.mkdir(parents=True)
    attempt = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": "comp-bar",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:abc",
        "generation": {
            "component_id": "comp-bar",
            "spec_bundle_hash": "sha256:abc",
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"bar.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification": {
            "component_id": "comp-bar",
            "criteria": [
                {"id": "AC-BAR-001", "covers": "R-BAR-001", "kind": "compiled", "result": "pass"},
                {"id": "AC-BAR-002", "covers": "R-BAR-002", "kind": "compiled", "result": "fail"},
            ],
            "requirement_results": {"R-BAR-001": "pass", "R-BAR-002": "fail"},
            "interface_drift": False,
            "mutation_score": None,
            "overall": "fail",
        },
    }
    (attempts_dir / "2026-10-25T14-32-01Z-a1b2c3.json").write_text(
        json.dumps(attempt, indent=2), encoding="utf-8"
    )


def test_page_has_no_form_no_generate_script_no_external_href(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_tracker_log.jsonl"
    _write_fixture(repo_root, log_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake provenance-tracker was really used.
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len([r for r in records if r["fn"] == "check_readiness"]) == 1

    # Given: the snapshot contains a failing component with non-empty retry_feedback.
    nodes = field(snapshot, "nodes")
    by_id = {field(n, "id"): n for n in nodes}
    assert "comp-bar" in by_id
    bar = by_id["comp-bar"]
    assert field(bar, "status") == "failing"
    assert list(field(bar, "retry_feedback")) == ["R-BAR-002"]

    index = out_dir / "index.html"
    assert index.is_file()
    html_text = index.read_text(encoding="utf-8")

    # No <form element anywhere.
    assert re.search(r"<form\b", html_text, re.IGNORECASE) is None
    scanner = _PageScanner()
    scanner.feed(html_text)
    scanner.close()
    assert scanner.form_tags == 0

    # No "hotdocs generate" in any executable script (every script except tracker-snapshot).
    for script_id, text in scanner.scripts:
        if script_id == "tracker-snapshot":
            continue
        assert "hotdocs generate" not in text, (
            f"script element id={script_id!r} contains 'hotdocs generate'"
        )

    # Every href attribute begins with "#".
    for href in scanner.hrefs:
        assert href is not None and href.startswith("#"), f"href leaves the page: {href!r}"