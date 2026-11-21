# hotdocs-criterion: sha256:67ce959c4db14d3e642f0f7c8a86932de1549973905d5218d2ca679cffe874a0
import provenance_tracker_ui

import json
from html.parser import HTMLParser
from pathlib import Path


ATTEMPT_A = "2026-10-01T00:00:00Z-aaaaaa"
ATTEMPT_B = "2026-10-02T00:00:00Z-bbbbbb"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall, requirement_results):
    criteria = []
    for i, (rid, res) in enumerate(sorted(requirement_results.items()), start=1):
        crit = {
            "id": "AC-" + rid[2:-4] + "-" + str(i).zfill(3) if False else "AC-FOO-" + str(i).zfill(3),
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            crit["failure_detail"] = {"message": "failed", "expected": 1, "actual": 2}
            crit["failure_origin"] = "implementation"
        criteria.append(crit)
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(requirement_results),
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [{
            "kind": "python", "path": ".", "definition_sha256": None,
            "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }],
        "overall": overall,
    }


def _generation_result(component_id):
    return {
        "component_id": component_id,
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
    }


def _attempt_record(attempt_id, component_id, failing):
    results = {"R-FOO-001": "pass", "R-FOO-002": "fail" if failing else "pass"}
    return {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": attempt_id[:20],
        "spec_bundle_hash": "sha256:abc",
        "generation": _generation_result(component_id),
        "verification": _verification_report(component_id, "fail", results),
    }


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    foo_vr = _verification_report(
        "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"})
    ok_vr = _verification_report(
        "comp-ok", "pass", {"R-FOO-001": "pass"})
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": foo_vr,
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-ok": {
                "hit": True,
                "reason": None,
                "verification_report": ok_vr,
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
        },
        "capabilities": {},
        "not_ready_reasons": ["comp-foo: verification failed"],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "import copy\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(report) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    if component_id == " + repr("comp-foo") + ":\n"
        "        return [" + repr("R-FOO-002") + "]\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")

    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": foo_vr,
                "provenance": {},
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-ok": {
                "type": "component",
                "verification": ok_vr,
                "provenance": {},
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    attempts_dir.mkdir(parents=True)
    # Write the newer one first so ordering cannot come from write order.
    for aid in (ATTEMPT_B, ATTEMPT_A):
        rec = _attempt_record(aid, "comp-foo", failing=True)
        (attempts_dir / (aid + ".json")).write_text(
            json.dumps(rec, indent=2) + "\n", encoding="utf-8")

    return repo_root, log_path


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class _Elem:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []
        self.text_parts = []

    @property
    def text(self):
        return "".join(self.text_parts)

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def descendants(self):
        out = []
        for c in self.children:
            out.append(c)
            out.extend(c.descendants())
        return out


class _TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Elem("#root", [], None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        el = _Elem(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(el)
        if tag not in VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        el = _Elem(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for el in self.stack:
            el.text_parts.append(data)


def _parse(html_text):
    p = _TreeParser()
    p.feed(html_text)
    p.close()
    return p.root


def _node_element(root, node_id):
    candidates = [e for e in root.descendants()
                  if e.attrs.get("data-node-id") == node_id]
    assert candidates, "no element with data-node-id " + repr(node_id)
    preferred = [e for e in candidates if "node" in e.classes()]
    if preferred:
        return preferred[0]
    return candidates[0]


def test_ac_ui_008_attempt_history_and_retry_feedback(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Snapshot assertions
    nodes = {field(n, "id"): n for n in field(snapshot, "nodes")}
    assert "comp-foo" in nodes
    assert "comp-ok" in nodes
    foo = nodes["comp-foo"]
    assert field(foo, "status") == "failing"
    attempt_ids = [field(a, "attempt_id") for a in field(foo, "attempts")]
    assert attempt_ids == [ATTEMPT_A, ATTEMPT_B]
    assert list(field(foo, "retry_feedback")) == ["R-FOO-002"]

    ok = nodes["comp-ok"]
    assert field(ok, "status") == "passing"
    assert list(field(ok, "attempts")) == []
    assert list(field(ok, "retry_feedback")) == []

    # The fake's last_requirement_failures was consulted for comp-foo once
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines.count("last_requirement_failures comp-foo") == 1

    # Page assertions
    html_text = (Path(out_dir) / "index.html").read_text(encoding="utf-8")
    root = _parse(html_text)

    foo_el = _node_element(root, "comp-foo")
    foo_desc = foo_el.descendants()
    page_attempt_ids = [e.attrs["data-attempt-id"] for e in foo_desc
                        if "data-attempt-id" in e.attrs]
    assert page_attempt_ids == [ATTEMPT_A, ATTEMPT_B]

    feedback = [e for e in foo_desc if "retry-feedback" in e.classes()]
    assert len(feedback) == 1
    assert feedback[0].text.strip() == "--retry-feedback=R-FOO-002"

    ok_el = _node_element(root, "comp-ok")
    ok_feedback = [e for e in ok_el.descendants() if "retry-feedback" in e.classes()]
    assert ok_feedback == []
    assert "retry-feedback" not in ok_el.classes()