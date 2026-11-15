import provenance_tracker_ui

import json
import re
from html.parser import HTMLParser
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAILING_REASON = (
    "comp-bar: verification failed for current spec state \u2014 "
    "run hotdocs generate comp-bar --retry-feedback=R-BAR-002"
)


FAKE_TRACKER_TEMPLATE = '''
import json
from pathlib import Path

_LOG = {log_path!r}


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def _verification_report(component_id, overall, requirement_results):
    criteria = []
    for i, (rid, res) in enumerate(sorted(requirement_results.items()), start=1):
        crit = {{
            "id": "AC-" + rid[2:],
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }}
        if res == "fail":
            crit["failure_detail"] = {{"message": "check failed", "expected": 1, "actual": 0}}
        criteria.append(crit)
    return {{
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(requirement_results),
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": overall,
    }}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{
        "fn": "check_readiness",
        "repo_root": str(repo_root),
        "changed_ids": changed_ids,
        "model": model,
        "seed": seed,
    }})
    return {{
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {{
            "comp-bar": {{
                "hit": True,
                "verification_report": _verification_report(
                    "comp-bar", "fail", {{"R-BAR-001": "pass", "R-BAR-002": "fail"}}
                ),
                "license_scan": {{"blocked": False, "findings": []}},
                "secret_scan": {{"flagged": False, "findings": []}},
            }},
            "comp-foo": {{
                "hit": True,
                "verification_report": _verification_report(
                    "comp-foo", "pass", {{"R-FOO-001": "pass"}}
                ),
                "license_scan": {{"blocked": False, "findings": []}},
                "secret_scan": {{"flagged": False, "findings": []}},
            }},
        }},
        "capabilities": {{}},
        "not_ready_reasons": [{reason!r}],
    }}


def last_requirement_failures(component_id, repo_root):
    _log({{
        "fn": "last_requirement_failures",
        "component_id": component_id,
        "repo_root": str(repo_root),
    }})
    if component_id == "comp-bar":
        return ["R-BAR-002"]
    return []


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    raise AssertionError("write_attempt_record must not be called by the UI")
'''


def _component_node(slug, overall):
    return {
        "type": "component",
        "verification": {
            "component_id": "comp-" + slug,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": overall,
        },
        "provenance": {"gate_version": "component_gate_runner@1.0.0"},
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {"component.md": "---\nid: comp-" + slug + "\n---\n"},
    }


def _build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.jsonl"

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.format(log_path=str(log_path), reason=FAILING_REASON),
        encoding="utf-8",
    )

    graph = {
        "nodes": {
            "comp-bar": _component_node("bar", "fail"),
            "comp-foo": _component_node("foo", "pass"),
        },
        "edges": [
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.5,
            "orphan_var_rate": 0.0,
        },
    }
    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-bar"
    attempts_dir.mkdir(parents=True)
    attempt = {
        "attempt_id": "20261025T143201Z-a1b2c3",
        "component_id": "comp-bar",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:abc123",
        "generation": {
            "component_id": "comp-bar",
            "spec_bundle_hash": "sha256:abc123",
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
                {"id": "AC-BAR-002", "covers": "R-BAR-002", "kind": "compiled", "result": "fail",
                 "failure_detail": {"message": "check failed", "expected": 1, "actual": 0}},
            ],
            "requirement_results": {"R-BAR-001": "pass", "R-BAR-002": "fail"},
            "interface_drift": False,
            "mutation_score": 0.8,
            "overall": "fail",
        },
    }
    (attempts_dir / "20261025T143201Z-a1b2c3.json").write_text(
        json.dumps(attempt, indent=2), encoding="utf-8"
    )

    return repo_root, log_path


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []  # (tag, attrs dict)
        self.scripts = []  # (attrs dict, content)
        self._in_script = False
        self._script_attrs = None
        self._script_chunks = []

    def _record(self, tag, attrs):
        self.tags.append((tag.lower(), {k.lower(): v for k, v in attrs}))

    def handle_starttag(self, tag, attrs):
        self._record(tag, attrs)
        if tag.lower() == "script":
            self._in_script = True
            self._script_attrs = {k.lower(): v for k, v in attrs}
            self._script_chunks = []

    def handle_startendtag(self, tag, attrs):
        self._record(tag, attrs)
        if tag.lower() == "script":
            self.scripts.append(({k.lower(): v for k, v in attrs}, ""))

    def handle_data(self, data):
        if self._in_script:
            self._script_chunks.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._in_script:
            self.scripts.append((self._script_attrs, "".join(self._script_chunks)))
            self._in_script = False
            self._script_attrs = None
            self._script_chunks = []

    def close(self):
        super().close()
        if self._in_script:
            self.scripts.append((self._script_attrs, "".join(self._script_chunks)))
            self._in_script = False


def test_ac_ui_003_page_has_no_generate_action(tmp_path):
    repo_root, log_path = _build_fixture(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Given: the fake tracker was used, and the snapshot holds a failing
    # component with a non-empty retry_feedback.
    assert log_path.exists(), "fake provenance-tracker was never invoked"
    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(c["fn"] == "check_readiness" for c in calls)

    nodes = field(snapshot, "nodes")
    by_id = {field(n, "id"): n for n in nodes}
    assert "comp-bar" in by_id
    bar = by_id["comp-bar"]
    assert field(bar, "status") == "failing"
    assert list(field(bar, "retry_feedback")) == ["R-BAR-002"]

    index = Path(out_dir) / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    parser = _PageParser()
    parser.feed(html)
    parser.close()

    # No <form element.
    form_tags = [t for t, _ in parser.tags if t == "form"]
    assert form_tags == [], "page contains a <form> element"

    snapshot_blocks = [content for attrs, content in parser.scripts
                       if (attrs or {}).get("id") == "tracker-snapshot"]
    remaining = html
    for content in snapshot_blocks:
        if content:
            remaining = remaining.replace(content, "", 1)
    assert not re.search(r"<\s*form\b", remaining, re.IGNORECASE), (
        "page contains a <form element outside the tracker-snapshot data block"
    )

    # No "hotdocs generate" in any executable script element.
    for attrs, content in parser.scripts:
        if (attrs or {}).get("id") == "tracker-snapshot":
            continue
        assert "hotdocs generate" not in content, (
            "an executable script element contains 'hotdocs generate': attrs=%r" % (attrs,)
        )

    # No href attribute other than ones beginning with "#".
    for tag, attrs in parser.tags:
        for name in ("href", "xlink:href"):
            if name in attrs:
                value = attrs[name] if attrs[name] is not None else ""
                assert value.strip().startswith("#"), (
                    "<%s> has %s=%r, which leaves the page" % (tag, name, value)
                )