# hotdocs-criterion: sha256:af6455d0d45fc9003debcc507f71d58abe7a3834867520e2550a72df55f29f98
"""AC-UI-003: the page has no form, no off-page href, and exactly two scripts."""

import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_REPORT = {
    "component_id": "comp-bar",
    "criteria": [
        {
            "id": "AC-BAR-002",
            "covers": "R-BAR-002",
            "kind": "compiled",
            "result": "fail",
            "failure_detail": {"message": "x equals 1 failed", "expected": 1, "actual": 2},
            "failure_origin": "implementation",
        }
    ],
    "requirement_results": {"R-BAR-002": "fail"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "fail",
}

SECRET_SCAN = {
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

VERIFY_REPORT = {
    "scope": "whole-corpus",
    "ready": False,
    "components": {
        "comp-bar": {
            "hit": True,
            "reason": None,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": {"blocked": False, "matches": []},
            "secret_scan": SECRET_SCAN,
        }
    },
    "capabilities": {},
    "secret_scan": SECRET_SCAN,
    "not_ready_reasons": [
        "comp-bar: verification failed \u2014 run hotdocs generate comp-bar"
    ],
}

CORPUS_GRAPH = {
    "nodes": {
        "comp-bar": {
            "type": "component",
            "verification": VERIFICATION_REPORT,
            "provenance": {},
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {},
        }
    },
    "edges": [],
    "aggregates": {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    },
}


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(json.dumps(VERIFY_REPORT)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    if component_id == 'comp-bar':\n"
        "        return ['R-BAR-002']\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used by this test')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


class _PageScanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = 0
        self.hrefs = []
        self.scripts = []  # list of [attrs_dict, text]
        self._in_script = None

    def handle_starttag(self, tag, attrs):
        self._tag(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._tag(tag, attrs)
        if tag == "script":
            self._in_script = None

    def _tag(self, tag, attrs):
        tag = tag.lower()
        for name, value in attrs:
            if name.lower() == "href":
                self.hrefs.append(value if value is not None else "")
        if tag == "form":
            self.forms += 1
        if tag == "script":
            entry = [{k.lower(): (v if v is not None else "") for k, v in attrs}, ""]
            self.scripts.append(entry)
            self._in_script = entry

    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script[1] += data

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self._in_script = None


def test_ac_ui_003_no_form_no_offpage_href_exactly_two_scripts(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(CORPUS_GRAPH, sort_keys=True, indent=2), encoding="utf-8"
    )
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake ran.
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert "check_readiness" in calls
    assert "last_requirement_failures comp-bar" in calls

    # Precondition: a failing component with non-empty retry_feedback.
    nodes = field(snapshot, "nodes")
    bar = [n for n in nodes if field(n, "id") == "comp-bar"]
    assert len(bar) == 1
    assert field(bar[0], "status") == "failing"
    assert list(field(bar[0], "retry_feedback")) == ["R-BAR-002"]

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    scanner = _PageScanner()
    scanner.feed(html)
    scanner.close()

    # No <form element.
    assert scanner.forms == 0

    # No href other than ones beginning with "#".
    offpage = [h for h in scanner.hrefs if not h.startswith("#")]
    assert offpage == []

    # Exactly two script elements.
    assert len(scanner.scripts) == 2, [s[0] for s in scanner.scripts]

    data_blocks = [s for s in scanner.scripts if s[0].get("id") == "tracker-snapshot"]
    module_scripts = [
        s
        for s in scanner.scripts
        if s[0].get("type", "").strip().lower() == "module"
        and s[0].get("id") != "tracker-snapshot"
    ]
    assert len(data_blocks) == 1
    assert len(module_scripts) == 1

    # The data block is JSON data and carries the failing node's feedback.
    data = json.loads(data_blocks[0][1])
    data_nodes = {n["id"]: n for n in data["nodes"]}
    assert data_nodes["comp-bar"]["status"] == "failing"
    assert data_nodes["comp-bar"]["retry_feedback"] == ["R-BAR-002"]