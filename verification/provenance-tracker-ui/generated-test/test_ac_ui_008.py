import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


FOO_ATTEMPT_IDS = [
    "2026-10-01T00:00:00Z-aaaaaa",
    "2026-10-02T00:00:00Z-bbbbbb",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Minimal HTML tree builder (stdlib only)
# ---------------------------------------------------------------------------

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class Element:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = {k: (v if v is not None else "") for k, v in attrs}
        self.parent = parent
        self.children = []  # Elements or str

    def iter(self):
        yield self
        for child in self.children:
            if isinstance(child, Element):
                yield from child.iter()

    def descendants(self):
        for child in self.children:
            if isinstance(child, Element):
                yield from child.iter()

    def text(self):
        parts = []
        for child in self.children:
            if isinstance(child, Element):
                if child.tag in ("script", "style"):
                    continue
                parts.append(child.text())
            else:
                parts.append(child)
        return "".join(parts)

    def classes(self):
        return self.attrs.get("class", "").split()


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("#root", [], None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        el = Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(el)
        if tag not in VOID_TAGS:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        el = Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(text):
    builder = TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def node_candidates(root, node_id):
    """Elements carrying an attribute whose value is exactly node_id."""
    out = []
    for el in root.iter():
        if el.tag in ("script", "style", "#root"):
            continue
        if any(v == node_id for v in el.attrs.values()):
            out.append(el)
    return out


def outer_attempt_ids(el):
    """data-attempt-id values of outermost attempt elements within el, in order."""
    ids = []

    def walk(e):
        for child in e.children:
            if not isinstance(child, Element):
                continue
            if "data-attempt-id" in child.attrs:
                ids.append(child.attrs["data-attempt-id"])
                continue
            walk(child)

    if "data-attempt-id" in el.attrs:
        return [el.attrs["data-attempt-id"]]
    walk(el)
    return ids


def retry_feedback_elements(el):
    return [d for d in el.iter() if "retry-feedback" in d.classes()]


# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------

def _verification_report(component_id, overall, requirement_results):
    criteria = []
    for i, (rid, res) in enumerate(sorted(requirement_results.items()), start=1):
        crit = {
            "id": "AC-" + rid[2:-4] + "-%03d" % i,
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            crit["failure_detail"] = {"message": "failed", "expected": 1, "actual": 0}
        criteria.append(crit)
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(requirement_results),
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": overall,
    }


def _license_scan():
    return {"blocked": False, "findings": []}


def _secret_scan():
    return {"flagged": False, "findings": []}


FAKE_TRACKER_TEMPLATE = '''
import json
from pathlib import Path

_LOG = Path({log_path!r})
_REPORT = json.loads({report_json!r})


def _log(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{"fn": "check_readiness", "changed_ids": changed_ids}})
    return json.loads(json.dumps(_REPORT))


def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    raise AssertionError("write_attempt_record must not be called")


def last_requirement_failures(component_id, repo_root):
    _log({{"fn": "last_requirement_failures", "component_id": component_id}})
    if component_id == "comp-foo":
        return ["R-FOO-002"]
    return []
'''


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    foo_vr = _verification_report(
        "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
    )
    pass_vr = _verification_report("comp-pass", "pass", {"R-PASS-001": "pass"})

    verify_report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": foo_vr,
                "license_scan": _license_scan(),
                "secret_scan": _secret_scan(),
            },
            "comp-pass": {
                "hit": True,
                "verification_report": pass_vr,
                "license_scan": _license_scan(),
                "secret_scan": _secret_scan(),
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-foo: verification failed — run hotdocs generate comp-foo"
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.format(
            log_path=str(log_path), report_json=json.dumps(verify_report)
        ),
        encoding="utf-8",
    )

    def comp_node(vr):
        return {
            "type": "component",
            "verification": vr,
            "provenance": {"gate_version": "x@1.0.0", "content_hash": "sha256:abc"},
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {"component.md": "---\nid: x\n---\n"},
        }

    corpus_graph = {
        "nodes": {
            "comp-foo": comp_node(foo_vr),
            "comp-pass": comp_node(pass_vr),
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
        json.dumps(corpus_graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    attempts_dir.mkdir(parents=True)
    # Write newest first so creation order differs from chronological order.
    for attempt_id in reversed(FOO_ATTEMPT_IDS):
        timestamp = attempt_id.rsplit("-", 1)[0]
        record = {
            "attempt_id": attempt_id,
            "component_id": "comp-foo",
            "timestamp": timestamp,
            "spec_bundle_hash": "sha256:feedface",
            "generation": {
                "component_id": "comp-foo",
                "spec_bundle_hash": "sha256:feedface",
                "model": "claude-sonnet-5",
                "prompt_version": "v1",
                "cache_hit": False,
                "files": {"foo.py": "print('hi')\n"},
                "model_call_error": None,
                "refused": None,
                "retry_feedback": None,
            },
            "verification": foo_vr,
        }
        (attempts_dir / (attempt_id + ".json")).write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )

    return repo_root, log_path


def test_ac_ui_008_attempt_history_and_retry_feedback(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake provenance-tracker was actually used.
    assert log_path.exists(), "fake provenance-tracker was never invoked"
    calls = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert any(
        c["fn"] == "last_requirement_failures" and c["component_id"] == "comp-foo"
        for c in calls
    ), calls

    # --- Snapshot ---------------------------------------------------------
    nodes = field(snapshot, "nodes")
    by_id = {field(n, "id"): n for n in nodes}
    assert "comp-foo" in by_id
    assert "comp-pass" in by_id

    foo = by_id["comp-foo"]
    assert field(foo, "status") == "failing"
    attempts = field(foo, "attempts")
    assert [field(a, "attempt_id") for a in attempts] == FOO_ATTEMPT_IDS
    assert list(field(foo, "retry_feedback")) == ["R-FOO-002"]

    # --- HTML -------------------------------------------------------------
    index = Path(out_dir) / "index.html"
    assert index.is_file()
    root = parse_html(index.read_text(encoding="utf-8"))

    foo_candidates = node_candidates(root, "comp-foo")
    assert foo_candidates, "no element identifies the comp-foo node"

    expected_text = "--retry-feedback=R-FOO-002"
    matching = []
    for el in foo_candidates:
        ids = outer_attempt_ids(el)
        rfs = retry_feedback_elements(el)
        if (
            ids == FOO_ATTEMPT_IDS
            and len(rfs) == 1
            and rfs[0].text().strip() == expected_text
        ):
            matching.append(el)
    diag = [
        (el.tag, el.attrs, outer_attempt_ids(el),
         [r.text() for r in retry_feedback_elements(el)])
        for el in foo_candidates
    ]
    assert matching, (
        "no comp-foo node element contains both attempts in order and the "
        "exact retry-feedback suggestion: %r" % (diag,)
    )

    # --- Passing component has no retry-feedback element ------------------
    pass_candidates = node_candidates(root, "comp-pass")
    assert pass_candidates, "no element identifies the comp-pass node"
    for el in pass_candidates:
        assert retry_feedback_elements(el) == [], (
            "passing component's node contains a retry-feedback element: %r"
            % (el.attrs,)
        )

    # Only the failing component carries a retry-feedback element at all.
    all_rf = retry_feedback_elements(root)
    assert len(all_rf) == 1, [r.text() for r in all_rf]
    assert all_rf[0].text().strip() == expected_text