import docs_site_renderer

import importlib
import json
from pathlib import Path

import pytest


def _cli():
    return importlib.import_module("docs_site_renderer.cli")


def _valid_graph():
    return {
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
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\nowners: [pipeline-team]\n---\n\n# Foo\n\nFoo component.\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** - Foo MUST do foo.\n",
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
                "documents": {
                    "component.md": "---\nid: comp-bar\ntitle: Bar\nstatus: draft\nowners: [pipeline-team]\n---\n\n# Bar\n",
                },
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


def _all_files(root: Path):
    return [p for p in root.rglob("*") if p.is_file()]


def test_valid_graph_renders_site_and_returns_0(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph_path.write_text(
        json.dumps(_valid_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "site-out"
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    rc = _cli().main([f"--repo-root={repo_root}", f"--out={out}"])

    assert rc == 0
    assert out.is_dir()
    files = _all_files(out)
    assert files, "expected the rendered site to be written under --out"
    combined = ""
    for f in files:
        try:
            combined += f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    assert "comp-foo" in combined


def test_missing_corpus_graph_returns_1(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    assert not (repo_root / "verification" / "corpus-graph.json").exists()
    rc = _cli().main([f"--repo-root={repo_root}"])

    assert rc == 1


@pytest.mark.parametrize("argv", [["--bogus"], ["--out"]])
def test_usage_errors_return_2(tmp_path, monkeypatch, argv):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(_valid_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(repo_root)

    rc = _cli().main(list(argv))

    assert rc == 2