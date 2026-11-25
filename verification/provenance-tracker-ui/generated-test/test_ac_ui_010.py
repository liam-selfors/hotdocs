# hotdocs-criterion: sha256:9d673df43d3e4ebd0e168e15946dbe713ee9909bad5828b91c2b5e80c9029e97
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

import pytest

import provenance_tracker_ui


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _search_starts():
    starts = []
    for p in (
        Path(provenance_tracker_ui.__file__).resolve().parent,
        Path(__file__).resolve().parent,
        Path.cwd().resolve(),
    ):
        if p not in starts:
            starts.append(p)
    return starts


def _find_app_js():
    direct = Path(provenance_tracker_ui.__file__).resolve().parent / "static" / "app.js"
    if direct.is_file():
        return direct
    seen = set()
    for start in _search_starts():
        for p in [start] + list(start.parents):
            if p in seen:
                continue
            seen.add(p)
            for cand in (
                p / "gen" / "provenance-tracker-ui" / "static" / "app.js",
                p / "provenance-tracker-ui" / "static" / "app.js",
            ):
                if cand.is_file():
                    return cand
    here = Path(__file__).resolve().parent / "static" / "app.js"
    if here.is_file():
        return here
    return None


def _find_kind_javascript_path():
    seen = set()
    for start in _search_starts():
        for p in [start] + list(start.parents):
            if p in seen:
                continue
            seen.add(p)
            for base in (p / "kind-javascript", p / "gen" / "kind-javascript"):
                flat = base / "kind_javascript.py"
                if flat.is_file():
                    return flat
                pkg = base / "kind_javascript" / "__init__.py"
                if pkg.is_file():
                    return pkg
            flat = p / "kind_javascript.py"
            if flat.is_file():
                return flat
    return None


_DOC_STUB = (
    "globalThis.document = globalThis.document || {\n"
    "  querySelectorAll: () => [],\n"
    "  querySelector: () => null,\n"
    "  addEventListener: () => {},\n"
    "  readyState: 'complete',\n"
    "};\n"
    "globalThis.window = globalThis.window || { addEventListener: () => {} };\n"
)


