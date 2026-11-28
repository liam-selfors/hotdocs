# hotdocs-criterion: sha256:82d79b8badfd6dc02cde11129ac14e04a6b53c944a51e7ee5dec86c977cb976d
import importlib
from pathlib import Path

import pytest

import corpus_graph_builder


def _main():
    main = getattr(corpus_graph_builder, "main", None)
    if callable(main):
        return main
    cli = importlib.import_module("corpus_graph_builder.cli")
    return cli.main


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_corpus(repo_root):
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(
        comp_dir / "component.md",
        "---\n"
        + "id: comp-a\n"
        + "title: Component A\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "sealed: true\n"
        + "source_path: legacy/a/\n"
        + "---\n"
        + "\n"
        + "# Component A\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-A-001.md",
        "# R-A-001\n"
        + "\n"
        + "**R-A-001** - The component MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        + "\n"
        + "Covers: R-A-001\n"
        + "Kind: llm-judge\n"
        + "\n"
        + "The component does one thing.\n",
    )
    return repo_root


def _assert_success(rc, out, expected_path, cwd):
    assert rc == 0
    assert expected_path.is_file()
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    assert lines, "expected the written path on stdout"
    expected = expected_path.resolve()
    matched = False
    for line in lines:
        candidate = Path(line)
        if not candidate.is_absolute():
            candidate = Path(cwd) / candidate
        if candidate.resolve() == expected:
            matched = True
            break
    assert matched, "stdout did not name the written path: " + repr(out)


def test_build_success_forms(tmp_path, capsys, monkeypatch):
    repo_root = _make_corpus(tmp_path / "repo")
    main = _main()
    out_file = repo_root / "verification" / "corpus-graph.json"

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    # --repo-root=<dir>
    if out_file.exists():
        out_file.unlink()
    capsys.readouterr()
    rc = main(["build", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    _assert_success(rc, out, out_file, elsewhere)

    # --repo-root <dir>
    out_file.unlink()
    rc = main(["build", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    _assert_success(rc, out, out_file, elsewhere)

    # default: current directory
    out_file.unlink()
    monkeypatch.chdir(repo_root)
    rc = main(["build"])
    out = capsys.readouterr().out
    _assert_success(rc, out, out_file, repo_root)


def test_build_invalid_provenance_returns_1(tmp_path, capsys):
    repo_root = _make_corpus(tmp_path / "repo")
    _write(repo_root / "verification" / "a" / ".provenance.json", "{not json")
    main = _main()
    rc = main(["build", "--repo-root=" + str(repo_root)])
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
def test_usage_errors_return_2(argv, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main = _main()
    try:
        rc = main(list(argv))
    except BaseException as exc:  # noqa: BLE001
        pytest.fail("main(" + repr(argv) + ") raised " + repr(exc))
    assert rc == 2