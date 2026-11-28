# hotdocs-criterion: sha256:b3a490325be0789c7f41696f0845d4c297015580e3bd1cd171fe3a5a6b8dffd6
"""AC-DOCS-004: given only corpus-graph.json, render_docs_site completes,
reading no data file except its own asset static/app.js (R-DOCS-004)."""

import dataclasses
import json
import os
import sys
import threading
from pathlib import Path

import docs_site_renderer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class CorpusGraph:
    """Stand-in with corpus-graph-builder's documented CorpusGraph shape."""

    nodes: dict
    edges: list
    aggregates: dict

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


GRAPH_DICT = {
    "nodes": {
        "P-ZERO-EDIT": {"type": "capability"},
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": "# Foo\n\nThe foo component.\n",
                "requirements/R-FOO-001.md": "# R-FOO-001\n\nFoo MUST foo.\n",
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
            "documents": {"component.md": "# Bar\n\nThe bar component.\n"},
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


_RECORDER = {"active": False, "thread": None, "reads": []}


def _audit(event, args):
    if event != "open" or not _RECORDER["active"]:
        return
    if threading.get_ident() != _RECORDER["thread"]:
        return
    path, mode, flags = (list(args) + [None, None, None])[:3]
    if path is None or isinstance(path, int):
        return
    try:
        path = os.fsdecode(path)
    except TypeError:
        return
    if isinstance(mode, str):
        if any(c in mode for c in "wax+"):
            return
    elif isinstance(flags, int):
        if (flags & os.O_ACCMODE) != os.O_RDONLY:
            return
    _RECORDER["reads"].append(os.path.realpath(path))


sys.addaudithook(_audit)


def _under(path, root):
    root = os.path.realpath(str(root))
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def test_ac_docs_004_renders_from_corpus_graph_alone(tmp_path, monkeypatch):
    # The only input: a corpus-graph.json in an otherwise empty directory.
    workdir = tmp_path / "work"
    workdir.mkdir()
    graph_file = workdir / "corpus-graph.json"
    graph_file.write_bytes(
        (json.dumps(GRAPH_DICT, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    )
    loaded = json.loads(graph_file.read_text(encoding="utf-8"))
    graph = CorpusGraph(loaded["nodes"], loaded["edges"], loaded["aggregates"])

    out_dir = tmp_path / "out"
    monkeypatch.chdir(workdir)

    pkg_dir = Path(docs_site_renderer.__file__).resolve().parent
    app_js = os.path.realpath(str(pkg_dir.parent / "static" / "app.js"))
    gen = next(p for p in pkg_dir.parents if p.name == "gen")
    ui_style_dir = gen / "ui-style"

    _RECORDER["reads"] = []
    _RECORDER["thread"] = threading.get_ident()
    _RECORDER["active"] = True
    try:
        result = docs_site_renderer.render_docs_site(graph, out_dir)
    finally:
        _RECORDER["active"] = False
    reads = list(_RECORDER["reads"])

    # It completes successfully.
    assert result is None
    index = out_dir / "index.html"
    assert index.is_file()

    # It read its own asset (inlined into index.html).
    assert app_js in reads
    asset_text = Path(app_js).read_text(encoding="utf-8")
    assert asset_text in index.read_text(encoding="utf-8")

    python_roots = {sys.prefix, sys.base_prefix, sys.exec_prefix}
    module_suffixes = (".py", ".pyc", ".pth", ".so", ".dylib", ".pyd")

    unexpected = []
    for path in reads:
        if path == app_js:
            continue
        if _under(path, out_dir):
            continue  # its own output
        if _under(path, ui_style_dir):
            continue  # the tool's own style, not a data source
        if path.endswith(module_suffixes):
            continue  # code being imported
        if any(_under(path, root) for root in python_roots):
            continue  # the interpreter's own files
        unexpected.append(path)

    assert unexpected == [], "read files other than its own asset: " + repr(unexpected)

    # In particular, nothing in the input directory was read, not even the
    # graph file again: the graph object is the only data source.
    assert [p for p in reads if _under(p, workdir)] == []