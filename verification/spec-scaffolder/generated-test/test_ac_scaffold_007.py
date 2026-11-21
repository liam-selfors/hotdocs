# hotdocs-criterion: sha256:1d2d3501e30a650e8c988f004e732a3f50e4ab21029cd166428a0cddc5dc533f
from pathlib import Path

import pytest

import spec_scaffolder


def _expected_definition(kind, title, owners):
    lines = [
        "---",
        "id: arch-asset-kind-" + kind,
        "title: Asset kind " + title,
        "status: draft",
        "owners: [" + owners + "]",
        "depends_on: []",
        "---",
        "",
        "# Asset kind `" + kind + "`",
        "",
        "TODO: say what the asset is and who consumes it; `comp-kind-" + kind + "` is its adapter.",
        "",
        "## Layout",
        "",
        "TODO: state what the file at the declared path must be, and the exact message `layout_errors` returns for each way it can be wrong.",
        "",
        "## Environment",
        "",
        "TODO: list each program the kind needs with its minimum version and the command that prints it, any lockfile under `environments/" + kind + "/`, and `provision`'s exact failure reasons.",
        "",
        "## Surface",
        "",
        "TODO: state what a consumer may rely on, extractable by code without judgement, and its notation in the asset's interface file.",
        "",
        "## Running criteria",
        "",
        "TODO: state what `asset_runner` takes and returns, with one example call and its JSON result.",
        "",
        "## Strength check",
        "",
        "TODO: write this section first: choose mutation, perturbation or evaluation, and list every site, so that each concrete wrong version of an asset is caught by at least one.",
        "",
        "## Test author guidance",
        "",
        "TODO: state exactly the text `guidance()[\"test_author\"]` returns: how a test builds fixtures and calls `asset_runner`, and what it must not do, never a requirement restated.",
        "",
        "## Generator guidance",
        "",
        "TODO: state exactly the text `guidance()[\"generator\"]` returns: the conventions the asset must follow, never test mechanics.",
    ]
    return "".join(line + "\n" for line in lines)


def _write_d4(repo_root):
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    (decisions / "D4.md").write_text(
        "---\n"
        "id: D4\n"
        "title: Earlier decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D4: Earlier decision\n"
        "\n"
        "Body.\n"
    )


def _snapshot(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def _same(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_new_kind_writes_three_parts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_d4(repo_root)

    result = spec_scaffolder.new_kind(
        repo_root, "yaml", owners=["team-a"], realizes=["P-DATA"]
    )
    result = list(result)
    assert len(result) == 3
    expected = [
        repo_root / "specs" / "architecture" / "asset-kind-yaml.md",
        repo_root / "specs" / "components" / "kind-yaml",
        repo_root / "specs" / "decisions" / "D5.md",
    ]
    for got, want in zip(result, expected):
        assert _same(got, want)
        assert Path(got).resolve().is_relative_to(repo_root.resolve())

    definition = expected[0]
    assert definition.is_file()
    text = definition.read_text()
    assert text == _expected_definition("yaml", "yaml", "team-a")

    lines = text.splitlines()
    headings = [l for l in lines if l.startswith("# ")]
    assert headings[0] == "# Asset kind `yaml`"
    sections = [l[3:] for l in lines if l.startswith("## ")]
    assert sections == [
        "Layout",
        "Environment",
        "Surface",
        "Running criteria",
        "Strength check",
        "Test author guidance",
        "Generator guidance",
    ]

    assert expected[1].is_dir()

    d5 = expected[2]
    assert d5.is_file()
    d5_text = d5.read_text()
    d5_lines = d5_text.splitlines()
    assert "id: D5" in d5_lines
    assert "title: Asset kind yaml" in d5_lines
    assert "owners: [team-a]" in d5_lines
    assert not any(l.startswith("builds_on:") for l in d5_lines)
    assert not any(l.startswith("supersedes:") for l in d5_lines)

    # Exactly as new_decision writes it, compared against a parallel repo.
    other = tmp_path / "other"
    other.mkdir()
    _write_d4(other)
    ref = spec_scaffolder.new_decision(other, "Asset kind yaml", owners=["team-a"])
    assert _same(ref, other / "specs" / "decisions" / "D5.md")
    assert d5_text == Path(ref).read_text()

    # Scenario 3: calling again raises and writes no D6.md.
    with pytest.raises(FileExistsError):
        spec_scaffolder.new_kind(repo_root, "yaml")
    assert not (repo_root / "specs" / "decisions" / "D6.md").exists()


def test_new_kind_title_and_default_owners(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)

    result = list(spec_scaffolder.new_kind(repo_root, "sql", title="SQL"))
    definition = repo_root / "specs" / "architecture" / "asset-kind-sql.md"
    assert _same(result[0], definition)
    lines = definition.read_text().splitlines()
    assert "title: Asset kind SQL" in lines
    assert "owners: [unassigned]" in lines
    headings = [l for l in lines if l.startswith("# ")]
    assert headings[0] == "# Asset kind `sql`"


def test_new_kind_existing_component_dir_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "components" / "kind-sql").mkdir(parents=True)

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_kind(repo_root, "sql")
    assert not (repo_root / "specs" / "architecture").exists()
    assert not (repo_root / "specs" / "decisions").exists()


@pytest.mark.parametrize(
    "kind", ["python", "Data_Schema", "9x", "sql-", "a--b", "data-schema"]
)
def test_new_kind_invalid_kind_raises(tmp_path, kind):
    repo_root = tmp_path / "repo"
    specs = repo_root / "specs"
    specs.mkdir(parents=True)
    before = _snapshot(specs)

    with pytest.raises(ValueError):
        spec_scaffolder.new_kind(repo_root, kind)
    assert _snapshot(specs) == before