def _node_runner(asset_text, with_stub=False):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available")

    def run(name, args):
        tmp = Path(tempfile.mkdtemp()).resolve()
        try:
            (tmp / "stub.mjs").write_text(_DOC_STUB if with_stub else "", encoding="utf-8")
            (tmp / "app.mjs").write_text(asset_text, encoding="utf-8")
            (tmp / "args.json").write_text(json.dumps(args), encoding="utf-8")
            runner = (
                "import './stub.mjs';\n"
                "import { readFileSync } from 'node:fs';\n"
                "const m = await import('./app.mjs');\n"
                "const args = JSON.parse(readFileSync(" + json.dumps(str(tmp / "args.json")) + ", 'utf8'));\n"
                "const r = await m[" + json.dumps(name) + "](...args);\n"
                "process.stdout.write(JSON.stringify(r === undefined ? null : r));\n"
            )
            (tmp / "runner.mjs").write_text(runner, encoding="utf-8")
            proc = subprocess.run(
                [node, str(tmp / "runner.mjs")],
                cwd=str(tmp),
                capture_output=True,
                text=True,
                timeout=30,
                env={"PATH": __import__("os").environ.get("PATH", "")},
            )
            assert proc.returncode == 0, proc.stderr
            return json.loads(proc.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    return run


NODES = [
    {"id": "a", "status": "passing"},
    {"id": "b", "status": "failing"},
    {"id": "c", "status": "missing"},
    {"id": "d", "status": "not-attempted"},
    {"id": "e", "status": "passing"},
]

TABLE = [
    ("all", {"a": False, "b": False, "c": False, "d": False, "e": False}),
    ("passing", {"a": False, "b": True, "c": True, "d": True, "e": False}),
    ("failing", {"a": True, "b": False, "c": True, "d": True, "e": True}),
    ("missing", {"a": True, "b": True, "c": False, "d": True, "e": True}),
    ("not-attempted", {"a": True, "b": True, "c": True, "d": False, "e": True}),
    ("Passing", {"a": True, "b": True, "c": True, "d": True, "e": True}),
    ("bogus", {"a": True, "b": True, "c": True, "d": True, "e": True}),
]


def _verification_report(component_id, overall):
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
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


def _hit(component_id, overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": {"blocked": False},
        "secret_scan": _secret_scan(),
    }


def _miss():
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-a": _hit("comp-a", "pass"),
            "comp-b": _hit("comp-b", "fail"),
            "comp-c": _miss(),
            "comp-d": _miss(),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-b: verification failed",
            "comp-c: no provenance for current spec state — run hotdocs generate comp-c",
            "comp-d: no provenance for current spec state — run hotdocs generate comp-d",
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    src = (
        "import copy\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + component_id)\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise RuntimeError('not used')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")

    graph = {
        "nodes": {
            cid: {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            }
            for cid in ["comp-a", "comp-b", "comp-c", "comp-d"]
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
        json.dumps(graph), encoding="utf-8"
    )

    attempts = repo_root / ".hotdocs" / "attempts" / "comp-c"
    attempts.mkdir(parents=True)
    record = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": "comp-c",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:0",
        "generation": {
            "component_id": "comp-c",
            "spec_bundle_hash": "sha256:0",
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"c.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification": _verification_report("comp-c", "fail"),
    }
    (attempts / "2026-10-25T14:32:01Z-a1b2c3.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    return repo_root, log_path


class _ScriptCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "script" and self.in_script:
            self.in_script = False
            self.scripts.append("".join(self._buf))

    def handle_data(self, data):
        if self.in_script:
            self._buf.append(data)


def _script_from_rendered_page():
    tmp = Path(tempfile.mkdtemp()).resolve()
    try:
        repo_root, _ = _build_repo(tmp)
        out_dir = tmp / "out"
        provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)
        html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    parser = _ScriptCollector()
    parser.feed(html_text)
    parser.close()
    for s in parser.scripts:
        if "hiddenByStatus" in s:
            if "export" not in s:
                s = s + "\nexport { hiddenByStatus };\n"
            return s
    return None


@pytest.fixture(scope="module")
def run():
    asset = _find_app_js()
    if asset is not None:
        path = _find_kind_javascript_path()
        if path is not None:
            kjs = load_module(path, "kind_javascript")
            return kjs.asset_runner(asset)
        return _node_runner(asset.read_text(encoding="utf-8"))
    script = _script_from_rendered_page()
    assert script is not None, "could not locate static/app.js or its inlined script"
    return _node_runner(script, with_stub=True)


@pytest.mark.parametrize("flt,expected", TABLE)
def test_hidden_by_status_table(run, flt, expected):
    result = run("hiddenByStatus", [NODES, flt])
    assert isinstance(result, dict)
    assert dict(result) == expected
    for v in result.values():
        assert v is True or v is False


def test_hidden_by_status_empty(run):
    assert dict(run("hiddenByStatus", [[], "all"])) == {}
    assert dict(run("hiddenByStatus", [[], "passing"])) == {}


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.filters = []
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "button" and "data-filter" in d:
            self.filters.append(d["data-filter"])
        classes = (d.get("class") or "").split()
        if "node" in classes or "data-node-id" in d:
            self.nodes.append((tag, d))

    handle_startendtag = handle_starttag


def test_rendered_filter_buttons(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    statuses = sorted(field(n, "status") for n in field(snapshot, "nodes"))
    assert statuses == sorted(["passing", "failing", "missing", "not-attempted"])

    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    parser = _Collector()
    parser.feed(html_text)
    parser.close()

    assert parser.filters == ["all", "passing", "failing", "missing", "not-attempted"]
    assert parser.nodes, "expected node elements in the rendered page"
    for tag, attrs in parser.nodes:
        assert "hidden" not in attrs, (tag, attrs)