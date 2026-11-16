"""AC-DOCS-004 (Covers: R-DOCS-004).

Given only corpus-graph.json as input, with no other files available,
when render_docs_site runs, then it completes successfully, reading
nothing else.
"""

import builtins
import dataclasses
import io
import json
import mimetypes
import os
import site
import sys
from pathlib import Path

import docs_site_renderer


DOC_MARKER = "zqxalphadocmarker"
REQ_MARKER = "zqxalpharequirementmarker"


# --------------------------------------------------------------------------
# A CorpusGraph matching comp-corpus-graph-builder's documented shape:
# a dataclass with `nodes`, `edges`, `aggregates`, `to_dict()` and
# `to_json_bytes()`.
# --------------------------------------------------------------------------
@dataclasses.dataclass
class CorpusGraph:
    nodes: dict
    edges: list
    aggregates: dict

    def to_dict(self):
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "aggregates": self.aggregates,
        }

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
            + "\n"
        ).encode("utf-8")


def _graph_dict():
    component_md = (
        "---\n"
        "id: comp-alpha\n"
        "title: Alpha\n"
        "status: draft\n"
        "owners: [docs-team]\n"
        "depends_on: [comp-beta]\n"
        "realizes: [P-ALPHA]\n"
        "uses_var: [VAR-ALPHA-URL]\n"
        "sealed: true\n"
        "source_path: legacy/alpha/\n"
        "---\n"
        "\n"
        "# Alpha\n"
        "\n"
        "The alpha component " + DOC_MARKER + " does things.\n"
    )
    req_md = (
        "# R-ALPHA-001\n"
        "\n"
        "**R-ALPHA-001** — Alpha MUST " + REQ_MARKER + ".\n"
    )
    beta_md = (
        "---\n"
        "id: comp-beta\n"
        "title: Beta\n"
        "status: draft\n"
        "owners: [docs-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/beta/\n"
        "---\n"
        "\n"
        "# Beta\n"
    )
    return {
        "nodes": {
            "P-ALPHA": {"type": "capability"},
            "VAR-ALPHA-URL": {"type": "var"},
            "comp-alpha": {
                "type": "component",
                "verification": None,
                "provenance": {
                    "component_id": "comp-alpha",
                    "generated_at": "2026-01-01T00:00:00Z",
                    "model": "anthropic:claude-sonnet-5",
                },
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["docs-team"],
                "documents": {
                    "component.md": component_md,
                    "requirements/R-ALPHA-001.md": req_md,
                },
            },
            "comp-beta": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": True,
                "pinned_overrides": [],
                "owners": [],
                "documents": {"component.md": beta_md},
            },
        },
        "edges": [
            {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
            {"from": "comp-alpha", "to": "VAR-ALPHA-URL", "kind": "uses_var"},
            {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


# --------------------------------------------------------------------------
# Read tracking
# --------------------------------------------------------------------------
def _real(p):
    return os.path.realpath(os.path.abspath(os.fsdecode(p)))


def _under(path, root):
    root = root.rstrip(os.sep) or os.sep
    return path == root or path.startswith(root + os.sep)


def _tool_gen_dir():
    here = Path(os.path.realpath(docs_site_renderer.__file__)).parent
    for parent in [here, *here.parents]:
        if parent.name == "gen":
            return str(parent)
    return None


def _allowed_roots(out_dir):
    roots = set()
    pkg_file = os.path.realpath(docs_site_renderer.__file__)
    roots.add(os.path.dirname(pkg_file))
    gen_dir = _tool_gen_dir()
    if gen_dir:
        roots.add(os.path.realpath(gen_dir))
    for p in (sys.prefix, sys.base_prefix, sys.exec_prefix):
        if p:
            roots.add(os.path.realpath(p))
    try:
        for p in site.getsitepackages():
            roots.add(os.path.realpath(p))
    except Exception:
        pass
    try:
        roots.add(os.path.realpath(site.getusersitepackages()))
    except Exception:
        pass
    roots.add(_real(out_dir))
    return roots


class _ReadRecorder:
    def __init__(self):
        self.reads = []

    def record(self, target):
        if isinstance(target, int):
            return
        try:
            self.reads.append(_real(target))
        except Exception:
            pass


def _install_tracking(monkeypatch, recorder):
    orig_open = builtins.open
    orig_io_open = io.open
    orig_os_open = os.open
    orig_scandir = os.scandir
    orig_listdir = os.listdir

    def _is_read_mode(mode):
        return "r" in mode or "+" in mode

    def make_open(orig):
        def tracked_open(file, mode="r", *args, **kwargs):
            if _is_read_mode(mode):
                recorder.record(file)
            return orig(file, mode, *args, **kwargs)

        return tracked_open

    def tracked_os_open(path, flags, *args, **kwargs):
        acc = flags & getattr(os, "O_ACCMODE", 3)
        if acc in (os.O_RDONLY, os.O_RDWR):
            recorder.record(path)
        return orig_os_open(path, flags, *args, **kwargs)

    def tracked_scandir(path="."):
        recorder.record(path)
        return orig_scandir(path)

    def tracked_listdir(path="."):
        recorder.record(path)
        return orig_listdir(path)

    monkeypatch.setattr(builtins, "open", make_open(orig_open))
    monkeypatch.setattr(io, "open", make_open(orig_io_open))
    monkeypatch.setattr(os, "open", tracked_os_open)
    monkeypatch.setattr(os, "scandir", tracked_scandir)
    monkeypatch.setattr(os, "listdir", tracked_listdir)


# --------------------------------------------------------------------------
# The test
# --------------------------------------------------------------------------
def test_ac_docs_004_renders_from_corpus_graph_json_alone(tmp_path, monkeypatch):
    # Given only corpus-graph.json as input, with no other files available.
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    graph_file = input_dir / "corpus-graph.json"
    seed = CorpusGraph(**_graph_dict())
    graph_file.write_bytes(seed.to_json_bytes())
    assert sorted(os.listdir(input_dir)) == ["corpus-graph.json"]

    loaded = json.loads(graph_file.read_text(encoding="utf-8"))
    graph = CorpusGraph(
        nodes=loaded["nodes"],
        edges=loaded["edges"],
        aggregates=loaded["aggregates"],
    )

    out_dir = tmp_path / "site"
    monkeypatch.chdir(input_dir)

    allowed = _allowed_roots(out_dir)
    allowed_files = {_real(graph_file)}
    for f in getattr(mimetypes, "knownfiles", []) or []:
        allowed_files.add(_real(f))

    recorder = _ReadRecorder()

    # When render_docs_site runs.
    with monkeypatch.context() as m:
        _install_tracking(m, recorder)
        result = docs_site_renderer.render_docs_site(graph, out_dir)

    # Then it completes successfully ...
    assert result is None
    assert out_dir.is_dir(), "render_docs_site produced no output directory"
    produced = [p for p in out_dir.rglob("*") if p.is_file()]
    assert produced, "render_docs_site wrote no files"
    assert any(p.suffix.lower() in (".html", ".htm") for p in produced), (
        "no HTML page was rendered"
    )

    # ... with the content drawn from the graph it was given ...
    combined = ""
    for p in produced:
        try:
            combined += p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    assert "comp-alpha" in combined
    assert DOC_MARKER in combined, (
        "component document text from the graph's `documents` was not rendered"
    )

    # ... reading nothing else.
    unexpected = sorted(
        {
            r
            for r in recorder.reads
            if r not in allowed_files
            and not any(_under(r, root) for root in allowed)
        }
    )
    assert unexpected == [], (
        "render_docs_site read from sources other than the given graph: "
        + repr(unexpected)
    )

    # The input directory still holds only corpus-graph.json.
    assert sorted(os.listdir(input_dir)) == ["corpus-graph.json"]