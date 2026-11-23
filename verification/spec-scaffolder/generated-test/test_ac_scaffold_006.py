# hotdocs-criterion: sha256:3bbba48343d45114f601e3fbd4f85649aa826dc183cc403c484d1e3f38d6f58f
import os
from pathlib import Path

import pytest

import spec_scaffolder


def _lines(path):
    return Path(path).read_text(encoding="utf-8").splitlines()


def _snapshot(root):
    root = Path(root)
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        snap[str(d.relative_to(root)) + "/"] = None
        for name in filenames:
            p = d / name
            snap[str(p.relative_to(root))] = p.read_bytes()
    return snap


def _decision_text(decision_id, title):
    return (
        "---\n"
        + "id: " + decision_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [a]\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "Body.\n"
    )


def _assert_one_error_line(err):
    lines = err.splitlines()
    assert len(lines) == 1, err
    assert lines[0].startswith("error: "), err


def test_decision_new_prints_path_and_writes_owners(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    capsys.readouterr()

    rc = spec_scaffolder.main(
        ["decision", "new", "First call", "--owners=a, b", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()

    assert rc == 0, err
    assert out.splitlines() == ["specs/decisions/D1.md"]
    d1 = repo_root / "specs" / "decisions" / "D1.md"
    assert d1.is_file()
    assert "owners: [a, b]" in _lines(d1)


def test_decision_ratify_unknown_returns_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    capsys.readouterr()

    rc = spec_scaffolder.main(
        ["decision", "ratify", "D9", "--repo-root", str(repo_root)]
    )
    out, err = capsys.readouterr()

    assert rc == 1
    _assert_one_error_line(err)


@pytest.mark.parametrize(
    "argv",
    [
        ["decision", "new", "x", "--bogus"],
        ["decision", "new", "x", "--owners"],
        ["decision", "frobnicate"],
        ["component", "new"],
        ["kind", "new"],
        ["kind"],
    ],
)
def test_usage_errors_return_2(tmp_path, capsys, monkeypatch, argv):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    monkeypatch.chdir(repo_root)
    before = _snapshot(repo_root)
    capsys.readouterr()

    rc = spec_scaffolder.main(list(argv))
    out, err = capsys.readouterr()

    assert rc == 2
    err_lines = err.splitlines()
    assert err_lines, "expected output on stderr"
    assert err_lines[0].startswith("usage error: "), err
    assert "Traceback" not in err
    assert "Traceback" not in out
    after = _snapshot(repo_root)
    assert after == before


def test_component_new_sealed(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    capsys.readouterr()

    rc = spec_scaffolder.main(
        ["component", "new", "my-thing", "--sealed", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()

    assert rc == 0, err
    assert out.splitlines() == ["specs/components/my-thing/"]
    component_md = repo_root / "specs" / "components" / "my-thing" / "component.md"
    assert component_md.is_file()
    assert "sealed: true" in _lines(component_md)


def _kind_repo(tmp_path):
    repo_root = tmp_path / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "D4.md").write_text(_decision_text("D4", "Fourth decision"), encoding="utf-8")
    return repo_root


def _run_kind_new_sql(repo_root):
    return spec_scaffolder.main(
        [
            "kind",
            "new",
            "sql",
            "--title",
            "SQL",
            "--owners=a, b",
            "--realizes=P-DATA",
            "--repo-root=" + str(repo_root),
        ]
    )


def test_kind_new_prints_three_paths(tmp_path, capsys):
    repo_root = _kind_repo(tmp_path)
    capsys.readouterr()

    rc = _run_kind_new_sql(repo_root)
    out, err = capsys.readouterr()

    assert rc == 0, err
    assert out.splitlines() == [
        "specs/architecture/asset-kind-sql.md",
        "specs/components/kind-sql/",
        "specs/decisions/D5.md",
    ]
    definition = repo_root / "specs" / "architecture" / "asset-kind-sql.md"
    assert definition.is_file()
    def_lines = _lines(definition)
    assert "title: Asset kind SQL" in def_lines
    assert "owners: [a, b]" in def_lines
    component_md = repo_root / "specs" / "components" / "kind-sql" / "component.md"
    assert component_md.is_file()
    assert "realizes: [P-DATA]" in _lines(component_md)
    assert (repo_root / "specs" / "decisions" / "D5.md").is_file()


def test_kind_new_refusals_return_1_and_write_no_decision(tmp_path, capsys):
    repo_root = _kind_repo(tmp_path)
    capsys.readouterr()
    rc = _run_kind_new_sql(repo_root)
    out, err = capsys.readouterr()
    assert rc == 0, err

    d6 = repo_root / "specs" / "decisions" / "D6.md"

    rc = spec_scaffolder.main(
        ["kind", "new", "sql", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_one_error_line(err)
    assert not d6.exists()

    rc = spec_scaffolder.main(
        ["kind", "new", "python", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_one_error_line(err)
    assert not d6.exists()