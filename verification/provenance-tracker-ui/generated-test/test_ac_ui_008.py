# hotdocs-criterion: sha256:2a791eb73d0cb78fa13a71c009c1af2580a5fc93965c29b18aab077e91ac83c8
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class Element:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children = []
        self.texts = []

    def iter(self):
        yield self
        for child in self.children:
            if isinstance(child, Element):
                yield from child.iter()

    def text(self):
        parts = []
        for child in self.children:
            if isinstance(child, Element):
                parts.append(child.text())
            else:
                parts.append(child)
        return "".join(parts)

    def classes(self):
        return (self.attrs.get("class") or "").split()


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("#root", {}, None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        attr_map = {k: (v if v is not None else "") for k, v in attrs}
        el = Element(tag, attr_map, self.stack[-1])
        self.stack[-1].children.append(el)
        if tag not in VOID_TAGS:
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        attr_map = {k: (v if v is not None else "") for k, v in attrs}
        el = Element(tag, attr_map, self.stack[-1])
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


def elements_tagged_with(root, value):
    out = []
    for el in root.iter():
        for name, attr_value in el.attrs.items():
            if name == "data-attempt-id":
                continue
            if attr_value == value:
                out.append(el)
                break
    return out


def attempt_ids_in(el):
    return [e.attrs["data-attempt-id"] for e in el.iter() if "data-attempt-id" in e.attrs]


def retry_feedback_texts_in(el):
    return [e.text().strip() for e in el.iter() if "retry-feedback" in e.classes()]


ATTEMPT_OLD = "2026-10-01T00:00:00Z-aaaaaa"
ATTEMPT_NEW = "2026-10-02T00:00:00Z-bbbbbb"


def verification_report(component_id, overall, results):
    criteria = []
    for i, (rid, res) in enumerate(sorted(results.items()), start=1):
        crit = {
            "id": "AC-" + rid[2:],
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            crit["failure_origin"] = "implementation"
            crit["failure_detail"] = {"message": "failed", "expected": 1, "actual": 0}
        criteria.append(crit)
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(results),
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": overall,
    }


def attempt_record(attempt_id, component_id):
    timestamp = attempt_id.rsplit("-", 1)[0]
    return {
        "attempt_id": attempt_id,
        "component_id": component_id,
        "timestamp": timestamp,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "generation": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"foo.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification": verification_report(
            component_id, "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
        ),
    }


def build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

    # Corpus graph
    graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["team-a"],
                "documents": {},
            },
            "comp-pass": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["team-a"],
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

    # Attempt records (newer written first, so ordering can't come from write order)
    attempts_dir = repo_root / ".hotdocs" / "attempts" / "comp-foo"
    attempts_dir.mkdir(parents=True)
    for aid in (ATTEMPT_NEW, ATTEMPT_OLD):
        (attempts_dir / (aid + ".json")).write_text(
            json.dumps(attempt_record(aid, "comp-foo"), indent=2), encoding="utf-8"
        )

    # Fake provenance-tracker
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report(
                    "comp-foo", "fail", {"R-FOO-001": "pass", "R-FOO-002": "fail"}
                ),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
            "comp-pass": {
                "hit": True,
                "verification_report": verification_report(
                    "comp-pass", "pass", {"R-PASS-001": "pass"}
                ),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-foo: verification failed — run hotdocs generate comp-foo"
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        "import json\n"
        "\n"
        "_LOG_PATH = " + repr(str(log_path)) + "\n"
        "_REPORT_JSON = " + repr(json.dumps(report)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(_REPORT_JSON)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    if component_id == " + repr("comp-foo") + ":\n"
        "        return [" + repr("R-FOO-002") + "]\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    return repo_root, log_path


def test_ac_ui_008_attempt_history_and_retry_feedback(tmp_path):
    repo_root, log_path = build_fixture(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake provenance-tracker was the one consulted
    assert log_path.is_file(), "fake provenance_tracker was never called"
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert "check_readiness" in log_lines

    # Snapshot assertions
    nodes = field(snapshot, "nodes")
    by_id = {field(n, "id"): n for n in nodes}
    assert "comp-foo" in by_id
    foo = by_id["comp-foo"]
    assert field(foo, "status") == "failing"
    attempts = field(foo, "attempts")
    assert [field(a, "attempt_id") for a in attempts] == [ATTEMPT_OLD, ATTEMPT_NEW]
    assert list(field(foo, "retry_feedback")) == ["R-FOO-002"]

    # HTML assertions
    index = out_dir / "index.html"
    assert index.is_file()
    root = parse_html(index.read_text(encoding="utf-8"))

    foo_candidates = elements_tagged_with(root, "comp-foo")
    assert foo_candidates, "no element identifies comp-foo's node"
    expected_feedback = "--retry-feedback=R-FOO-002"
    matching = [
        el for el in foo_candidates
        if attempt_ids_in(el) == [ATTEMPT_OLD, ATTEMPT_NEW]
        and retry_feedback_texts_in(el) == [expected_feedback]
    ]
    assert matching, (
        "no comp-foo node element contains exactly the two data-attempt-id "
        "elements in oldest-first order and one retry-feedback element with text "
        + repr(expected_feedback)
        + "; candidates: "
        + repr([(attempt_ids_in(el), retry_feedback_texts_in(el)) for el in foo_candidates])
    )

    # Passing component: no retry-feedback element in its node
    pass_candidates = elements_tagged_with(root, "comp-pass")
    assert pass_candidates, "no element identifies comp-pass's node"
    for el in pass_candidates:
        assert retry_feedback_texts_in(el) == [], (
            "passing component's node contains a retry-feedback element"
        )