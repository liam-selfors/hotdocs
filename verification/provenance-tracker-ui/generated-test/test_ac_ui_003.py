# hotdocs-criterion: sha256:c966c5190082c5f9218fbf0f22207b4dee961b61f1ac6a48c134a37083c2d619
"""AC-UI-003: the rendered page holds no form, no off-page link, and exactly
two script elements: the tracker-snapshot JSON data block and one module
script whose text is static/app.js's text followed by "\\ninit(document);\\n".
"""

import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall, results):
    criteria = []
    n = 0
    for rid, res in sorted(results.items()):
        n += 1
        crit = {
            "id": "AC-" + rid[2:-4] + "-00" + str(n),
            "covers": rid,
            "kind": "compiled",
            "result": res,
        }
        if res == "fail":
            crit["failure_detail"] = {
                "message": "value equals 5 failed",
                "expected": 5,
                "actual": 3,
            }
            crit["failure_origin"] = "implementation"
        criteria.append(crit)
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": dict(results),
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
    return {"blocked": False, "matches": []}


def _provenance_hit(component_id, overall, results):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall, results),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


def _build_repo(repo_root, log_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-bar": _provenance_hit(
                "comp-bar", "fail", {"R-BAR-001": "pass", "R-BAR-002": "fail"}
            ),
            "comp-foo": _provenance_hit("comp-foo", "pass", {"R-FOO-001": "pass"}),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-bar: verification failed — run hotdocs generate comp-bar"
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
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
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used by this test')\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + component_id)\n"
        "    if component_id == 'comp-bar':\n"
        "        return ['R-BAR-002']\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    def comp_node(slug, overall, results):
        cid = "comp-" + slug
        return {
            "type": "component",
            "verification": _verification_report(cid, overall, results),
            "provenance": {"component_id": cid, "spec_bundle_hash": "sha256:00"},
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {"component.md": "# " + cid + "\n"},
        }

    graph = {
        "nodes": {
            "comp-bar": comp_node(
                "bar", "fail", {"R-BAR-001": "pass", "R-BAR-002": "fail"}
            ),
            "comp-foo": comp_node("foo", "pass", {"R-FOO-001": "pass"}),
        },
        "edges": [{"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"}],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    ver = repo_root / "verification"
    ver.mkdir(parents=True)
    (ver / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tags = []
        self.scripts = []
        self._in_script = None

    def _start(self, tag, attrs):
        tag = tag.lower()
        self.tags.append((tag, attrs))
        if tag == "script":
            entry = {"attrs": dict(attrs), "text": ""}
            self.scripts.append(entry)
            self._in_script = entry

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs)
        if tag.lower() == "script":
            self._in_script = None

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self._in_script = None

    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script["text"] += data


def test_ac_ui_003_page_has_no_actions_and_only_two_scripts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_repo(repo_root, log_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Precondition: the snapshot has a failing component with non-empty retry_feedback.
    nodes = field(snapshot, "nodes")
    by_id = {field(n, "id"): n for n in nodes}
    assert "comp-bar" in by_id
    assert field(by_id["comp-bar"], "status") == "failing"
    assert list(field(by_id["comp-bar"], "retry_feedback")) == ["R-BAR-002"]
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    parser = _PageParser()
    parser.feed(html)
    parser.close()

    # No <form element.
    assert [t for t, _ in parser.tags if t == "form"] == []

    # No href attribute other than ones beginning with "#".
    hrefs = [
        value
        for _, attrs in parser.tags
        for name, value in attrs
        if name.lower() == "href"
    ]
    bad = [h for h in hrefs if h is None or not h.startswith("#")]
    assert bad == []

    # Exactly two script elements.
    assert len(parser.scripts) == 2, [s["attrs"] for s in parser.scripts]

    data_blocks = [s for s in parser.scripts if s["attrs"].get("id") == "tracker-snapshot"]
    module_scripts = [s for s in parser.scripts if s["attrs"].get("type") == "module"]
    assert len(data_blocks) == 1
    assert len(module_scripts) == 1
    assert data_blocks[0] is not module_scripts[0]

    # The data block is the snapshot's JSON.
    json.loads(data_blocks[0]["text"])

    app_js = (
        Path(provenance_tracker_ui.__file__).parent / "static" / "app.js"
    ).read_text(encoding="utf-8")
    assert module_scripts[0]["text"] == app_js + "\ninit(document);\n"