# hotdocs-criterion: sha256:8347115dcfde74f7d804ea63c242ce11674e7c75d93669b7cb5610ca80d0b34c
import importlib
import json
from pathlib import Path

import corpus_graph_builder

cli = importlib.import_module("corpus_graph_builder.cli")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_corpus(repo_root):
    comp_dir = repo_root / "specs" / "components" / "a"
    write(
        comp_dir / "component.md",
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
        "\n"
        "# comp-a\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component.\n",
    )
    write(
        comp_dir / "requirements" / "R-A-001.md",
        "**R-A-001** - comp-a MUST exist.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n\nCovers: R-A-001\nKind: generated-test\n",
    )
    return repo_root


def printed_path_matches(out, repo_root, expected):
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    assert lines, "nothing was printed"
    for line in lines:
        p = Path(line)
        if not p.is_absolute():
            p = repo_root / p
        try:
            if p.resolve() == expected.resolve():
                return True
        except OSError:
            continue
    return False


def check_written(repo_root, out):
    expected = repo_root / "verification" / "corpus-graph.json"
    assert expected.is_file()
    data = json.loads(expected.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert printed_path_matches(out, repo_root, expected), out


def test_build_variants_return_zero_write_and_print(tmp_path, capsys, monkeypatch):
    repo_root = make_corpus(tmp_path / "repo")
    target = repo_root / "verification" / "corpus-graph.json"

    capsys.readouterr()
    rc = cli.main(["build", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    check_written(repo_root, out)

    target.unlink()
    rc = cli.main(["build", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    check_written(repo_root, out)

    target.unlink()
    monkeypatch.chdir(repo_root)
    rc = cli.main(["build"])
    out = capsys.readouterr().out
    assert rc == 0
    check_written(repo_root, out)


def test_invalid_provenance_json_returns_one(tmp_path):
    repo_root = make_corpus(tmp_path / "repo")
    write(repo_root / "verification" / "a" / ".provenance.json", "{not json")
    rc = cli.main(["build", "--repo-root=" + str(repo_root)])
    assert rc == 1


def test_usage_errors_return_two_without_raising(tmp_path, monkeypatch):
    repo_root = make_corpus(tmp_path / "repo")
    monkeypatch.chdir(repo_root)
    for argv in ([], ["serve"], ["build", "--bogus"], ["build", "--repo-root"]):
        try:
            rc = cli.main(argv)
        except BaseException as exc:  # SystemExit included
            raise AssertionError(
                "main(" + repr(argv) + ") raised " + repr(exc)
            )
        assert rc == 2, "main(" + repr(argv) + ") returned " + repr(rc)