# hotdocs-criterion: sha256:0e27161c19cbba4e0afe798b936b03766ab9238353502e6cfda247d9bf4dcd98
import spec_scaffolder


def _lines(text):
    return [line.rstrip() for line in text.splitlines()]


def _snapshot(root):
    result = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_file():
            result[rel] = p.read_bytes()
        else:
            result[rel] = None
    return result


def _write_decision(path, decision_id):
    text = (
        "---\n"
        + "id: " + decision_id + "\n"
        + "title: Earlier decision\n"
        + "status: draft\n"
        + "owners: [a]\n"
        + "---\n"
        + "\n"
        + "# Earlier decision\n"
        + "\n"
        + "Body.\n"
    )
    path.write_text(text)


def _assert_single_error_line(err):
    lines = [line for line in err.splitlines() if line.strip()]
    assert len(lines) == 1, err
    assert lines[0].startswith("error: "), err
    assert "Traceback" not in err


def test_decision_new_and_ratify_unknown(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)

    rc = spec_scaffolder.main(
        ["decision", "new", "First call", "--owners=a, b",
         "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.strip().splitlines() == ["specs/decisions/D1.md"]

    record = repo_root / "specs" / "decisions" / "D1.md"
    assert record.is_file()
    assert "owners: [a, b]" in _lines(record.read_text())

    rc = spec_scaffolder.main(
        ["decision", "ratify", "D9", "--repo-root", str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_single_error_line(err)


def test_usage_errors_return_2_and_write_nothing(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    (repo_root / "specs" / "components").mkdir(parents=True)
    monkeypatch.chdir(repo_root)

    cases = [
        ["decision", "new", "x", "--bogus"],
        ["decision", "new", "x", "--owners"],
        ["decision", "frobnicate"],
        ["component", "new"],
        ["kind", "new"],
        ["kind"],
    ]
    for argv in cases:
        before = _snapshot(repo_root)
        rc = spec_scaffolder.main(list(argv))
        out, err = capsys.readouterr()
        assert rc == 2, (argv, out, err)
        err_lines = err.splitlines()
        assert err_lines, argv
        assert err_lines[0].startswith("usage error: "), (argv, err)
        assert "Traceback" not in err, argv
        assert "Traceback" not in out, argv
        after = _snapshot(repo_root)
        assert after == before, argv


def test_component_new_sealed(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)

    rc = spec_scaffolder.main(
        ["component", "new", "my-thing", "--sealed",
         "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.strip().splitlines() == ["specs/components/my-thing/"]

    component_md = repo_root / "specs" / "components" / "my-thing" / "component.md"
    assert component_md.is_file()
    assert "sealed: true" in _lines(component_md.read_text())


def test_kind_new_and_refusals(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    _write_decision(decisions / "D4.md", "D4")

    rc = spec_scaffolder.main(
        ["kind", "new", "sql", "--title", "SQL", "--owners=a, b",
         "--realizes=P-DATA", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 0, err
    assert out.strip().splitlines() == [
        "specs/architecture/asset-kind-sql.md",
        "specs/components/kind-sql/",
        "specs/decisions/D5.md",
    ]

    definition = repo_root / "specs" / "architecture" / "asset-kind-sql.md"
    assert definition.is_file()
    def_lines = _lines(definition.read_text())
    assert "title: Asset kind SQL" in def_lines
    assert "owners: [a, b]" in def_lines

    component_md = repo_root / "specs" / "components" / "kind-sql" / "component.md"
    assert component_md.is_file()
    assert "realizes: [P-DATA]" in _lines(component_md.read_text())

    assert (decisions / "D5.md").is_file()

    rc = spec_scaffolder.main(
        ["kind", "new", "sql", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_single_error_line(err)
    assert not (decisions / "D6.md").exists()

    rc = spec_scaffolder.main(
        ["kind", "new", "python", "--repo-root=" + str(repo_root)]
    )
    out, err = capsys.readouterr()
    assert rc == 1
    _assert_single_error_line(err)
    assert not (decisions / "D6.md").exists()