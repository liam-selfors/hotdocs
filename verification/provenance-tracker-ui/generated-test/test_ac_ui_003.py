import json
import shutil
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


FAKE_PROVENANCE_TRACKER_SOURCE = '''
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
                    "mutation_score": 0.5,
                    "overall": "fail",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-foo: verification failed -- run hotdocs generate comp-foo"
        ],
    }


def last_requirement_failures(component_id, repo_root):
    return ["R-FOO-002"]
'''


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.hrefs = []
        self.scripts = []
        self._in_script = False
        self._current_script_attrs = None
        self._current_script_content = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "form":
            self.forms.append(attrs_dict)
        if "href" in attrs_dict and attrs_dict["href"] is not None:
            self.hrefs.append(attrs_dict["href"])
        if tag == "script":
            self._in_script = True
            self._current_script_attrs = attrs_dict
            self._current_script_content = []

    def handle_endtag(self, tag):
        if tag == "script" and self._in_script:
            self.scripts.append(
                (self._current_script_attrs, "".join(self._current_script_content))
            )
            self._in_script = False
            self._current_script_attrs = None
            self._current_script_content = []

    def handle_data(self, data):
        if self._in_script:
            self._current_script_content.append(data)


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


class TestACUI003NoGenerateActionInPage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir) / "repo"
        self.out_dir = Path(self.tmpdir) / "out"

        dep_dir = self.repo_root / "gen" / "provenance-tracker"
        dep_dir.mkdir(parents=True)
        (dep_dir / "provenance_tracker.py").write_text(
            FAKE_PROVENANCE_TRACKER_SOURCE, encoding="utf-8"
        )

        verification_dir = self.repo_root / "verification"
        verification_dir.mkdir(parents=True)
        corpus_graph = {
            "nodes": {
                "comp-foo": {
                    "type": "component",
                    "verification": {
                        "component_id": "comp-foo",
                        "criteria": [],
                        "requirement_results": {"R-FOO-002": "fail"},
                        "interface_drift": False,
                        "mutation_score": 0.5,
                        "overall": "fail",
                    },
                    "provenance": {},
                    "size_status": "ok",
                    "sealed": False,
                    "pinned_overrides": [],
                }
            },
            "edges": [],
            "aggregates": {
                "orphan_capability_rate": 0.0,
                "orphan_component_rate": 0.0,
                "orphan_var_rate": 0.0,
            },
        }
        (verification_dir / "corpus-graph.json").write_text(
            json.dumps(corpus_graph), encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_form_no_generate_script_no_external_href(self):
        snapshot = provenance_tracker_ui.render_tracker_ui(
            self.out_dir,
            self.repo_root,
            changed_ids=None,
            model=None,
            seed=0,
            llm_backend=None,
        )

        nodes = _get(snapshot, "nodes")
        self.assertIsNotNone(nodes, "snapshot must expose nodes")

        foo_node = None
        for node in nodes:
            if _get(node, "id") == "comp-foo":
                foo_node = node
                break
        self.assertIsNotNone(foo_node, "expected comp-foo node in snapshot")

        status = _get(foo_node, "status")
        retry_feedback = _get(foo_node, "retry_feedback")
        self.assertEqual(status, "failing")
        self.assertTrue(
            retry_feedback, "expected non-empty retry_feedback for the failing component"
        )

        index_path = self.out_dir / "index.html"
        self.assertTrue(index_path.exists(), "render_tracker_ui must write index.html")
        html_text = index_path.read_text(encoding="utf-8")

        parser = PageParser()
        parser.feed(html_text)

        self.assertEqual(parser.forms, [], "page must contain no <form> element")

        for href in parser.hrefs:
            self.assertTrue(
                href.startswith("#"),
                "href %r must begin with '#'" % (href,),
            )

        self.assertTrue(parser.scripts, "page must contain at least one <script> element")

        found_snapshot_block = False
        for attrs, content in parser.scripts:
            script_id = attrs.get("id")
            if script_id == "tracker-snapshot":
                found_snapshot_block = True
                data = json.loads(content.strip())
                reasons = data.get("not_ready_reasons", [])
                joined = " ".join(reasons)
                self.assertIn(
                    "hotdocs generate",
                    joined,
                    "the data block's not_ready_reasons should carry the verbatim "
                    "retry command for this fixture",
                )
                continue
            self.assertNotIn(
                "hotdocs generate",
                content,
                "no executable script element may contain 'hotdocs generate'",
            )

        self.assertTrue(
            found_snapshot_block,
            "expected an id=\"tracker-snapshot\" script data block in the page",
        )


if __name__ == "__main__":
    unittest.main()