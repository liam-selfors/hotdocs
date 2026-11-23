# hotdocs-criterion: sha256:d635ef14479ea23872c04f2f3d170cd551645bef2171aa2b6710fab7723e0534
import importlib
from pathlib import Path

import pytest

import corpus_graph_builder


def _main():
    try:
        cli = importlib.import_module("corpus_graph_builder.cli")
        fn = getattr(cli, "main", None)
        if fn is not None:
            return fn
    except ImportError:
        pass
    return getattr(corpus_graph_builder, "main")


COMPONENT_MD = (
    "---\n"
    "id: comp-a\n"
    "title: Component A\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
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
    "A small fixture component.\n"
)


def _make_corpus(root):
    comp_dir = root / "specs" / "components" / "a"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    return root


def _printed_path_matches(out, expected, bases):
    expected = expected.resolve()
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    for line in lines:
        p = Path(line)
        candidates = [p] if p.is_absolute() else [b / p for b in bases]
        for c in candidates:
            try:
                if c.resolve() == expected:
                    return True
            except OSError:
                continue
    return False


def test_build_variants_write_and_print(tmp_path, monkeypatch, capsys):
    main = _main()
    repo_root = _make_corpus(tmp_path / "repo")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    expected = repo_root / "verification" / "corpus-graph.json"

    runs = [
        (elsewhere, ["build", "--repo-root=" + str(repo_root)]),
        (elsewhere, ["build", "--repo-root", str(repo_root)]),
        (repo_root, ["build"]),
    ]
    for cwd, argv in runs:
        if expected.exists():
            expected.unlink()
        monkeypatch.chdir(cwd)
        capsys.readouterr()
        rc = main(argv)
        out = capsys.readouterr().out
        assert rc == 0, argv
        assert expected.is_file(), argv
        assert _printed_path_matches(out, expected, [Path.cwd(), repo_root]), (argv, out)


def test_invalid_provenance_json_returns_1(tmp_path, monkeypatch):
    main = _main()
    repo_root = _make_corpus(tmp_path / "repo")
    prov_dir = repo_root / "verification" / "a"
    prov_dir.mkdir(parents=True)
    (prov_dir / ".provenance.json").write_text("{not json", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
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
def test_usage_errors_return_2(tmp_path, monkeypatch, argv):
    main = _main()
    repo_root = _make_corpus(tmp_path / "repo")
    monkeypatch.chdir(repo_root)
    try:
        rc = main(list(argv))
    except BaseException as exc:  # noqa: BLE001
        pytest.fail("main raised " + repr(exc) + " for " + repr(argv))
    assert rc == 2