# hotdocs-criterion: sha256:ca8f2561ca04eab4b2cea1ad425f0f7a322c1d380f4059f2be79ff6e21dcbb4c
import importlib
import json
from pathlib import Path

import pytest

import docs_site_renderer


def _main():
    main = getattr(docs_site_renderer, "main", None)
    if callable(main):
        return main
    if hasattr(docs_site_renderer, "__path__"):
        cli = importlib.import_module("docs_site_renderer.cli")
        return cli.main
    cli = getattr(docs_site_renderer, "cli", None)
    if cli is not None and callable(getattr(cli, "main", None)):
        return cli.main
    raise AssertionError("docs_site_renderer exposes no main")


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
                    "component.md": "# Foo\n\nThe foo component.\n",
                    "requirements/R-FOO-001.md": "# R-FOO-001\n\nFoo MUST work.\n",
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


def test_valid_graph_renders_site_and_returns_0(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_graph(repo_root)
    out = tmp_path / "out"
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)

    code = _main()(["--repo-root=" + str(repo_root), "--out=" + str(out)])

    assert code == 0
    assert out.is_dir()
    index = out / "index.html"
    assert index.is_file()
    assert index.read_text(encoding="utf-8").strip() != ""


def test_missing_graph_returns_1_with_one_error_line(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    capsys.readouterr()

    code = _main()(["--repo-root=" + str(repo_root)])

    captured = capsys.readouterr()
    assert code == 1
    err = captured.err
    if err.endswith("\n"):
        err = err[:-1]
    lines = err.split("\n")
    assert len(lines) == 1, captured.err
    line = lines[0]
    assert line.startswith("error: ")
    assert line.endswith(
        "verification/corpus-graph.json is missing; run hotdocs corpus-graph build first"
    )
    assert "  " not in line


@pytest.mark.parametrize("argv", [["--bogus"], ["--out"]])
def test_usage_errors_return_2(tmp_path, monkeypatch, argv):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_graph(repo_root)
    monkeypatch.chdir(repo_root)

    code = _main()(list(argv))

    assert code == 2