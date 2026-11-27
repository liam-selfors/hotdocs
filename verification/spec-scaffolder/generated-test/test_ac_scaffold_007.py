# hotdocs-criterion: sha256:05ca76e11252376d375d76c2d7e7370dabedd7c4456e98438dd5128f36b3131f
from pathlib import Path

import pytest

import spec_scaffolder


D4_TEXT = (
    "---\n"
    "id: D4\n"
    "title: Earlier decision\n"
    "status: draft\n"
    "owners: [team-z]\n"
    "---\n"
    "\n"
    "# D4\n"
    "\n"
    "Some earlier decision.\n"
)


def expected_definition(kind, title, owners):
    lines = [
        "---",
        "id: arch-asset-kind-" + kind,
        "title: Asset kind " + title,
        "status: draft",
        "owners: [" + ", ".join(owners) + "]",
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


def make_repo(root, with_d4=False):
    root.mkdir(parents=True, exist_ok=True)
    (root / "specs").mkdir()
    if with_d4:
        (root / "specs" / "decisions").mkdir()
        (root / "specs" / "decisions" / "D4.md").write_text(D4_TEXT)
    return root


def snapshot(root):
    return sorted(
        (str(p.relative_to(root)), p.read_bytes() if p.is_file() else None)
        for p in (root / "specs").rglob("*")
    )


def norm(paths):
    return [Path(p).resolve() for p in paths]


def frontmatter_lines(text):
    lines = text.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    return lines[1:end]


def test_scenario_yaml_with_owners_and_rerun(tmp_path):
    repo = make_repo(tmp_path / "repo", with_d4=True)

    result = spec_scaffolder.new_kind(repo, "yaml", owners=["team-a"], realizes=["P-DATA"])
    result = list(result)
    assert norm(result) == norm([
        repo / "specs" / "architecture" / "asset-kind-yaml.md",
        repo / "specs" / "components" / "kind-yaml",
        repo / "specs" / "decisions" / "D5.md",
    ])
    for p in result:
        assert Path(p).resolve().is_relative_to(repo.resolve())

    definition = (repo / "specs" / "architecture" / "asset-kind-yaml.md").read_text()
    assert definition == expected_definition("yaml", "yaml", ["team-a"])

    headings = [l for l in definition.splitlines() if l.startswith("# ")]
    assert headings[0] == "# Asset kind `yaml`"
    sections = [l[3:] for l in definition.splitlines() if l.startswith("## ")]
    assert sections == [
        "Layout",
        "Environment",
        "Surface",
        "Running criteria",
        "Strength check",
        "Test author guidance",
        "Generator guidance",
    ]

    assert (repo / "specs" / "components" / "kind-yaml").is_dir()

    d5 = (repo / "specs" / "decisions" / "D5.md").read_text()
    fm = frontmatter_lines(d5)
    assert "id: D5" in fm
    assert "title: Asset kind yaml" in fm
    assert "owners: [team-a]" in fm
    assert not any(l.startswith("builds_on") for l in fm)
    assert not any(l.startswith("supersedes") for l in fm)

    ref = make_repo(tmp_path / "ref", with_d4=True)
    ref_path = spec_scaffolder.new_decision(ref, "Asset kind yaml", owners=["team-a"])
    assert Path(ref_path).name == "D5.md"
    assert d5 == Path(ref_path).read_text()

    before = snapshot(repo)
    with pytest.raises(FileExistsError):
        spec_scaffolder.new_kind(repo, "yaml")
    assert not (repo / "specs" / "decisions" / "D6.md").exists()
    assert snapshot(repo) == before


def test_scenario_sql_with_title_defaults_owners(tmp_path):
    repo = make_repo(tmp_path / "repo")
    spec_scaffolder.new_kind(repo, "sql", title="SQL")
    definition = (repo / "specs" / "architecture" / "asset-kind-sql.md").read_text()
    lines = definition.splitlines()
    assert "title: Asset kind SQL" in frontmatter_lines(definition)
    assert "owners: [unassigned]" in frontmatter_lines(definition)
    headings = [l for l in lines if l.startswith("# ")]
    assert headings[0] == "# Asset kind `sql`"
    assert definition == expected_definition("sql", "SQL", ["unassigned"])


def test_existing_component_dir_writes_nothing(tmp_path):
    repo = make_repo(tmp_path / "repo")
    (repo / "specs" / "components" / "kind-sql").mkdir(parents=True)
    before = snapshot(repo)
    with pytest.raises(FileExistsError):
        spec_scaffolder.new_kind(repo, "sql")
    assert not (repo / "specs" / "architecture").exists()
    assert not (repo / "specs" / "decisions").exists()
    assert snapshot(repo) == before


@pytest.mark.parametrize("bad", ["python", "Data_Schema", "9x", "sql-", "a--b"])
def test_invalid_kind_raises_value_error(tmp_path, bad):
    repo = make_repo(tmp_path / "repo")
    before = snapshot(repo)
    with pytest.raises(ValueError):
        spec_scaffolder.new_kind(repo, bad)
    assert snapshot(repo) == before
    assert list((repo / "specs").iterdir()) == []


def test_hyphenated_kind(tmp_path):
    repo = make_repo(tmp_path / "repo")
    result = list(spec_scaffolder.new_kind(repo, "data-schema"))
    assert norm(result) == norm([
        repo / "specs" / "architecture" / "asset-kind-data-schema.md",
        repo / "specs" / "components" / "kind-data-schema",
        repo / "specs" / "decisions" / "D1.md",
    ])
    library = repo / "specs" / "components" / "kind-data-schema" / "interface" / "library.md"
    assert library.is_file()
    assert "kind_data_schema.py" in library.read_text()