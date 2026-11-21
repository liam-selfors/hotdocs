# hotdocs-criterion: sha256:484ee667e541281b2830e5c7f493d187b5d1b661433e79252f9ca89360fd2179
import importlib
import json
from pathlib import Path

import docs_site_renderer


def _cli_main():
    try:
        cli = importlib.import_module("docs_site_renderer.cli")
        return cli.main
    except Exception:
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
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {
                    "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\nowners: [pipeline-team]\n---\n\n# Foo\n",
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


def test_valid_graph_renders_site_and_returns_0(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_bytes = json.dumps(_valid_graph(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    (repo_root / "verification" / "corpus-graph.json").write_text(graph_bytes, encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.chdir(tmp_path)

    main = _cli_main()
    code = main(["--repo-root=" + str(repo_root), "--out=" + str(out)])

    assert code == 0
    assert out.is_dir()
    index = out / "index.html"
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    assert text.strip() != ""
    assert "comp-foo" in text


def test_missing_corpus_graph_returns_1(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    main = _cli_main()
    code = main(["--repo-root=" + str(repo_root)])

    assert code == 1


def test_unknown_flag_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main = _cli_main()
    assert main(["--bogus"]) == 2


def test_flag_without_value_returns_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main = _cli_main()
    assert main(["--out"]) == 2