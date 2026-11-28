# hotdocs-criterion: sha256:13437767bbb37537a5cf4612bd07b105bef53eddb4024347e0a3a7150a563de2
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tags = []
        self.scripts = []
        self._in_script = None

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag.lower(), list(attrs)))
        if tag.lower() == "script":
            self._in_script = {"attrs": dict(attrs), "text": ""}
            self.scripts.append(self._in_script)

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag.lower(), list(attrs)))
        if tag.lower() == "script":
            self.scripts.append({"attrs": dict(attrs), "text": ""})

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self._in_script = None

    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script["text"] += data


def _verification_report(component_id, overall, req_results):
    criteria = []
    n = 1
    for rid, res in sorted(req_results.items()):
        crit = {
            "id": "AC-" + rid[2:-4] + "-" + ("%03d" % n),
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
        "requirement_results": req_results,
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


def _build_repo(repo_root, log_path):
    foo_vr = _verification_report("comp-foo", "pass", {"R-FOO-001": "pass"})
    bar_vr = _verification_report(
        "comp-bar", "fail", {"R-BAR-001": "pass", "R-BAR-002": "fail"}
    )
    license_scan = {"blocked": False}
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": foo_vr,
                "license_scan": license_scan,
                "secret_scan": _secret_scan(),
            },
            "comp-bar": {
                "hit": True,
                "reason": None,
                "verification_report": bar_vr,
                "license_scan": license_scan,
                "secret_scan": _secret_scan(),
            },
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-bar: verification failed \u2014 run hotdocs generate comp-bar"
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = json.loads(" + repr(json.dumps(report)) + ")\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(json.dumps(REPORT))\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + component_id)\n"
        "    if component_id == 'comp-bar':\n"
        "        return ['R-BAR-002']\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")

    def comp_node(vr):
        return {
            "type": "component",
            "verification": vr,
            "provenance": {"component_id": "x"},
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {},
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
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def test_ac_ui_003_no_actions_only_two_scripts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake.log"
    _build_repo(repo_root, log_path)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake ran.
    log = log_path.read_text(encoding="utf-8").splitlines()
    assert log.count("check_readiness") == 1
    assert "last_requirement_failures comp-bar" in log

    # Given: a failing component with non-empty retry_feedback.
    nodes = {field(n, "id"): n for n in field(snapshot, "nodes")}
    assert field(nodes["comp-bar"], "status") == "failing"
    assert list(field(nodes["comp-bar"], "retry_feedback")) == ["R-BAR-002"]

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    parser = _Collector()
    parser.feed(html)
    parser.close()

    # No <form element.
    assert [t for t, _ in parser.tags if t == "form"] == []
    assert "<form" not in html.lower()

    # Every href begins with "#".
    hrefs = [
        v for _, attrs in parser.tags for k, v in attrs if k.lower() == "href"
    ]
    for href in hrefs:
        assert href is not None and href.startswith("#"), href

    # Exactly two script elements.
    assert len(parser.scripts) == 2, parser.scripts
    data_blocks = [
        s for s in parser.scripts if s["attrs"].get("id") == "tracker-snapshot"
    ]
    modules = [s for s in parser.scripts if s["attrs"].get("type") == "module"]
    assert len(data_blocks) == 1
    assert len(modules) == 1
    assert data_blocks[0] is not modules[0]

    # The data block is JSON data.
    json.loads(data_blocks[0]["text"])

    app_js = (
        Path(provenance_tracker_ui.__file__).parent / "static" / "app.js"
    ).read_text(encoding="utf-8")
    assert modules[0]["text"] == app_js + "\ninit(document);\n"