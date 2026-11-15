"""AC-DOCS-004: given only corpus-graph.json as input, with no other files
available, render_docs_site runs, completes successfully, and reads nothing
else (R-DOCS-004: the site is a pure function of corpus-graph.json)."""

import docs_site_renderer

import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# File-access recorder (audit hook; only records while explicitly active)
# ---------------------------------------------------------------------------

class _AccessRecorder:
    def __init__(self):
        self.active = False
        self.events = []

    def hook(self, event, args):
        if not self.active:
            return
        try:
            if event == "open":
                path = args[0]
                if isinstance(path, (str, bytes, os.PathLike)):
                    self.events.append(("open", os.fsdecode(path)))
            elif event in ("os.listdir", "os.scandir"):
                path = args[0] if args else None
                if isinstance(path, (str, bytes, os.PathLike)):
                    self.events.append((event, os.fsdecode(path)))
        except Exception:
            pass


_RECORDER = _AccessRecorder()
sys.addaudithook(_RECORDER.hook)


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _graph_dict():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
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
            "comp-foo": {
                "type": "component",
                "verification": {
                    "requirement_results": {"R-FOO-001": "pass"},
                    "criteria": [
                        {"id": "AC-FOO-001", "kind": "generated-test", "result": "pass"}
                    ],
                },
                "provenance": {"generated_at": "2026-01-01T00:00:00Z", "model": "x"},
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\n---\n\n# Foo\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** - Foo MUST work.\n",
                },
            },
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


def _write_graph(repo_root: Path) -> Path:
    path = repo_root / "verification" / "corpus-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(_graph_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    path.write_bytes(data.encode("utf-8"))
    return path


def _all_files(root: Path):
    return sorted(p for p in root.rglob("*") if p.is_file())


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve(raw: str, cwd: Path) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = cwd / p
    return Path(os.path.realpath(str(p)))


def _assert_output_rendered(out_dir: Path):
    assert out_dir.is_dir(), "no output directory was rendered"
    files = _all_files(out_dir)
    assert files, "render produced no files"
    found = False
    for f in files:
        try:
            if "comp-foo" in f.read_text(encoding="utf-8", errors="replace"):
                found = True
                break
        except OSError:
            continue
    assert found, "rendered site does not mention the graph's nodes"


def _assert_only_graph_read(events, repo_root: Path, graph_path: Path, cwd: Path,
                            allow_graph_open: bool):
    repo_real = Path(os.path.realpath(str(repo_root)))
    cwd_real = Path(os.path.realpath(str(cwd)))
    graph_real = Path(os.path.realpath(str(graph_path)))
    offending = []
    for kind, raw in events:
        resolved = _resolve(raw, cwd)
        inside_repo = _is_under(resolved, repo_real)
        inside_cwd = _is_under(resolved, cwd_real)
        if not (inside_repo or inside_cwd):
            continue
        if kind == "open":
            if allow_graph_open and resolved == graph_real:
                continue
            offending.append((kind, raw))
        else:
            offending.append((kind, raw))
    assert not offending, f"renderer read something other than corpus-graph.json: {offending}"


# ---------------------------------------------------------------------------
# CLI path: corpus-graph.json is the only file present
# ---------------------------------------------------------------------------

def test_cli_renders_from_corpus_graph_json_alone(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    graph_path = _write_graph(repo_root)
    out_dir = tmp_path / "site-out"
    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.chdir(empty_cwd)

    # Precondition: corpus-graph.json is the only file available.
    assert _all_files(repo_root) == [graph_path]
    assert _all_files(empty_cwd) == []

    cli = importlib.import_module("docs_site_renderer.cli")

    _RECORDER.events = []
    _RECORDER.active = True
    try:
        rc = cli.main([f"--repo-root={repo_root}", f"--out={out_dir}"])
    finally:
        _RECORDER.active = False
    events = list(_RECORDER.events)

    assert rc == 0
    _assert_output_rendered(out_dir)
    _assert_only_graph_read(events, repo_root, graph_path, empty_cwd, allow_graph_open=True)

    # Nothing else appeared in, or was required from, the input tree.
    assert _all_files(repo_root) == [graph_path]
    assert _all_files(empty_cwd) == []


# ---------------------------------------------------------------------------
# Library path: render_docs_site(graph, out_dir) with the graph's data alone
# ---------------------------------------------------------------------------

def _tool_root():
    here = Path(os.path.realpath(docs_site_renderer.__file__))
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_corpus_graph_builder():
    root = _tool_root()
    if root is None:
        return None
    base = root / "gen" / "corpus-graph-builder"
    for candidate in (base / "corpus_graph_builder.py",
                      base / "corpus_graph_builder" / "__init__.py"):
        if candidate.is_file():
            name = "corpus_graph_builder"
            spec = importlib.util.spec_from_file_location(name, candidate)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
    return None


def test_library_render_reads_no_other_files(tmp_path, monkeypatch):
    cgb = _load_corpus_graph_builder()
    if cgb is None or not hasattr(cgb, "CorpusGraph"):
        pytest.skip("corpus-graph-builder's CorpusGraph not available from the tool root")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    graph_path = _write_graph(repo_root)
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    graph = cgb.CorpusGraph(nodes=data["nodes"], edges=data["edges"],
                            aggregates=data["aggregates"])
    assert _field(graph, "nodes") == data["nodes"]

    out_dir = tmp_path / "lib-out"
    empty_cwd = tmp_path / "empty-cwd"
    empty_cwd.mkdir()
    monkeypatch.chdir(empty_cwd)

    _RECORDER.events = []
    _RECORDER.active = True
    try:
        result = docs_site_renderer.render_docs_site(graph, out_dir)
    finally:
        _RECORDER.active = False
    events = list(_RECORDER.events)

    assert result is None
    _assert_output_rendered(out_dir)
    # Given the graph in memory, the renderer needs no file at all from the
    # input tree or the working directory.
    _assert_only_graph_read(events, repo_root, graph_path, empty_cwd, allow_graph_open=False)
    assert _all_files(empty_cwd) == []