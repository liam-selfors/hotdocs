"""AC-DOCS-007 (Covers: R-DOCS-007): cli.main exit codes for docs-site build."""

import importlib
import json
from pathlib import Path

import pytest

import docs_site_renderer

cli = importlib.import_module("docs_site_renderer.cli")


def _run(argv):
    """Run cli.main and return its exit code.

    The contract is `main(argv) -> int`; a SystemExit carrying the same
    code (e.g. from an argument parser) is read as that exit code.
    """
    try:
        return cli.main(argv)
    except SystemExit as exc:  # pragma: no cover - depends on implementation
        code = exc.code
        if code is None:
            return 0
        return code


def _valid_graph():
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
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-bar\ntitle: Bar\nstatus: draft\nowners: [pipeline-team]\n---\n# Bar\n",
                },
            },
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\nowners: [pipeline-team]\n---\n# Foo\n",
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


def _write_graph(repo_root: Path):
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    data = json.dumps(_valid_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    (vdir / "corpus-graph.json").write_bytes(data.encode("utf-8"))


def test_valid_graph_renders_site_and_returns_0(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_graph(repo_root)
    out = tmp_path / "site-out"
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    code = _run([f"--repo-root={repo_root}", f"--out={out}"])

    assert code == 0
    assert out.is_dir(), "out directory was not created"
    files = [p for p in out.rglob("*") if p.is_file()]
    assert files, "out holds no rendered files"
    html_files = [p for p in files if p.suffix.lower() in (".html", ".htm")]
    assert html_files, f"no HTML pages rendered in out: {files}"
    combined = "".join(
        p.read_text(encoding="utf-8", errors="replace") for p in html_files
    )
    assert "comp-foo" in combined
    assert "comp-bar" in combined


def test_missing_corpus_graph_returns_1(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / "verification" / "corpus-graph.json").exists()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    code = _run([f"--repo-root={repo_root}"])

    assert code == 1


@pytest.mark.parametrize("argv", [["--bogus"], ["--out"]])
def test_usage_errors_return_2(tmp_path, monkeypatch, argv):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_graph(repo_root)
    monkeypatch.chdir(repo_root)

    code = _run(list(argv))

    assert code == 2


@pytest.mark.parametrize("argv", [["--bogus"], ["--out"]])
def test_usage_errors_return_2_without_graph(tmp_path, monkeypatch, argv):
    repo_root = tmp_path / "empty"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    code = _run(list(argv))

    assert code == 2