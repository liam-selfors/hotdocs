# hotdocs-criterion: sha256:3eb54c5591cfdf95d0d3024ccf71d0e50d759ed2ca763a9885d38441d2f87070
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall, r_results, criteria):
    return {
        "component_id": component_id,
        "criteria": criteria,
        "requirement_results": r_results,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": overall,
    }


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

    foo_vr = _verification_report(
        "comp-foo",
        "pass",
        {"R-FOO-001": "pass"},
        [{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}],
    )
    bar_vr = _verification_report(
        "comp-bar",
        "fail",
        {"R-BAR-001": "pass", "R-BAR-002": "fail"},
        [
            {"id": "AC-BAR-001", "covers": "R-BAR-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-BAR-002",
                "covers": "R-BAR-002",
                "kind": "generated-test",
                "result": "fail",
                "failure_origin": "implementation",
                "failure_detail": {"message": "x equals 5 failed", "expected": 5, "actual": 3},
            },
        ],
    )

    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": foo_vr,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
            "comp-bar": {
                "hit": True,
                "verification_report": bar_vr,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            "comp-bar: verification failed for current spec state — run hotdocs generate comp-bar"
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT_TEXT = " + repr(json.dumps(report)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(REPORT_TEXT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    if component_id == 'comp-bar':\n"
        "        return ['R-BAR-002']\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    def comp_node(vr):
        return {
            "type": "component",
            "verification": vr,
            "provenance": {"component_id": "x"},
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["team-a"],
            "documents": {"component.md": "text"},
        }

    graph = {
        "nodes": {
            "comp-bar": comp_node(bar_vr),
            "comp-foo": comp_node(foo_vr),
        },
        "edges": [{"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"}],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    ver = repo_root / "verification"
    ver.mkdir()
    (ver / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    attempt_id = "2026-10-25T14:32:01Z-a1b2c3"
    attempt = {
        "attempt_id": attempt_id,
        "component_id": "comp-bar",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:abc",
        "generation": {
            "component_id": "comp-bar",
            "spec_bundle_hash": "sha256:abc",
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"bar.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification": bar_vr,
    }
    adir = repo_root / ".hotdocs" / "attempts" / "comp-bar"
    adir.mkdir(parents=True)
    (adir / (attempt_id + ".json")).write_text(json.dumps(attempt), encoding="utf-8")

    return repo_root, log_path


class _Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = 0
        self.hrefs = []
        self.scripts = []  # list of [attrs_dict, text]
        self._in_script = None

    def _tag(self, tag, attrs):
        t = tag.lower()
        if t == "form":
            self.forms += 1
        for name, value in attrs:
            if name.lower() == "href":
                self.hrefs.append(value)
        return t

    def handle_starttag(self, tag, attrs):
        t = self._tag(tag, attrs)
        if t == "script":
            entry = [dict((k.lower(), v) for k, v in attrs), ""]
            self.scripts.append(entry)
            self._in_script = entry

    def handle_startendtag(self, tag, attrs):
        t = self._tag(tag, attrs)
        if t == "script":
            self.scripts.append([dict((k.lower(), v) for k, v in attrs), ""])

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self._in_script = None

    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script[1] += data


def test_page_has_no_form_no_generate_script_no_external_href(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # Precondition: the fake was used and the failing component has retry_feedback.
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text(encoding="utf-8")
    bar = [n for n in field(snapshot, "nodes") if field(n, "id") == "comp-bar"]
    assert len(bar) == 1
    assert field(bar[0], "status") == "failing"
    assert list(field(bar[0], "retry_feedback")) == ["R-BAR-002"]

    html_path = out_dir / "index.html"
    assert html_path.is_file()
    html = html_path.read_text(encoding="utf-8")

    inspector = _Inspector()
    inspector.feed(html)
    inspector.close()

    # No <form element.
    assert inspector.forms == 0
    executable = [s for s in inspector.scripts if s[0].get("id") != "tracker-snapshot"]
    # Raw check for "<form" outside the data block too.
    stripped = html
    for attrs, text in inspector.scripts:
        if attrs.get("id") == "tracker-snapshot" and text:
            stripped = stripped.replace(text, "")
    assert "<form" not in stripped.lower()

    # No "hotdocs generate" inside any executable script element.
    for attrs, text in executable:
        assert "hotdocs generate" not in text, attrs

    # Every href begins with "#".
    for href in inspector.hrefs:
        assert href is not None and href.startswith("#"), href