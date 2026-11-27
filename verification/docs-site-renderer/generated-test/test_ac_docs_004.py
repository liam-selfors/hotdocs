# hotdocs-criterion: sha256:ee056ec5943e85310bf57d58f13ec8c11dbe8e0fcdcae96e1de469905933b9df
"""AC-DOCS-004: given only corpus-graph.json, render_docs_site completes and
reads no file except the component's own asset static/app.js (plus the
tool's own code and style, which are not data sources)."""

import json
import os
import sys
from pathlib import Path

import docs_site_renderer

_RECORDING = {"on": False, "events": []}


def _audit_hook(event, args):
    if not _RECORDING["on"]:
        return
    if event != "open":
        return
    try:
        path = args[0]
        if isinstance(path, int) or path is None:
            return
        path = os.fsdecode(path)
        _RECORDING["events"].append(os.path.abspath(path))
    except Exception:
        pass


sys.addaudithook(_audit_hook)


def _real(p):
    return os.path.realpath(str(p))


def _is_under(path, root):
    root = root.rstrip(os.sep)
    return path == root or path.startswith(root + os.sep)


def _corpus_graph():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-foo": {
                "type": "component",
                "verification": {
                    "requirement_results": {"R-FOO-001": "passing"},
                    "criteria": [
                        {"id": "AC-FOO-001", "kind": "compiled", "result": "passing"}
                    ],
                },
                "provenance": {"generated_at": "2026-01-01T00:00:00Z", "model": "m"},
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\n---\n\n# Foo\n",
                    "requirements/R-FOO-001.md": "# R-FOO-001\n\nFoo MUST work.\n",
                },
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": [],
                "documents": {},
            },
            "VAR-FOO-URL": {"type": "var"},
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


class _Graph(dict):
    """CorpusGraph-shaped value: attributes nodes/edges/aggregates, to_dict(),
    to_json_bytes(), and also readable as the plain dict it holds."""

    def __init__(self, data):
        super().__init__(data)
        self.nodes = data["nodes"]
        self.edges = data["edges"]
        self.aggregates = data["aggregates"]

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def test_ac_docs_004_reads_only_corpus_graph_and_own_asset(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_file = repo_root / "verification" / "corpus-graph.json"
    graph_file.write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    graph = _Graph(json.loads(graph_file.read_text(encoding="utf-8")))

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    gen = next(
        p for p in Path(docs_site_renderer.__file__).resolve().parents if p.name == "gen"
    )
    tool_root = _real(gen.parent)
    gen_real = _real(gen)
    own_dir = _real(gen / "docs-site-renderer")
    app_js_suffix = os.sep + "static" + os.sep + "app.js"
    ui_style_dir = _real(gen / "ui-style")
    tmp_real = _real(tmp_path)
    out_real = _real(out_dir)
    graph_real = _real(graph_file)

    _RECORDING["events"] = []
    _RECORDING["on"] = True
    try:
        docs_site_renderer.render_docs_site(graph, out_dir)
    finally:
        _RECORDING["on"] = False
    events = list(_RECORDING["events"])

    assert (out_dir / "index.html").is_file()

    violations = []
    for raw in events:
        path = _real(raw)
        if _is_under(path, out_real):
            continue
        if _is_under(path, tmp_real):
            if path == graph_real:
                continue
            violations.append(path)
            continue
        if _is_under(path, tool_root):
            if _is_under(path, own_dir) and path.endswith(app_js_suffix):
                continue
            if _is_under(path, ui_style_dir):
                continue
            if _is_under(path, gen_real) and (
                path.endswith(".py")
                or path.endswith(".pyc")
                or (os.sep + "__pycache__") in path
            ):
                continue
            violations.append(path)
            continue
        # Paths outside the tool and the test's temp dir belong to the Python
        # runtime itself (stdlib, site-packages), not data sources.

    assert violations == [], (
        "read files other than corpus-graph.json and static/app.js: " + repr(violations)
    )