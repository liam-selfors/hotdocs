import corpus_graph_builder

import importlib
import json
from pathlib import Path

import pytest


def _main():
    cli = importlib.import_module("corpus_graph_builder.cli")
    return cli.main


def _call(argv):
    main = _main()
    try:
        return main(argv)
    except SystemExit as exc:  # pragma: no cover - failure path
        pytest.fail(f"main({argv!r}) raised SystemExit({exc.code!r}) instead of returning")
    except BaseException as exc:  # pragma: no cover - failure path
        pytest.fail(f"main({argv!r}) raised {type(exc).__name__}: {exc}")


COMPONENT_MD = """---
id: comp-a
title: A
status: draft
owners: [team-a]
depends_on: []
realizes: []
uses_var: []
sealed: true
source_path: legacy/a/
---

# A

## Purpose

A tiny fixture component used to exercise the corpus graph builder CLI.
"""


def _make_corpus(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "a"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")


def _printed_paths(out: str):
    return [line.strip() for line in out.splitlines() if line.strip()]


def _assert_printed_path(out: str, expected: Path, base: Path) -> None:
    expected_resolved = expected.resolve()
    for line in _printed_paths(out):
        candidate = Path(line)
        if not candidate.is_absolute():
            candidate = base / candidate
        try:
            if candidate.resolve() == expected_resolved:
                return
        except OSError:
            continue
    pytest.fail(f"expected printed path {expected} in output, got: {out!r}")


def _assert_written(repo_root: Path) -> None:
    graph_path = repo_root / "verification" / "corpus-graph.json"
    assert graph_path.is_file(), "verification/corpus-graph.json was not written"
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "nodes" in data
    assert "comp-a" in data["nodes"]


def test_build_variants_return_0_write_and_print_path(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)
    graph_path = repo_root / "verification" / "corpus-graph.json"

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    # --repo-root=<dir>
    capsys.readouterr()
    rc = _call(["build", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert rc == 0
    _assert_written(repo_root)
    _assert_printed_path(out, graph_path, elsewhere)

    graph_path.unlink()

    # --repo-root <dir>
    rc = _call(["build", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    _assert_written(repo_root)
    _assert_printed_path(out, graph_path, elsewhere)

    graph_path.unlink()

    # default: current directory
    monkeypatch.chdir(repo_root)
    rc = _call(["build"])
    out = capsys.readouterr().out
    assert rc == 0
    _assert_written(repo_root)
    _assert_printed_path(out, graph_path, repo_root)


def test_invalid_provenance_json_returns_1(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)
    prov_dir = repo_root / "verification" / "a"
    prov_dir.mkdir(parents=True)
    (prov_dir / ".provenance.json").write_text("{not json", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    rc = _call(["build", f"--repo-root={repo_root}"])
    assert rc == 1


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["serve"],
        ["build", "--bogus"],
        ["build", "--repo-root"],
    ],
)
def test_usage_errors_return_2_without_raising(argv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = _call(list(argv))
    assert rc == 2