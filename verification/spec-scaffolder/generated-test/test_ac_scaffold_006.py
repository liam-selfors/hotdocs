import os

import pytest

import spec_scaffolder


def _snapshot(root):
    entries = set()
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            entries.add(("d", os.path.relpath(os.path.join(dirpath, d), root)))
        for f in filenames:
            full = os.path.join(dirpath, f)
            with open(full, "rb") as fh:
                content = fh.read()
            entries.add(("f", os.path.relpath(full, root), content))
    return entries


def _lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [line.rstrip("\r\n") for line in fh.read().splitlines()]


def test_decision_new_prints_path_and_writes_owners(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)

    rc = spec_scaffolder.main(
        [
            "decision",
            "new",
            "First call",
            "--owners=a, b",
            "--repo-root=%s" % repo_root,
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0, captured.err
    assert captured.out.splitlines() == ["specs/decisions/D1.md"]

    record = repo_root / "specs" / "decisions" / "D1.md"
    assert record.is_file()
    owners_lines = [l for l in _lines(record) if l.startswith("owners:")]
    assert owners_lines == ["owners: [a, b]"]


def test_decision_ratify_unknown_returns_1_with_error_line(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)

    rc = spec_scaffolder.main(
        ["decision", "ratify", "D9", "--repo-root", str(repo_root)]
    )
    captured = capsys.readouterr()

    assert rc == 1
    err_lines = [l for l in captured.err.splitlines() if l.strip() != ""]
    assert len(err_lines) == 1, captured.err
    assert err_lines[0].startswith("error: ")
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    "argv",
    [
        ["decision", "new", "x", "--bogus"],
        ["decision", "new", "x", "--owners"],
        ["decision", "frobnicate"],
        ["component", "new"],
    ],
)
def test_usage_errors_return_2_and_write_nothing(tmp_path, capsys, monkeypatch, argv):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    (repo_root / "specs" / "components").mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    before = _snapshot(str(repo_root))
    rc = spec_scaffolder.main(list(argv))
    captured = capsys.readouterr()
    after = _snapshot(str(repo_root))

    assert rc == 2
    err_lines = captured.err.splitlines()
    assert err_lines, "expected stderr output"
    assert err_lines[0].startswith("usage error: "), captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert before == after


def test_component_new_sealed_prints_dir_and_writes_sealed(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)

    rc = spec_scaffolder.main(
        [
            "component",
            "new",
            "my-thing",
            "--sealed",
            "--repo-root=%s" % repo_root,
        ]
    )
    captured = capsys.readouterr()

    assert rc == 0, captured.err
    assert captured.out.splitlines() == ["specs/components/my-thing/"]

    component_md = repo_root / "specs" / "components" / "my-thing" / "component.md"
    assert component_md.is_file()
    sealed_lines = [l for l in _lines(component_md) if l.startswith("sealed:")]
    assert sealed_lines == ["sealed: true"]