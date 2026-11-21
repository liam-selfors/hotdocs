# hotdocs-criterion: sha256:c06dd69eac80fcafad171d19326879ea8130ab3f2c968d731b51b349e56a9dee
import docs_site_renderer

import json
import os
import sys
from dataclasses import dataclass, field as dc_field
from pathlib import Path


@dataclass
class CorpusGraph:
    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


_STATE = {"active": False, "opens": []}


def _hook(event, args):
    if not _STATE["active"]:
        return
    if event == "open":
        _STATE["opens"].append(args)


sys.addaudithook(_hook)


def _graph_dict():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-foo": {
                "type": "component",
                "verification": {
                    "requirement_results": {"R-FOO-001": "pass"},
                    "criteria": [
                        {"id": "AC-FOO-001", "kind": "generated-test", "result": "pass"}
                    ],
                },
                "provenance": {"generated_at": "2026-01-01T00:00:00Z", "model": "m"},
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "# Foo\n\nThe foo component.\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** - foo MUST work.\n",
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
                "documents": {"component.md": "# Bar\n"},
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


def _is_write(mode, flags):
    if isinstance(mode, str) and any(c in mode for c in "wax+"):
        return True
    if isinstance(flags, int):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC):
            return True
    return False


def test_ac_docs_004_reads_only_its_own_asset(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_file = repo_root / "verification" / "corpus-graph.json"
    graph_file.write_text(json.dumps(_graph_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    monkeypatch.chdir(repo_root)

    data = json.loads(graph_file.read_text(encoding="utf-8"))
    graph = CorpusGraph(nodes=data["nodes"], edges=data["edges"], aggregates=data["aggregates"])

    out_dir = tmp_path / "out"
    asset = (Path(docs_site_renderer.__file__).resolve().parent.parent / "static" / "app.js")
    asset_real = os.path.realpath(str(asset))
    out_real = os.path.realpath(str(out_dir))

    _STATE["opens"] = []
    _STATE["active"] = True
    try:
        result = docs_site_renderer.render_docs_site(graph, out_dir)
    finally:
        _STATE["active"] = False

    assert result is None

    offending = []
    for args in _STATE["opens"]:
        path = args[0] if len(args) > 0 else None
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else None
        if path is None or isinstance(path, int):
            continue
        if isinstance(path, bytes):
            path = os.fsdecode(path)
        path = str(path)
        real = os.path.realpath(os.path.abspath(path))
        if real == out_real or real.startswith(out_real + os.sep):
            continue
        if _is_write(mode, flags):
            continue
        if real == asset_real:
            continue
        if real.endswith((".py", ".pyc", ".so", ".pyd")) or "__pycache__" in real:
            continue
        if os.path.isdir(real):
            continue
        offending.append(real)

    assert offending == [], "render_docs_site read files other than static/app.js: " + repr(offending)

    index = out_dir / "index.html"
    assert index.is_file()
    asset_text = asset.read_text(encoding="utf-8")
    assert asset_text in index.read_text(encoding="utf-8")