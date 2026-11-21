# hotdocs-criterion: sha256:e132c260c7f256c5d1b65e9b7eafef7b734a5b24bb9fa1877e4c55b2f172ce66
from pathlib import Path

import pytest

import spec_scaffolder


SECTION_NAMES = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]


def expected_definition(kind, title, owners_text):
    lines = [
        "---",
        "id: arch-asset-kind-" + kind,
        "title: Asset kind " + title,
        "status: draft",
        "owners: [" + owners_text + "]",
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


D4_TEXT = (
    "---\n"
    "id: D4\n"
    "title: Earlier decision\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# D4: Earlier decision\n"
    "\n"
    "An earlier decision.\n"
)


def make_repo(root, with_d4=False):
    root = Path(root)
    (root / "specs").mkdir(parents=True)
    if with_d4:
        (root / "specs" / "decisions").mkdir()
        (root / "specs" / "decisions" / "D4.md").write_text(D4_TEXT)
    return root


def norm(p):
    return Path(p).resolve()


def snapshot(root):
    return sorted(str(p.relative_to(root)) for p in (root / "specs").rglob("*"))


def first_heading(text):
    for line in text.splitlines():
        if line.startswith("# "):
            return line
    return None


def section_lines(text):
    return [line for line in text.splitlines() if line.startswith("## ")]


def frontmatter_lines(text):
    lines = text.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    return lines[1:end]


def run_first_scenario(repo_root):
    return spec_scaffolder.new_kind(
        repo_root, "yaml", owners=["team-a"], realizes=["P-DATA"]
    )


def test_first_scenario_writes_three_parts(tmp_path):
    repo_root = make_repo(tmp_path / "repo", with_d4=True)
    result = run_first_scenario(repo_root)

    assert isinstance(result, list)
    assert len(result) == 3
    expected = [
        repo_root / "specs" / "architecture" / "asset-kind-yaml.md",
        repo_root / "specs" / "components" / "kind-yaml",
        repo_root / "specs" / "decisions" / "D5.md",
    ]
    assert [norm(p) for p in result] == [norm(p) for p in expected]
    for p in result:
        assert norm(repo_root) in norm(p).parents

    definition = expected[0].read_text()
    assert definition == expected_definition("yaml", "yaml", "team-a")
    assert first_heading(definition) == "# Asset kind `yaml`"
    assert section_lines(definition) == ["## " + name for name in SECTION_NAMES]

    assert expected[1].is_dir()

    d5_text = expected[2].read_text()
    fm = frontmatter_lines(d5_text)
    assert "id: D5" in fm
    assert "title: Asset kind yaml" in fm
    assert "owners: [team-a]" in fm
    assert not any(line.startswith("builds_on:") for line in fm)
    assert not any(line.startswith("supersedes:") for line in fm)
    assert not any(line.startswith("builds_on:") for line in d5_text.splitlines())
    assert not any(line.startswith("supersedes:") for line in d5_text.splitlines())

    # D5.md is exactly what new_decision writes for the same inputs.
    ref_root = make_repo(tmp_path / "ref", with_d4=True)
    ref_path = spec_scaffolder.new_decision(
        ref_root, "Asset kind yaml", owners=["team-a"]
    )
    assert norm(ref_path) == norm(ref_root / "specs" / "decisions" / "D5.md")
    assert d5_text == Path(ref_path).read_text()


def test_title_and_default_owners(tmp_path):
    repo_root = make_repo(tmp_path / "repo")
    result = spec_scaffolder.new_kind(repo_root, "sql", title="SQL")
    definition_path = repo_root / "specs" / "architecture" / "asset-kind-sql.md"
    assert norm(result[0]) == norm(definition_path)
    text = definition_path.read_text()
    lines = text.splitlines()
    assert "title: Asset kind SQL" in lines
    assert "owners: [unassigned]" in lines
    assert first_heading(text) == "# Asset kind `sql`"
    assert text == expected_definition("sql", "SQL", "unassigned")


def test_second_call_raises_and_writes_no_new_decision(tmp_path):
    repo_root = make_repo(tmp_path / "repo", with_d4=True)
    run_first_scenario(repo_root)
    before = snapshot(repo_root)
    with pytest.raises(FileExistsError):
        spec_scaffolder.new_kind(repo_root, "yaml")
    assert not (repo_root / "specs" / "decisions" / "D6.md").exists()
    assert snapshot(repo_root) == before


def test_existing_component_dir_raises_and_writes_nothing(tmp_path):
    repo_root = make_repo(tmp_path / "repo")
    (repo_root / "specs" / "components" / "kind-sql").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        spec_scaffolder.new_kind(repo_root, "sql")
    assert not (repo_root / "specs" / "architecture").exists()
    assert not (repo_root / "specs" / "decisions").exists()


@pytest.mark.parametrize("kind", ["python", "Data_Schema", "9x", "sql-", "a--b"])
def test_invalid_kind_raises_value_error(tmp_path, kind):
    repo_root = make_repo(tmp_path / "repo")
    before = snapshot(repo_root)
    with pytest.raises(ValueError):
        spec_scaffolder.new_kind(repo_root, kind)
    assert snapshot(repo_root) == before


def test_hyphenated_kind(tmp_path):
    repo_root = make_repo(tmp_path / "repo")
    result = spec_scaffolder.new_kind(repo_root, "data-schema")
    expected = [
        repo_root / "specs" / "architecture" / "asset-kind-data-schema.md",
        repo_root / "specs" / "components" / "kind-data-schema",
        repo_root / "specs" / "decisions" / "D1.md",
    ]
    assert [norm(p) for p in result] == [norm(p) for p in expected]
    library = (
        repo_root / "specs" / "components" / "kind-data-schema" / "interface" / "library.md"
    )
    assert library.is_file()
    assert "kind_data_schema.py" in library.read_text()