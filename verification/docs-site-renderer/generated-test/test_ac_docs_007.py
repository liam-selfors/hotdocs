# hotdocs-criterion: sha256:a7892587ea91bd3e43e927312ba2c5f774001b9813be251d05c8235243671047
"""AC-DOCS-007: cli.main exit codes (0 after rendering, 1 on missing graph, 2 on usage error)."""

import importlib
import json
from pathlib import Path

import docs_site_renderer


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
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\nowners: [pipeline-team]\n---\n\n# Foo\n",
                    "requirements/R-FOO-001.md": "**R-FOO-001** - Foo MUST work.\n",
                },
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": False,
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


def _write_graph(repo_root: Path):
    verification = repo_root / "verification"
    verification.mkdir(parents=True, exist_ok=True)
    data = json.dumps(_valid_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    (verification / "corpus-graph.json").write_bytes(data.encode("utf-8"))


def test_valid_graph_renders_and_returns_0(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_graph(repo_root)
    out = tmp_path / "out"
    monkeypatch.chdir(tmp_path)

    rc = _cli().main(["--repo-root=" + str(repo_root), "--out=" + str(out)])

    assert rc == 0
    assert out.is_dir()
    files = [p for p in out.rglob("*") if p.is_file()]
    assert files, "expected rendered site files under --out"


def test_missing_graph_returns_1(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    rc = _cli().main(["--repo-root=" + str(repo_root)])

    assert rc == 1


def test_unknown_flag_returns_2(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_graph(repo_root)
    monkeypatch.chdir(repo_root)

    rc = _cli().main(["--bogus"])

    assert rc == 2


def test_flag_without_value_returns_2(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_graph(repo_root)
    monkeypatch.chdir(repo_root)

    rc = _cli().main(["--out"])

    assert rc == 2