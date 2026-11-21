# hotdocs-criterion: sha256:10f1590d6001b4fb702cb428e192d75603a614532d4a2805a348096c9f409044
import corpus_graph_builder

import importlib
import os
from pathlib import Path


def _main():
    try:
        cli = importlib.import_module("corpus_graph_builder.cli")
        fn = getattr(cli, "main", None)
        if fn is not None:
            return fn
    except ImportError:
        pass
    return getattr(corpus_graph_builder, "main")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_corpus(repo_root):
    component_md = (
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
        + "A tiny fixture component.\n"
    )
    _write(repo_root / "specs" / "components" / "a" / "component.md", component_md)
    return repo_root


def _graph_path(repo_root):
    return repo_root / "verification" / "corpus-graph.json"


def _assert_printed_path(out, repo_root, cwd):
    expected = _graph_path(repo_root).resolve()
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    assert lines, "nothing printed to stdout"
    found = False
    for line in lines:
        candidate = Path(line)
        if not candidate.is_absolute():
            candidate = Path(cwd) / candidate
        try:
            if candidate.resolve() == expected:
                found = True
                break
        except OSError:
            continue
    assert found, "written path not printed; stdout was: " + repr(out)


def test_build_succeeds_with_each_repo_root_form(tmp_path, capsys, monkeypatch):
    main = _main()
    repo_root = _make_corpus(tmp_path / "repo")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)

    target = _graph_path(repo_root)

    capsys.readouterr()
    rc = main(["build", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert target.is_file()
    _assert_printed_path(out, repo_root, os.getcwd())

    target.unlink()

    rc = main(["build", "--repo-root", str(repo_root)])
    out = capsys.readouterr().out
    assert rc == 0
    assert target.is_file()
    _assert_printed_path(out, repo_root, os.getcwd())

    target.unlink()

    monkeypatch.chdir(repo_root)
    rc = main(["build"])
    out = capsys.readouterr().out
    assert rc == 0
    assert target.is_file()
    _assert_printed_path(out, repo_root, os.getcwd())


def test_build_returns_1_on_invalid_provenance_json(tmp_path, monkeypatch):
    main = _main()
    repo_root = _make_corpus(tmp_path / "repo")
    _write(repo_root / "verification" / "a" / ".provenance.json", "{not json")
    monkeypatch.chdir(tmp_path)

    rc = main(["build", "--repo-root=" + str(repo_root)])
    assert rc == 1


def test_usage_errors_return_2_without_raising(tmp_path, monkeypatch):
    main = _main()
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)

    for argv in ([], ["serve"], ["build", "--bogus"], ["build", "--repo-root"]):
        try:
            rc = main(argv)
        except BaseException as exc:
            raise AssertionError("main(" + repr(argv) + ") raised " + repr(exc))
        assert rc == 2, "main(" + repr(argv) + ") returned " + repr(rc)