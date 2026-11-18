# hotdocs-criterion: sha256:50fd51198ecfcf834037a752e22436df140bb7e9158eeccb7f0b9a8758981f2b
import dataclasses
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    elif not isinstance(value, (dict, list, str, int, float, bool, type(None))):
        if hasattr(value, "to_dict"):
            value = value.to_dict()
    return json.loads(json.dumps(value))


def make_verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": "pass",
    }


def make_report(not_ready_reasons, ready):
    return {
        "scope": "whole-corpus",
        "ready": ready,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": make_verification_report(),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": not_ready_reasons,
    }


def build_repo(repo_root, report, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "import json\n"
        "REPORT_JSON = " + repr(json.dumps(report)) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return json.loads(REPORT_JSON)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('last_requirement_failures ' + str(component_id) + '\\n')\n"
        "    return []\n"
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
            }
        },
        "edges": [],
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


class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.snapshot_blocks = []
        self._in_snapshot = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append((tag, d))
        if (
            tag == "script"
            and d.get("id") == "tracker-snapshot"
            and d.get("type") == "application/json"
        ):
            self._in_snapshot = True
            self._buf = []

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        if self._in_snapshot:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_snapshot:
            self._in_snapshot = False
            self.snapshot_blocks.append("".join(self._buf))


def is_external(url):
    u = (url or "").strip().lower()
    if u == "" or u.startswith("#"):
        return False
    if u.startswith("data:") or u.startswith("javascript:") or u.startswith("about:"):
        return False
    return True


def run_render(tmp_path, monkeypatch, report):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake.log"
    build_repo(repo_root, report, log_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.delitem(sys.modules, "provenance_tracker", raising=False)
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
    assert log_path.is_file()
    calls = [l for l in log_path.read_text().splitlines() if l == "check_readiness"]
    assert len(calls) == 1
    return out_dir, snapshot


def parse_index(out_dir):
    entries = sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*"))
    assert entries == ["index.html"]
    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    c = Collector()
    c.feed(html_text)
    c.close()
    return html_text, c


def test_single_self_contained_index_html(tmp_path, monkeypatch):
    report = make_report([], True)
    out_dir, snapshot = run_render(tmp_path, monkeypatch, report)
    html_text, c = parse_index(out_dir)

    assert len(c.snapshot_blocks) == 1
    parsed = json.loads(c.snapshot_blocks[0])
    assert parsed == to_plain(snapshot)

    node_ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert "comp-foo" in node_ids

    assert any(attrs.get("data-node-id") == "comp-foo" for _, attrs in c.tags)

    assert "fetch(" not in html_text
    assert "XMLHttpRequest" not in html_text
    assert "WebAssembly" not in html_text

    for tag, attrs in c.tags:
        for key in ("src", "href"):
            if key in attrs:
                assert not is_external(attrs[key]), (tag, key, attrs[key])
    # Also catch src=/href= that the parser might not attribute to a tag
    for m in re.finditer(r"""\b(?:src|href)\s*=\s*["']?([^"'\s>]*)""", html_text):
        assert not is_external(m.group(1)), m.group(0)


def test_script_close_in_reasons_does_not_break_snapshot(tmp_path, monkeypatch):
    reasons = ["comp-foo: weird </script><script>alert(1)</script> reason"]
    report = make_report(reasons, False)
    out_dir, snapshot = run_render(tmp_path, monkeypatch, report)
    html_text, c = parse_index(out_dir)

    assert len(c.snapshot_blocks) >= 1
    parsed = json.loads(c.snapshot_blocks[0])
    plain = to_plain(snapshot)
    assert parsed == plain
    assert parsed["not_ready_reasons"] == reasons