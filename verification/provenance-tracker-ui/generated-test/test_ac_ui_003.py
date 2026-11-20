# hotdocs-criterion: sha256:415dc820d0afad440a76c6e960e60db31ce2f6fa4672332d04a1fa0145abb6d9
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.start_tags = []
        self.scripts = []
        self._in_script = None

    def handle_starttag(self, tag, attrs):
        self.start_tags.append((tag.lower(), attrs))
        if tag.lower() == "script":
            self._in_script = {"attrs": dict(attrs), "data": ""}

    def handle_startendtag(self, tag, attrs):
        self.start_tags.append((tag.lower(), attrs))
        if tag.lower() == "script":
            self.scripts.append({"attrs": dict(attrs), "data": ""})

    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script["data"] += data

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._in_script is not None:
            self.scripts.append(self._in_script)
            self._in_script = None


def _verification_report(component_id, overall, failing):
    criteria = [
        {"id": "AC-BAR-001", "covers": "R-BAR-001", "kind": "compiled", "result": "pass"},
    ]
    results = {"R-BAR-001": "pass"}
    if failing:
        criteria.append({
            "id": "AC-BAR-002", "covers": "R-BAR-002", "kind": "compiled", "result": "fail",
            "failure_detail": {"message": "x equals 1 failed", "expected": 1, "actual": 2},
            "failure_origin": "implementation",
        })
        results["R-BAR-002"] = "fail"
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": results,
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": overall,
    }


FAKE_TRACKER_BODY = '''
import json
from pathlib import Path


def _log(line):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\\n")


def _report(component_id, overall, failing):
    criteria = [
        {"id": "AC-BAR-001", "covers": "R-BAR-001", "kind": "compiled", "result": "pass"},
    ]
    results = {"R-BAR-001": "pass"}
    if failing:
        criteria.append({
            "id": "AC-BAR-002", "covers": "R-BAR-002", "kind": "compiled", "result": "fail",
            "failure_detail": {"message": "x equals 1 failed", "expected": 1, "actual": 2},
            "failure_origin": "implementation",
        })
        results["R-BAR-002"] = "fail"
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": results,
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
        "overall": overall,
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {
            "comp-bar": {
                "hit": True,
                "reason": None,
                "verification_report": _report("comp-bar", "fail", True),
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _report("comp-foo", "pass", False),
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-bar: verification failed \\u2014 run hotdocs generate comp-bar"
        ],
    }


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures " + component_id)
    if component_id == "comp-bar":
        return ["R-BAR-002"]
    return []
'''


def _component_node(slug):
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


def _build_repo(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_TRACKER_BODY
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    graph = {
        "nodes": {
            "comp-bar": _component_node("bar"),
            "comp-foo": _component_node("foo"),
        },
        "edges": [
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    ver = repo_root / "verification"
    ver.mkdir(parents=True)
    (ver / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempts = repo_root / ".hotdocs" / "attempts" / "comp-bar"
    attempts.mkdir(parents=True)
    attempt_id = "2026-10-25T14:32:01Z-a1b2c3"
    record = {
        "attempt_id": attempt_id,
        "component_id": "comp-bar",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:abc",
        "generation": {
            "component_id": "comp-bar",
            "spec_bundle_hash": "sha256:abc",
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"bar.py": "x = 2\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": _verification_report("comp-bar", "fail", True),
    }
    (attempts / (attempt_id + ".json")).write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


def test_ac_ui_003_page_has_no_actions(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _build_repo(repo_root, log_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake dependency was used.
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert "check_readiness" in log_lines
    assert "last_requirement_failures comp-bar" in log_lines

    # Precondition: a failing component with non-empty retry_feedback.
    nodes = field(snapshot, "nodes")
    bar = [n for n in nodes if field(n, "id") == "comp-bar"]
    assert len(bar) == 1
    assert field(bar[0], "status") == "failing"
    assert list(field(bar[0], "retry_feedback")) == ["R-BAR-002"]

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    parser = _PageParser()
    parser.feed(html)
    parser.close()

    # No <form element.
    assert all(tag != "form" for tag, _ in parser.start_tags)
    assert "<form" not in html.lower()

    # No href attribute other than ones beginning with "#".
    hrefs = [
        value
        for _, attrs in parser.start_tags
        for name, value in attrs
        if name.lower() == "href"
    ]
    for value in hrefs:
        assert value is not None and value.startswith("#"), value

    # Exactly two script elements.
    assert len(parser.scripts) == 2
    data_scripts = [s for s in parser.scripts if s["attrs"].get("id") == "tracker-snapshot"]
    other_scripts = [s for s in parser.scripts if s["attrs"].get("id") != "tracker-snapshot"]
    assert len(data_scripts) == 1
    assert len(other_scripts) == 1

    # The tracker-snapshot block is a JSON data block.
    embedded = json.loads(data_scripts[0]["data"])
    embedded_bar = [n for n in embedded["nodes"] if n["id"] == "comp-bar"]
    assert len(embedded_bar) == 1
    assert embedded_bar[0]["status"] == "failing"
    assert embedded_bar[0]["retry_feedback"] == ["R-BAR-002"]
    assert "src" not in data_scripts[0]["attrs"]

    # The other script is the inlined static/app.js, verbatim.
    app_js = (Path(provenance_tracker_ui.__file__).parent / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert app_js.strip() != ""
    assert "src" not in other_scripts[0]["attrs"]
    assert app_js.strip() in other_scripts[0]["data"]