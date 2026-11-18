# hotdocs-criterion: sha256:5f0fb7d44491d9d9be1a9d36d01c16912e902309998b197625865011bab462ac
"""AC-DOCS-004: given only corpus-graph.json, render_docs_site completes,
reading nothing else (R-DOCS-004: the site is a pure function of the graph)."""

import json
import os
import sys
from pathlib import Path

import docs_site_renderer
import docs_site_renderer.cli


_STATE = {"active": False, "repo_root": None, "opened": []}
_HOOK_INSTALLED = {"done": False}


def _normalize(raw):
    if isinstance(raw, int):
        return None
    try:
        raw = os.fspath(raw)
    except TypeError:
        return None
    if isinstance(raw, bytes):
        try:
            raw = os.fsdecode(raw)
        except Exception:
            return None
    if not isinstance(raw, str):
        return None
    if not os.path.isabs(raw):
        try:
            raw = os.path.join(os.getcwd(), raw)
        except Exception:
            return None
    try:
        return os.path.realpath(raw)
    except Exception:
        return os.path.abspath(raw)


def _hook(event, args):
    if not _STATE["active"]:
        return
    if event != "open" or not args:
        return
    # Avoid recursion while normalizing paths.
    _STATE["active"] = False
    try:
        path = _normalize(args[0])
        root = _STATE["repo_root"]
        if path is not None and root is not None:
            if path == root or path.startswith(root + os.sep):
                _STATE["opened"].append(path)
    finally:
        _STATE["active"] = True


def _install_hook():
    if not _HOOK_INSTALLED["done"]:
        sys.addaudithook(_hook)
        _HOOK_INSTALLED["done"] = True


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
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["docs-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\nowners: [docs-team]\n---\n\n# Foo\n\nFoo body text.\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** — Foo MUST work.\n",
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


def test_ac_docs_004_renders_from_corpus_graph_json_alone(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph_path.write_bytes(
        (json.dumps(_graph_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    )
    out_dir = tmp_path / "site"

    # The only file available under repo_root is corpus-graph.json.
    present = sorted(p for p in repo_root.rglob("*") if p.is_file())
    assert present == [graph_path]

    monkeypatch.chdir(repo_root)

    real_root = os.path.realpath(str(repo_root))
    real_graph = os.path.realpath(str(graph_path))
    real_gen = os.path.join(real_root, "gen")

    _install_hook()
    _STATE["repo_root"] = real_root
    _STATE["opened"] = []
    _STATE["active"] = True
    try:
        code = docs_site_renderer.cli.main(
            ["--repo-root=" + str(repo_root), "--out=" + str(out_dir)]
        )
    finally:
        _STATE["active"] = False
    opened = list(_STATE["opened"])

    assert code == 0

    # It read nothing under repo_root other than corpus-graph.json
    # (dependency module code under gen/ is code, not a data source).
    others = [
        p
        for p in opened
        if p != real_graph
        and not (p.startswith(real_gen + os.sep) and p.endswith(".py"))
    ]
    assert others == [], "read files other than corpus-graph.json: " + repr(others)
    assert real_graph in opened, "corpus-graph.json was never read"

    # The site was actually rendered, from the graph's content.
    assert out_dir.is_dir()
    files = [p for p in out_dir.rglob("*") if p.is_file()]
    assert files, "no site files rendered"
    combined = ""
    for p in files:
        try:
            combined += p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    assert "comp-foo" in combined

    # Still nothing else was created in the input repo.
    after = sorted(p for p in repo_root.rglob("*") if p.is_file())
    assert after == [graph_path]