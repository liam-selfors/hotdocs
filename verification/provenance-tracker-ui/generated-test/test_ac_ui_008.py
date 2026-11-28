# hotdocs-criterion: sha256:dd32275d0f8ae0aec157441b47f9b7753a0ae34be019469d5e8a9a7afc309937
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ATTEMPT_A = "2026-10-01T00:00:00Z-aaaaaa"
ATTEMPT_B = "2026-10-02T00:00:00Z-bbbbbb"


def _verification_report(component_id, overall, requirement_results):
    criteria = []
    for i, (rid, res) in enumerate(sorted(requirement_results.items()), start=1):
        crit = {
            "id": "AC-" + rid[2:-4] + "-" + rid[-3:],
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
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


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


def _license_scan():
    return {"blocked": False, "flagged": False, "matches": [], "notified": False}


def _provenance_check_result(component_id, overall, requirement_results):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall, requirement_results),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


def _attempt_record(attempt_id, component_id):
    timestamp = attempt_id.split("Z-")[0] + "Z"
    return {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": timestamp,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "generation": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "0" * 64,
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
        "verification": _verification_report(
            component_id, "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
        ),
    }


def _write_fake_tracker(repo_root, report, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "\n"
        "_REPORT = " + repr(json.dumps(report)) + "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return json.loads(_REPORT)\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise RuntimeError('not used')\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('last_requirement_failures ' + str(component_id) + '\\n')\n"
        "    if component_id == " + repr("comp-foo") + ":\n"
        "        return [" + repr("R-FOO-002") + "]\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _component_graph_node(verification):
    return {
        "type": "component",
        "verification": verification,
        "provenance": None,
        "size_status": "ok",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


class _NodeAttemptCollector(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.attempts_by_node = {}
        self.retry_by_node = {}

    def _current_node(self):
        for _tag, node_id in reversed(self.stack):
            if node_id is not None:
                return node_id
        return None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        node_id = None
        classes = (a.get("class") or "").split()
        if tag == "li" and "node" in classes and a.get("data-node-id") is not None:
            node_id = a.get("data-node-id")
        enclosing = node_id if node_id is not None else self._current_node()
        if "data-attempt-id" in a and enclosing is not None:
            self.attempts_by_node.setdefault(enclosing, []).append(a["data-attempt-id"])
        if "retry-feedback" in classes and enclosing is not None:
            self.retry_by_node[enclosing] = self.retry_by_node.get(enclosing, 0) + 1
        if tag not in self.VOID:
            self.stack.append((tag, node_id))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return


def test_ac_ui_008_attempt_history_and_retry_feedback(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_calls.log"

    foo_result = _provenance_check_result(
        "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
    )
    ok_result = _provenance_check_result("comp-ok", "pass", {"R-OK-001": "pass"})
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {"comp-foo": foo_result, "comp-ok": ok_result},
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": ["comp-foo: verification failed — run hotdocs generate comp-foo"],
    }
    _write_fake_tracker(repo_root, report, log_path)

    graph = {
        "nodes": {
            "comp-foo": _component_graph_node(foo_result["verification_report"]),
            "comp-ok": _component_graph_node(ok_result["verification_report"]),
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
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    attempts_dir.mkdir(parents=True)
    # write newest first so creation order does not match chronological order
    for aid in (ATTEMPT_B, ATTEMPT_A):
        (attempts_dir / (aid + ".json")).write_text(
            json.dumps(_attempt_record(aid, "comp-foo"), indent=2), encoding="utf-8"
        )

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # the fake ran
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines.count("check_readiness") == 1
    assert "last_requirement_failures comp-foo" in log_lines

    nodes = {field(n, "id"): n for n in field(snapshot, "nodes")}
    foo = nodes["comp-foo"]
    assert field(foo, "status") == "failing"
    attempt_ids = [field(a, "attempt_id") for a in field(foo, "attempts")]
    assert attempt_ids == [ATTEMPT_A, ATTEMPT_B]
    assert list(field(foo, "retry_feedback")) == ["R-FOO-002"]

    ok = nodes["comp-ok"]
    assert field(ok, "status") == "passing"
    assert list(field(ok, "attempts")) == []
    assert list(field(ok, "retry_feedback")) == []

    index = out_dir / "index.html"
    assert index.is_file()

    # order of data-attempt-id elements within comp-foo's node, as written
    collector = _NodeAttemptCollector()
    collector.feed(index.read_text(encoding="utf-8"))
    collector.close()
    assert collector.attempts_by_node.get("comp-foo") == [ATTEMPT_A, ATTEMPT_B]
    assert collector.retry_by_node.get("comp-ok", 0) == 0

    page = browser.open(index)
    foo_sel = 'li.node[data-node-id="comp-foo"]'
    ok_sel = 'li.node[data-node-id="comp-ok"]'
    assert page.find(css=foo_sel).count() == 1
    assert page.find(css=ok_sel).count() == 1
    assert page.find(css=foo_sel + " [data-attempt-id]").count() == 2
    assert page.find(css=foo_sel + ' [data-attempt-id="' + ATTEMPT_A + '"]').count() == 1
    assert page.find(css=foo_sel + ' [data-attempt-id="' + ATTEMPT_B + '"]').count() == 1
    retry = page.find(css=foo_sel + " .retry-feedback")
    assert retry.count() == 1
    assert retry.text().strip() == "--retry-feedback=R-FOO-002"
    assert page.find(css=ok_sel + " .retry-feedback").count() == 0
    assert page.console_errors() == []