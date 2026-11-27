# hotdocs-criterion: sha256:999f0d9aec88f36ffa89685152667e15a9edb9192b5daaa57757e1b864cb3db6
import os
from pathlib import Path

import pytest

import spec_scaffolder


def _snapshot(root):
    entries = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        rel_dir = os.path.relpath(dirpath, str(root))
        entries.append(("dir", rel_dir, b""))
        for name in filenames:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                data = fh.read()
            entries.append(("file", os.path.join(rel_dir, name), data))
    return sorted(entries)


def _lines_starting(path, prefix):
    text = Path(path).read_text(encoding="utf-8")
    return [line.rstrip() for line in text.splitlines() if line.startswith(prefix)]


def _assert_error_one_line(err):
    lines = [line for line in err.splitlines() if line.strip() != ""]
    assert len(lines) == 1, err
    assert lines[0].startswith("error: "), err
    assert "Traceback" not in err


def _write_decision(repo_root, n):
    text = (
        "---\n"
        + "id: D" + str(n) + "\n"
        + "title: Decision " + str(n) + "\n"
        + "status: draft\n"
        + "owners: [a]\n"
        + "---\n"
        + "\n"
        + "# D" + str(n) + "\n"
        + "\n"
        + "Body.\n"
    )
    (repo_root / "specs" / "decisions" / ("D" + str(n) + ".md")).write_text(
        text, encoding="utf-8"
    )


def test_decision_new_and_ratify_unknown(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    rc = spec_scaffolder.main(
        ["decision", "new", "First call", "--owners=a, b",
         "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.splitlines() == ["specs/decisions/D1.md"]
    d1 = repo_root / "specs" / "decisions" / "D1.md"
    assert d1.is_file()
    assert _lines_starting(d1, "owners:") == ["owners: [a, b]"]

    rc = spec_scaffolder.main(
        ["decision", "ratify", "D9", "--repo-root", str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_error_one_line(err)


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
def test_usage_errors(tmp_path, capsys, monkeypatch, argv):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    monkeypatch.chdir(repo_root)
    before = _snapshot(tmp_path)

    rc = spec_scaffolder.main(list(argv))
    out, err = capsys.readouterr()

    assert rc == 2
    err_lines = err.splitlines()
    assert err_lines, "expected output on stderr"
    assert err_lines[0].startswith("usage error: "), err
    assert "Traceback" not in err
    assert "Traceback" not in out
    assert _snapshot(tmp_path) == before


def test_component_new_sealed(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    rc = spec_scaffolder.main(
        ["component", "new", "my-thing", "--sealed",
         "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.splitlines() == ["specs/components/my-thing/"]
    comp = repo_root / "specs" / "components" / "my-thing" / "component.md"
    assert comp.is_file()
    assert _lines_starting(comp, "sealed:") == ["sealed: true"]


def test_kind_new_and_refusals(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    _write_decision(repo_root, 4)
    monkeypatch.chdir(tmp_path)

    rc = spec_scaffolder.main(
        ["kind", "new", "sql", "--title", "SQL", "--owners=a, b",
         "--realizes=P-DATA", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.splitlines() == [
        "specs/architecture/asset-kind-sql.md",
        "specs/components/kind-sql/",
        "specs/decisions/D5.md",
    ]
    definition = repo_root / "specs" / "architecture" / "asset-kind-sql.md"
    assert definition.is_file()
    assert _lines_starting(definition, "title:") == ["title: Asset kind SQL"]
    assert _lines_starting(definition, "owners:") == ["owners: [a, b]"]
    comp = repo_root / "specs" / "components" / "kind-sql" / "component.md"
    assert comp.is_file()
    assert _lines_starting(comp, "realizes:") == ["realizes: [P-DATA]"]
    assert (repo_root / "specs" / "decisions" / "D5.md").is_file()

    d6 = repo_root / "specs" / "decisions" / "D6.md"

    rc = spec_scaffolder.main(
        ["kind", "new", "sql", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_error_one_line(err)
    assert not d6.exists()

    rc = spec_scaffolder.main(
        ["kind", "new", "python", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_error_one_line(err)
    assert not d6.exists()