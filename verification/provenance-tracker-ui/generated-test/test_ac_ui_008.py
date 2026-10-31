import json
import shutil
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _Elem:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.children = []


def _text(elem):
    parts = []
    for c in elem.children:
        if isinstance(c, str):
            parts.append(c)
        else:
            parts.append(_text(c))
    return "".join(parts)


def _walk(elem):
    yield elem
    for c in elem.children:
        if not isinstance(c, str):
            for d in _walk(c):
                yield d


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Elem("[root]", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        elem = _Elem(tag, dict(attrs))
        self.stack[-1].children.append(elem)
        if tag not in _VOID_TAGS:
            self.stack.append(elem)

    def handle_startendtag(self, tag, attrs):
        elem = _Elem(tag, dict(attrs))
        self.stack[-1].children.append(elem)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


_PROVENANCE_TRACKER_FAKE = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "whole-corpus" if changed_ids is None else "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [],
                    "requirement_results": {"R-FOO-002": "fail"},
                    "interface_drift": False,
                    "mutation_score": 0.0,
                    "overall": "fail",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
            "comp-bar": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-bar",
                    "criteria": [],
                    "requirement_results": {},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            },
        },
        "capabilities": {},
        "not_ready_reasons": ["comp-foo: verification failed"],
    }


def last_requirement_failures(component_id, repo_root):
    if component_id == "comp-foo":
        return ["R-FOO-002"]
    return []
'''


class RenderTrackerUiAttemptHistoryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.repo_root = Path(self._tmp) / "repo"
        self.out_dir = Path(self._tmp) / "out"
        self.repo_root.mkdir()
        self.out_dir.mkdir()
        self._write_fake_provenance_tracker()
        self._write_corpus_graph()
        self._write_attempt_records()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_fake_provenance_tracker(self):
        dep_dir = self.repo_root / "gen" / "provenance-tracker"
        dep_dir.mkdir(parents=True)
        (dep_dir / "provenance_tracker.py").write_text(_PROVENANCE_TRACKER_FAKE)

    def _write_corpus_graph(self):
        verification_dir = self.repo_root / "verification"
        verification_dir.mkdir(parents=True)
        graph = {
            "nodes": {
                "comp-foo": {
                    "type": "component", "verification": None, "provenance": None,
                    "size_status": "ok", "sealed": False, "pinned_overrides": [],
                },
                "comp-bar": {
                    "type": "component", "verification": None, "provenance": None,
                    "size_status": "ok", "sealed": False, "pinned_overrides": [],
                },
            },
            "edges": [],
            "aggregates": {
                "orphan_capability_rate": 0.0,
                "orphan_component_rate": 0.0,
                "orphan_var_rate": 0.0,
            },
        }
        (verification_dir / "corpus-graph.json").write_text(json.dumps(graph))

    def _write_attempt_records(self):
        attempts_dir = self.repo_root / ".hotdocs" / "attempts" / "comp-foo"
        attempts_dir.mkdir(parents=True)

        record_a = {
            "attempt_id": "2026-10-01T00:00:00Z-aaaaaa",
            "component_id": "comp-foo",
            "timestamp": "2026-10-01T00:00:00Z",
            "spec_bundle_hash": "sha256:aaa",
            "generation": {
                "component_id": "comp-foo",
                "spec_bundle_hash": "sha256:aaa",
                "model": "claude-sonnet-5",
                "prompt_version": "v1",
                "cache_hit": False,
                "files": {"comp_foo.py": "x = 1"},
                "model_call_error": None,
                "refused": None,
                "retry_feedback": None,
            },
            "verification": {
                "component_id": "comp-foo",
                "criteria": [],
                "requirement_results": {"R-FOO-002": "fail"},
                "interface_drift": False,
                "mutation_score": 0.0,
                "overall": "fail",
            },
        }
        record_b = {
            "attempt_id": "2026-10-02T00:00:00Z-bbbbbb",
            "component_id": "comp-foo",
            "timestamp": "2026-10-02T00:00:00Z",
            "spec_bundle_hash": "sha256:bbb",
            "generation": {
                "component_id": "comp-foo",
                "spec_bundle_hash": "sha256:bbb",
                "model": "claude-sonnet-5",
                "prompt_version": "v1",
                "cache_hit": False,
                "files": {"comp_foo.py": "x = 2"},
                "model_call_error": None,
                "refused": None,
                "retry_feedback": ["R-FOO-002"],
            },
            "verification": {
                "component_id": "comp-foo",
                "criteria": [],
                "requirement_results": {"R-FOO-002": "fail"},
                "interface_drift": False,
                "mutation_score": 0.0,
                "overall": "fail",
            },
        }

        (attempts_dir / "2026-10-01T00:00:00Z-aaaaaa.json").write_text(json.dumps(record_a))
        (attempts_dir / "2026-10-02T00:00:00Z-bbbbbb.json").write_text(json.dumps(record_b))

    def test_attempt_history_and_retry_feedback_in_ui(self):
        import provenance_tracker_ui

        snapshot = provenance_tracker_ui.render_tracker_ui(self.out_dir, self.repo_root)

        nodes = _get(snapshot, "nodes")
        nodes_by_id = {_get(n, "id"): n for n in nodes}

        foo_node = nodes_by_id["comp-foo"]
        bar_node = nodes_by_id["comp-bar"]

        self.assertEqual(_get(foo_node, "status"), "failing")
        self.assertEqual(_get(bar_node, "status"), "passing")

        foo_attempts = _get(foo_node, "attempts")
        self.assertEqual(len(foo_attempts), 2)
        self.assertEqual(
            [_get(a, "attempt_id") for a in foo_attempts],
            ["2026-10-01T00:00:00Z-aaaaaa", "2026-10-02T00:00:00Z-bbbbbb"],
        )
        self.assertEqual(_get(foo_node, "retry_feedback"), ["R-FOO-002"])

        self.assertEqual(_get(bar_node, "attempts"), [])
        self.assertEqual(_get(bar_node, "retry_feedback"), [])

        index_html = self.out_dir / "index.html"
        self.assertTrue(index_html.exists())
        html_text = index_html.read_text()

        builder = _TreeBuilder()
        builder.feed(html_text)
        all_elems = list(_walk(builder.root))

        attempt_elems = [e for e in all_elems if "data-attempt-id" in e.attrs]
        self.assertEqual(
            [e.attrs["data-attempt-id"] for e in attempt_elems],
            ["2026-10-01T00:00:00Z-aaaaaa", "2026-10-02T00:00:00Z-bbbbbb"],
        )

        retry_elems = [
            e for e in all_elems
            if "retry-feedback" in (e.attrs.get("class") or "").split()
        ]
        self.assertEqual(len(retry_elems), 1)
        self.assertEqual(_text(retry_elems[0]), "--retry-feedback=R-FOO-002")


if __name__ == "__main__":
    unittest.main()