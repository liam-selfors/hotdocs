# hotdocs-criterion: sha256:4fc92b399e7a14953155b1de9a6143365618537df6daa047c74b4a66a9085ffd
import os
from pathlib import Path

import pytest

import spec_scaffolder


def _lines(path):
    return [line.rstrip() for line in Path(path).read_text(encoding="utf-8").splitlines()]


def _snapshot(root):
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*"))


def _write_decision(root, n):
    text = (
        "---\n"
        + "id: D" + str(n) + "\n"
        + "title: Prior decision " + str(n) + "\n"
        + "status: draft\n"
        + "owners: [x]\n"
        + "---\n"
        + "\n"
        + "# D" + str(n) + "\n"
    )
    (root / "specs" / "decisions" / ("D" + str(n) + ".md")).write_text(text, encoding="utf-8")


def _assert_one_error_line(err):
    err_lines = [line for line in err.splitlines() if line.strip()]
    assert len(err_lines) == 1, err
    assert err_lines[0].startswith("error: "), err


def test_decision_new_and_ratify_unknown(tmp_path, capsys):
    root = tmp_path / "repo"
    (root / "specs" / "decisions").mkdir(parents=True)

    capsys.readouterr()
    rc = spec_scaffolder.main(
        ["decision", "new", "First call", "--owners=a, b", "--repo-root=" + str(root)]
    )
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.splitlines() == ["specs/decisions/D1.md"]
    d1 = root / "specs" / "decisions" / "D1.md"
    assert d1.is_file()
    assert "owners: [a, b]" in _lines(d1)

    capsys.readouterr()
    rc = spec_scaffolder.main(["decision", "ratify", "D9", "--repo-root", str(root)])
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
def test_usage_errors(argv, tmp_path, capsys, monkeypatch):
    root = tmp_path / "repo"
    (root / "specs" / "decisions").mkdir(parents=True)
    monkeypatch.chdir(root)
    before = _snapshot(root)

    capsys.readouterr()
    rc = spec_scaffolder.main(list(argv))
    out, err = capsys.readouterr()

    assert rc == 2
    err_lines = err.splitlines()
    assert err_lines, "no stderr output"
    assert err_lines[0].startswith("usage error: "), err
    assert "Traceback" not in err
    assert "Traceback" not in out
    assert _snapshot(root) == before


def test_component_new_sealed(tmp_path, capsys):
    root = tmp_path / "repo"
    (root / "specs").mkdir(parents=True)

    capsys.readouterr()
    rc = spec_scaffolder.main(
        ["component", "new", "my-thing", "--sealed", "--repo-root=" + str(root)]
    )
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.splitlines() == ["specs/components/my-thing/"]
    comp = root / "specs" / "components" / "my-thing" / "component.md"
    assert comp.is_file()
    assert "sealed: true" in _lines(comp)


def _kind_repo(tmp_path):
    root = tmp_path / "repo"
    (root / "specs" / "decisions").mkdir(parents=True)
    _write_decision(root, 4)
    return root


def _run_kind_sql(root):
    return spec_scaffolder.main(
        [
            "kind",
            "new",
            "sql",
            "--title",
            "SQL",
            "--owners=a, b",
            "--realizes=P-DATA",
            "--repo-root=" + str(root),
        ]
    )


def test_kind_new(tmp_path, capsys):
    root = _kind_repo(tmp_path)

    capsys.readouterr()
    rc = _run_kind_sql(root)
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.splitlines() == [
        "specs/architecture/asset-kind-sql.md",
        "specs/components/kind-sql/",
        "specs/decisions/D5.md",
    ]
    definition = root / "specs" / "architecture" / "asset-kind-sql.md"
    assert definition.is_file()
    def_lines = _lines(definition)
    assert "title: Asset kind SQL" in def_lines
    assert "owners: [a, b]" in def_lines
    comp = root / "specs" / "components" / "kind-sql" / "component.md"
    assert comp.is_file()
    assert "realizes: [P-DATA]" in _lines(comp)
    assert (root / "specs" / "decisions" / "D5.md").is_file()


def test_kind_new_refusals(tmp_path, capsys):
    root = _kind_repo(tmp_path)

    capsys.readouterr()
    rc = _run_kind_sql(root)
    out, err = capsys.readouterr()
    assert rc == 0, err

    d6 = root / "specs" / "decisions" / "D6.md"

    capsys.readouterr()
    rc = spec_scaffolder.main(["kind", "new", "sql", "--repo-root=" + str(root)])
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_one_error_line(err)
    assert not d6.exists()

    capsys.readouterr()
    rc = spec_scaffolder.main(["kind", "new", "python", "--repo-root=" + str(root)])
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_one_error_line(err)
    assert not d6.exists()