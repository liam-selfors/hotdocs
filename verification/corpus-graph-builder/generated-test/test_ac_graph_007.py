import importlib
import json
from pathlib import Path

import pytest

import corpus_graph_builder


def _cli():
    return importlib.import_module("corpus_graph_builder.cli")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_corpus(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "---\n"
        "\n"
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A tiny fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-A-001.md",
        "**R-A-001** — The component MUST exist.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )


def _call(argv):
    main = _cli().main
    try:
        return main(argv)
    except BaseException as exc:  # includes SystemExit
        pytest.fail(f"main({argv!r}) raised {type(exc).__name__}: {exc!r}")


def _assert_printed_path(out: str, repo_root: Path, expected: Path) -> None:
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    assert lines, "expected the written path to be printed"
    assert any("corpus-graph.json" in ln for ln in lines), out
    matched = False
    for ln in lines:
        if "corpus-graph.json" not in ln:
            continue
        p = Path(ln)
        if not p.is_absolute():
            p = repo_root / p
        if p.resolve() == expected.resolve():
            matched = True
            break
    assert matched, f"printed output {out!r} does not name {expected}"


def _assert_written(expected: Path) -> None:
    assert expected.is_file(), f"{expected} was not written"
    data = json.loads(expected.read_text(encoding="utf-8"))
    nodes = data["nodes"]
    assert "comp-a" in nodes


def test_build_variants_return_0_write_and_print(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)
    expected = repo_root / "verification" / "corpus-graph.json"

    # --repo-root=<dir>
    capsys.readouterr()
    rc = _call(["build", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out
    assert rc == 0
    _assert_written(expected)
    _assert_printed_path(out, repo_root, expected)

    # --repo-root <dir>
    expected.unlink()
    rc = _call(["build", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    _assert_written(expected)
    _assert_printed_path(out, repo_root, expected)

    # default: current directory
    expected.unlink()
    monkeypatch.chdir(repo_root)
    rc = _call(["build"])
    out = capsys.readouterr().out
    assert rc == 0
    _assert_written(expected)
    _assert_printed_path(out, repo_root, expected)


def test_invalid_provenance_json_returns_1(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)
    _write(repo_root / "verification" / "a" / ".provenance.json", "{not json")

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
def test_usage_errors_return_2_without_raising(tmp_path, monkeypatch, argv):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)
    monkeypatch.chdir(repo_root)

    rc = _call(list(argv))
    assert rc == 2