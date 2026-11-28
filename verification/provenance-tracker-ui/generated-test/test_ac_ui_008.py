# hotdocs-criterion: sha256:63eeeaa68a266433c3f44b6c0983f71b624690134623941d5c34f9949dfd577f
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


OLD_ID = "2026-10-01T00:00:00Z-aaaaaa"
NEW_ID = "2026-10-02T00:00:00Z-bbbbbb"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall, requirement_results):
    criteria = []
    for i, (rid, res) in enumerate(sorted(requirement_results.items()), start=1):
        crit = {
            "id": "AC-" + rid[2:-4] + "-00" + str(i) if False else "AC-FOO-00" + str(i),
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            crit["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
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
    return {"blocked": False, "matches": [], "gate_version": "license_scanner@1.0.0"}


def _generation(component_id):
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


def _attempt_record(attempt_id):
    timestamp = attempt_id.split("Z-")[0] + "Z"
    return {
        "attempt_id": attempt_id,
        "component_id": "comp-foo",
        "timestamp": timestamp,
        "spec_bundle_hash": "sha256:abc",
        "generation": _generation("comp-foo"),
        "verification": _verification_report(
            "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
        ),
    }


def _graph_component_node(verification):
    return {
        "type": "component",
        "verification": verification,
        "provenance": {"spec_bundle_hash": "sha256:abc"},
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {"component.md": "---\nid: x\n---\n"},
    }


def _build_repo(repo_root, log_path):
    foo_report = _verification_report(
        "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
    )
    pass_report = _verification_report("comp-pass", "pass", {"R-PASS-001": "pass"})

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
            "comp-pass": {
                "hit": True,
                "reason": None,
                "verification_report": pass_report,
                "license_scan": _license_scan(),
                "secret_scan": _secret_scan(),
            },
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": ["comp-foo: verification failed"],
    }

    # Corpus graph
    graph = {
        "nodes": {
            "comp-foo": _graph_component_node(foo_report),
            "comp-pass": _graph_component_node(pass_report),
        },
        "edges": [],
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

    # Attempt records (written newest first, so order cannot come from write order)
    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    attempts_dir.mkdir(parents=True)
    for aid in (NEW_ID, OLD_ID):
        (attempts_dir / (aid + ".json")).write_text(
            json.dumps(_attempt_record(aid), indent=2), encoding="utf-8"
        )

    # Fake provenance-tracker
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        "from pathlib import Path\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(verify_report) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    report = copy.deepcopy(_REPORT)\n"
        "    report['scope'] = 'whole-corpus' if changed_ids is None else 'blast-radius'\n"
        "    return report\n"
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
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


class _AttemptOrderParser(HTMLParser):
    """Collects data-attempt-id values, in document order, inside the
    element carrying data-node-id == target."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, target):
        super().__init__()
        self.target = target
        self.depth = 0  # >0 while inside target node
        self.ids = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.depth == 0:
            if a.get("data-node-id") == self.target and tag not in self.VOID:
                self.depth = 1
            return
        if "data-attempt-id" in a:
            self.ids.append(a["data-attempt-id"])
        if tag not in self.VOID:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.depth > 0:
            a = dict(attrs)
            if "data-attempt-id" in a:
                self.ids.append(a["data-attempt-id"])

    def handle_endtag(self, tag):
        if self.depth > 0 and tag not in self.VOID:
            self.depth -= 1


def _node(snapshot, node_id):
    matches = [n for n in field(snapshot, "nodes") if field(n, "id") == node_id]
    assert len(matches) == 1, matches
    return matches[0]


def test_ac_ui_008_attempt_history_and_retry_feedback(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_calls.log"
    _build_repo(repo_root, log_path)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Snapshot: comp-foo
    foo = _node(snapshot, "comp-foo")
    assert field(foo, "status") == "failing"
    attempt_ids = [field(a, "attempt_id") for a in field(foo, "attempts")]
    assert attempt_ids == [OLD_ID, NEW_ID]
    assert list(field(foo, "retry_feedback")) == ["R-FOO-002"]

    # Snapshot: passing component
    passing = _node(snapshot, "comp-pass")
    assert field(passing, "status") == "passing"
    assert list(field(passing, "retry_feedback")) == []

    # The fake's feedback lookup ran for comp-foo
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert "last_requirement_failures comp-foo" in calls

    index = out_dir / "index.html"
    assert index.is_file()

    # Order of attempt elements inside comp-foo's node, in document order
    parser = _AttemptOrderParser("comp-foo")
    parser.feed(index.read_text(encoding="utf-8"))
    assert parser.ids == [OLD_ID, NEW_ID]

    # Page as shown in the browser
    page = browser.open(index)
    foo_sel = 'li.node[data-node-id="comp-foo"]'
    pass_sel = 'li.node[data-node-id="comp-pass"]'

    assert page.find(css=foo_sel).count() == 1
    assert page.find(css=foo_sel + " [data-attempt-id]").count() == 2
    assert page.find(css=foo_sel + ' [data-attempt-id="' + OLD_ID + '"]').count() == 1
    assert page.find(css=foo_sel + ' [data-attempt-id="' + NEW_ID + '"]').count() == 1

    feedback = page.find(css=foo_sel + " .retry-feedback")
    assert feedback.count() == 1
    assert feedback.text().strip() == "--retry-feedback=R-FOO-002"

    assert page.find(css=pass_sel).count() == 1
    assert page.find(css=pass_sel + " .retry-feedback").count() == 0