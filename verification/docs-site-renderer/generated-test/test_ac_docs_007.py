# hotdocs-criterion: sha256:efcc3b02ca833a536c95191e1f764400b4d58a71e735ca8f6eaeb99409363c58
import importlib
import json
from pathlib import Path

import docs_site_renderer


def _main():
    try:
        cli = importlib.import_module("docs_site_renderer.cli")
        fn = getattr(cli, "main", None)
        if fn is not None:
            return fn
    except ImportError:
        pass
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


def test_valid_graph_renders_and_returns_0(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_text = json.dumps(_valid_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    (repo_root / "verification" / "corpus-graph.json").write_text(graph_text, encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()

    rc = _main()(["--repo-root=" + str(repo_root), "--out=" + str(out)])

    assert rc == 0
    assert (out / "index.html").is_file()
    assert (out / "index.html").read_text(encoding="utf-8").strip() != ""


def test_missing_graph_returns_1_with_one_error_line(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out = tmp_path / "out"

    capsys.readouterr()
    rc = _main()(["--repo-root=" + str(repo_root), "--out=" + str(out)])
    captured = capsys.readouterr()

    assert rc == 1
    text = captured.err
    if text.endswith("\n"):
        text = text[:-1]
    lines = text.split("\n")
    assert len(lines) == 1, repr(captured.err)
    line = lines[0]
    assert line.startswith("error: ")
    assert line.endswith(
        "verification/corpus-graph.json is missing; run hotdocs corpus-graph build first"
    )


def test_missing_graph_default_out_returns_1(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    capsys.readouterr()
    rc = _main()(["--repo-root=" + str(repo_root)])
    captured = capsys.readouterr()

    assert rc == 1
    text = captured.err
    if text.endswith("\n"):
        text = text[:-1]
    lines = text.split("\n")
    assert len(lines) == 1, repr(captured.err)
    assert lines[0].startswith("error: ")
    assert lines[0].endswith(
        "verification/corpus-graph.json is missing; run hotdocs corpus-graph build first"
    )


def test_unknown_flag_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _main()(["--bogus"]) == 2


def test_flag_without_value_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _main()(["--out"]) == 2