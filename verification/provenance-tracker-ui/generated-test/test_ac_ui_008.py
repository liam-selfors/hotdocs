import json
import textwrap
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


FOO = "comp-foo"
BAR = "comp-bar"
ATTEMPT_A = "2026-10-01T00:00:00Z-aaaaaa"
ATTEMPT_B = "2026-10-02T00:00:00Z-bbbbbb"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# --------------------------------------------------------------------------
# Minimal HTML tree builder (stdlib only)
# --------------------------------------------------------------------------

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children = []  # Node or str

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.iter()

    def text(self):
        parts = []
        for c in self.children:
            if isinstance(c, Node):
                if c.tag in ("script", "style"):
                    continue
                parts.append(c.text())
            else:
                parts.append(c)
        return "".join(parts)

    def classes(self):
        return (self.attrs.get("class") or "").split()


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs},
                    self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs},
                    self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(text):
    b = TreeBuilder()
    b.feed(text)
    b.close()
    return b.root


def identifies(node, node_id):
    if node.tag in ("script", "style", "#root"):
        return False
    for k, v in node.attrs.items():
        if k == "data-attempt-id":
            continue
        if v == node_id:
            return True
    own_text = "".join(c for c in node.children if isinstance(c, str)).strip()
    return own_text == node_id


def contains_identifier(node, node_id):
    return any(identifies(n, node_id) for n in node.iter())


def node_scopes(root, node_id, other_ids):
    """For each element identifying node_id, the largest ancestor-or-self
    that contains no identifier for any other node id."""
    scopes = []
    for el in root.iter():
        if not identifies(el, node_id):
            continue
        scope = el
        while scope.parent is not None and scope.parent.tag != "#root":
            parent = scope.parent
            if any(contains_identifier(parent, o) for o in other_ids):
                break
            scope = parent
        if all(scope is not s for s in scopes):
            scopes.append(scope)
    return scopes


# --------------------------------------------------------------------------
# Fixture
# --------------------------------------------------------------------------

FAKE_TRACKER = textwrap.dedent(
    '''
    def _vr(component_id, overall, requirement_results):
        return {
            "component_id": component_id,
            "criteria": [
                {"id": rid.replace("R-", "AC-"), "covers": rid,
                 "kind": "compiled", "result": res}
                for rid, res in sorted(requirement_results.items())
            ],
            "requirement_results": dict(requirement_results),
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": overall,
        }


    def check_readiness(repo_root, changed_ids=None, model=None, seed=0,
                        llm_backend=None):
        return {
            "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
            "ready": False,
            "components": {
                "comp-foo": {
                    "hit": True,
                    "verification_report": _vr(
                        "comp-foo", "fail",
                        {"R-FOO-001": "pass", "R-FOO-002": "fail"}),
                    "license_scan": {"blocked": False, "findings": []},
                    "secret_scan": {"flagged": False, "findings": []},
                },
                "comp-bar": {
                    "hit": True,
                    "verification_report": _vr(
                        "comp-bar", "pass", {"R-BAR-001": "pass"}),
                    "license_scan": {"blocked": False, "findings": []},
                    "secret_scan": {"flagged": False, "findings": []},
                },
            },
            "capabilities": {},
            "not_ready_reasons": [
                "comp-foo: verification failed for current spec state"
            ],
        }


    def last_requirement_failures(component_id, repo_root):
        if component_id == "comp-foo":
            return ["R-FOO-002"]
        return []
    '''
)


def _attempt_record(attempt_id, timestamp):
    return {
        "attempt_id": attempt_id,
        "component_id": FOO,
        "timestamp": timestamp,
        "spec_bundle_hash": "sha256:" + attempt_id[-6:] * 4,
        "generation": {
            "component_id": FOO,
            "spec_bundle_hash": "sha256:" + attempt_id[-6:] * 4,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification": {
            "component_id": FOO,
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001",
                 "kind": "compiled", "result": "pass"},
                {"id": "AC-FOO-002", "covers": "R-FOO-002",
                 "kind": "compiled", "result": "fail",
                 "failure_detail": {"message": "m", "expected": 1, "actual": 2}},
            ],
            "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "fail",
        },
    }


def _build_repo(repo_root: Path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(FAKE_TRACKER, encoding="utf-8")

    graph = {
        "nodes": {
            BAR: {
                "type": "component", "verification": None, "provenance": None,
                "size_status": "ok", "sealed": True, "pinned_overrides": [],
                "owners": ["team"], "documents": {},
            },
            FOO: {
                "type": "component", "verification": None, "provenance": None,
                "size_status": "ok", "sealed": True, "pinned_overrides": [],
                "owners": ["team"], "documents": {},
            },
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    adir = repo_root / ".hotdocs" / "attempts" / FOO
    adir.mkdir(parents=True)
    # Write the newer one first so write order cannot masquerade as ordering.
    for attempt_id, ts in ((ATTEMPT_B, "2026-10-02T00:00:00Z"),
                           (ATTEMPT_A, "2026-10-01T00:00:00Z")):
        (adir / f"{attempt_id}.json").write_text(
            json.dumps(_attempt_record(attempt_id, ts), indent=2) + "\n",
            encoding="utf-8")


# --------------------------------------------------------------------------
# Test
# --------------------------------------------------------------------------

def test_ac_ui_008_failing_node_shows_attempts_and_retry_feedback(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # ---- snapshot ----
    nodes = {field(n, "id"): n for n in field(snapshot, "nodes")}
    assert FOO in nodes and BAR in nodes
    foo = nodes[FOO]
    assert field(foo, "status") == "failing"
    attempt_ids = [field(a, "attempt_id") for a in field(foo, "attempts")]
    assert attempt_ids == [ATTEMPT_A, ATTEMPT_B]
    assert list(field(foo, "retry_feedback")) == ["R-FOO-002"]

    bar = nodes[BAR]
    assert field(bar, "status") == "passing"
    assert list(field(bar, "retry_feedback")) == []

    # ---- page ----
    index = out_dir / "index.html"
    assert index.is_file()
    root = parse_html(index.read_text(encoding="utf-8"))

    foo_scopes = node_scopes(root, FOO, [BAR])
    assert foo_scopes, "no element identifying comp-foo's node found"

    def foo_scope_ok(scope):
        ids = [el.attrs["data-attempt-id"] for el in scope.iter()
               if "data-attempt-id" in el.attrs]
        if ids != [ATTEMPT_A, ATTEMPT_B]:
            return False
        fb = [el for el in scope.iter() if "retry-feedback" in el.classes()]
        return len(fb) == 1 and fb[0].text().strip() == "--retry-feedback=R-FOO-002"

    assert any(foo_scope_ok(s) for s in foo_scopes), (
        "comp-foo's node element does not contain one data-attempt-id element "
        "per attempt (oldest first) plus a retry-feedback element with text "
        "'--retry-feedback=R-FOO-002'"
    )

    # Every retry-feedback element on the page has the exact text.
    all_fb = [el for el in root.iter() if "retry-feedback" in el.classes()]
    assert all_fb
    for el in all_fb:
        assert el.text().strip() == "--retry-feedback=R-FOO-002"

    bar_scopes = node_scopes(root, BAR, [FOO])
    assert bar_scopes, "no element identifying comp-bar's node found"
    for scope in bar_scopes:
        assert not any("retry-feedback" in el.classes() for el in scope.iter()), (
            "passing component comp-bar's node contains a retry-feedback element"
        )