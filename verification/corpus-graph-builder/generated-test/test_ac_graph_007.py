import importlib
import json
import os
from pathlib import Path

import pytest

import corpus_graph_builder


def _cli():
    return importlib.import_module("corpus_graph_builder.cli")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "components" / "a" / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "---\n"
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A tiny fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "requirements" / "R-A-001.md",
        "**R-A-001** — Component A MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given component A\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# Capability X\n",
    )
    _write(
        repo_root / "specs" / "vars" / "y.md",
        "---\n"
        "id: VAR-Y\n"
        "title: Var Y\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# Var Y\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision one\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# D1\n",
    )
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **thing** — a thing.\n",
    )


def _printed_path_matches(out: str, expected: Path, cwd: str) -> bool:
    expected_resolved = expected.resolve()
    for line in out.splitlines():
        line = line.strip()
        if not line or "corpus-graph.json" not in line:
            continue
        candidate = Path(line)
        if not candidate.is_absolute():
            candidate = Path(cwd) / candidate
        try:
            if candidate.resolve() == expected_resolved:
                return True
        except OSError:
            continue
    return False


def _check_written(repo_root: Path) -> None:
    out_file = repo_root / "verification" / "corpus-graph.json"
    assert out_file.is_file(), "verification/corpus-graph.json was not written"
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "nodes" in data
    assert "comp-a" in data["nodes"]


def test_build_variants_succeed_and_print_path(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)
    other = tmp_path / "elsewhere"
    other.mkdir()
    out_file = repo_root / "verification" / "corpus-graph.json"
    main = _cli().main

    # 1: --repo-root=<dir>
    monkeypatch.chdir(other)
    capsys.readouterr()
    rc = main(["build", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert rc == 0
    _check_written(repo_root)
    assert _printed_path_matches(out, out_file, os.getcwd()), out
    assert not (other / "verification").exists()

    # 2: --repo-root <dir>
    out_file.unlink()
    rc = main(["build", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    _check_written(repo_root)
    assert _printed_path_matches(out, out_file, os.getcwd()), out
    assert not (other / "verification").exists()

    # 3: default repo root is the current directory
    out_file.unlink()
    monkeypatch.chdir(repo_root)
    rc = main(["build"])
    out = capsys.readouterr().out
    assert rc == 0
    _check_written(repo_root)
    assert _printed_path_matches(out, out_file, os.getcwd()), out


def test_invalid_provenance_json_returns_1(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)
    _write(repo_root / "verification" / "a" / ".provenance.json", "{not json")
    monkeypatch.chdir(tmp_path)
    main = _cli().main
    try:
        rc = main(["build", f"--repo-root={repo_root}"])
    except BaseException as exc:  # noqa: BLE001
        pytest.fail(f"main raised instead of returning 1: {exc!r}")
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
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    main = _cli().main
    try:
        rc = main(list(argv))
    except BaseException as exc:  # noqa: BLE001
        pytest.fail(f"main({argv!r}) raised instead of returning 2: {exc!r}")
    assert rc == 2