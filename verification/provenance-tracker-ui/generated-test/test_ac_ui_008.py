# hotdocs-criterion: sha256:06316988dd417f7fb73d2ae82ddb6b181e2655862ebf686d1caf5deac145fef1
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


ATTEMPT_A = "2026-10-01T00:00:00Z-aaaaaa"
ATTEMPT_B = "2026-10-02T00:00:00Z-bbbbbb"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "source", "track", "wbr", "param", "keygen",
}


class Elem:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []
        self.texts = []

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Elem):
                for d in c.iter():
                    yield d

    def text(self):
        parts = []
        for c in self.children:
            if isinstance(c, Elem):
                parts.append(c.text())
            else:
                parts.append(c)
        return "".join(parts)


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Elem("#root", [], None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        el = Elem(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(el)
        if tag not in VOID:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        el = Elem(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse(html_text):
    b = TreeBuilder()
    b.feed(html_text)
    b.close()
    return b.root


def find_node(root, node_id):
    candidates = [e for e in root.iter() if e.attrs.get("data-node-id") == node_id]
    assert candidates, "no element with data-node-id " + node_id
    preferred = [e for e in candidates if e.tag == "li" and "node" in e.classes()]
    return preferred[0] if preferred else candidates[0]


def generation_result(component_id):
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


def verification_report(component_id, overall, req_results):
    criteria = []
    n = 1
    for rid, res in sorted(req_results.items()):
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
        n += 1
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(req_results),
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def attempt_record(attempt_id, component_id):
    return {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": attempt_id.split("Z-")[0] + "Z",
        "spec_bundle_hash": "sha256:abc",
        "generation": generation_result(component_id),
        "verification": verification_report(
            component_id, "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
        ),
    }


def license_scan():
    return {"blocked": False, "matches": []}


def secret_scan():
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


def build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    foo_result = {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(
            "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
        ),
        "license_scan": license_scan(),
        "secret_scan": secret_scan(),
    }
    pass_result = {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(
            "comp-pass", "pass", {"R-PASS-001": "pass"}
        ),
        "license_scan": license_scan(),
        "secret_scan": secret_scan(),
    }
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {"comp-foo": foo_result, "comp-pass": pass_result},
        "capabilities": {},
        "secret_scan": secret_scan(),
        "not_ready_reasons": ["comp-foo: verification failed"],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "import json\n"
        "\n"
        "_REPORT = json.loads(" + repr(json.dumps(report)) + ")\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(json.dumps(_REPORT))\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    if component_id == 'comp-foo':\n"
        "        return ['R-FOO-002']\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")

    graph = {
        "nodes": {
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
            "comp-pass": {
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
    # Write newer first so ordering cannot come from write order.
    for aid in (ATTEMPT_B, ATTEMPT_A):
        (attempts_dir / (aid + ".json")).write_text(
            json.dumps(attempt_record(aid, "comp-foo"), indent=2), encoding="utf-8"
        )

    return repo_root, log_path


def test_ac_ui_008_attempt_history_and_retry_feedback(tmp_path):
    repo_root, log_path = build_fixture(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Fake ran.
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert "check_readiness" in log_lines
    assert "last_requirement_failures comp-foo" in log_lines

    nodes = field(snapshot, "nodes")
    by_id = {field(n, "id"): n for n in nodes}
    assert "comp-foo" in by_id
    assert "comp-pass" in by_id

    foo = by_id["comp-foo"]
    assert field(foo, "status") == "failing"
    attempts = field(foo, "attempts")
    assert [field(a, "attempt_id") for a in attempts] == [ATTEMPT_A, ATTEMPT_B]
    assert list(field(foo, "retry_feedback")) == ["R-FOO-002"]

    passing = by_id["comp-pass"]
    assert field(passing, "status") == "passing"
    assert list(field(passing, "retry_feedback")) == []

    index = out_dir / "index.html"
    assert index.is_file()
    root = parse(index.read_text(encoding="utf-8"))

    foo_el = find_node(root, "comp-foo")
    attempt_ids = [
        e.attrs.get("data-attempt-id")
        for e in foo_el.iter()
        if e is not foo_el and "data-attempt-id" in e.attrs
    ]
    assert attempt_ids == [ATTEMPT_A, ATTEMPT_B]

    feedback = [e for e in foo_el.iter() if "retry-feedback" in e.classes()]
    assert len(feedback) == 1
    assert feedback[0].text().strip() == "--retry-feedback=R-FOO-002"

    pass_el = find_node(root, "comp-pass")
    assert not [e for e in pass_el.iter() if "retry-feedback" in e.classes()]