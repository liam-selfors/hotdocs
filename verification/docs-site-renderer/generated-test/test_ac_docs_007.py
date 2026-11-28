# hotdocs-criterion: sha256:0a5d74c4fad93ffa66ca9080836b047a7165065af2da3281f7595e6364b859e1
"""AC-DOCS-007: cli.main exit codes and the missing-graph error line."""

import importlib
import json

import pytest

import docs_site_renderer


def _main():
    try:
        cli = importlib.import_module("docs_site_renderer.cli")
        return cli.main
    except ImportError:
        return docs_site_renderer.main


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


def test_valid_graph_renders_site_and_returns_0(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_text = json.dumps(_valid_graph(), sort_keys=True, indent=2) + "\n"
    (repo_root / "verification" / "corpus-graph.json").write_text(
        graph_text, encoding="utf-8"
    )
    out = tmp_path / "site"
    monkeypatch.chdir(tmp_path)

    code = _main()(["--repo-root=" + str(repo_root), "--out=" + str(out)])

    assert code == 0
    assert out.is_dir()
    index = out / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")
    assert "comp-foo" in html
    assert "comp-bar" in html


def test_missing_graph_returns_1_with_one_error_line(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    code = _main()(["--repo-root=" + str(repo_root)])

    assert code == 1
    err = capsys.readouterr().err
    lines = err.splitlines()
    assert len(lines) == 1, repr(err)
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
    monkeypatch.chdir(repo_root)

    code = _main()(list(argv))

    assert code == 2