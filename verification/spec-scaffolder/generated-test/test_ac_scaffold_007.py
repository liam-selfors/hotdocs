# hotdocs-criterion: sha256:fdcf99b73664435ed42f3b82042cdc740909d605b9cd036f9c3f8ff2c1ef6e2b
import spec_scaffolder

from pathlib import Path

import pytest


SECTION_ORDER = [
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


def write_d4(repo_root):
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "id: D4\n"
        "title: An earlier decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D4: An earlier decision\n"
        "\n"
        "Context.\n"
    )
    (decisions / "D4.md").write_text(text)


def norm(p):
    return Path(str(p)).resolve()


def all_files(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def first_heading(text):
    for line in text.splitlines():
        if line.startswith("# "):
            return line
    return None


def h2_lines(text):
    return [line[3:] for line in text.splitlines() if line.startswith("## ")]


def frontmatter_lines(text):
    lines = text.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    return lines[1:end]


def test_new_kind_writes_three_parts_in_order(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_d4(repo_root)

    result = spec_scaffolder.new_kind(
        repo_root, "yaml", owners=["team-a"], realizes=["P-DATA"]
    )
    result = list(result)

    expected = [
        repo_root / "specs" / "architecture" / "asset-kind-yaml.md",
        repo_root / "specs" / "components" / "kind-yaml",
        repo_root / "specs" / "decisions" / "D5.md",
    ]
    assert [norm(p) for p in result] == [norm(p) for p in expected]
    for p in result:
        assert str(norm(p)).startswith(str(norm(repo_root)))

    definition = expected[0].read_text()
    assert definition == expected_definition("yaml", "yaml", "team-a")
    assert first_heading(definition) == "# Asset kind `yaml`"
    assert h2_lines(definition) == SECTION_ORDER

    assert expected[1].is_dir()

    d5 = expected[2].read_text()
    fm = frontmatter_lines(d5)
    assert "id: D5" in fm
    assert "title: Asset kind yaml" in fm
    assert "owners: [team-a]" in fm
    assert not any(line.startswith("builds_on") for line in fm)
    assert not any(line.startswith("supersedes") for line in fm)

    # Exactly as new_decision writes it, in an equivalent repo.
    other_root = tmp_path / "other"
    other_root.mkdir()
    write_d4(other_root)
    ref_path = spec_scaffolder.new_decision(
        other_root, "Asset kind yaml", owners=["team-a"]
    )
    assert norm(ref_path) == norm(other_root / "specs" / "decisions" / "D5.md")
    assert d5 == Path(str(ref_path)).read_text()

    # Scenario 3: calling again raises and writes no D6.md.
    with pytest.raises(FileExistsError):
        spec_scaffolder.new_kind(repo_root, "yaml")
    assert not (repo_root / "specs" / "decisions" / "D6.md").exists()


def test_new_kind_title_and_default_owners(tmp_path):
    repo_root = tmp_path
    (repo_root / "specs").mkdir()

    result = list(spec_scaffolder.new_kind(repo_root, "sql", title="SQL"))
    definition_path = repo_root / "specs" / "architecture" / "asset-kind-sql.md"
    assert norm(result[0]) == norm(definition_path)

    definition = definition_path.read_text()
    lines = definition.splitlines()
    assert "title: Asset kind SQL" in lines
    assert "owners: [unassigned]" in lines
    assert first_heading(definition) == "# Asset kind `sql`"
    assert definition == expected_definition("sql", "SQL", "unassigned")


def test_new_kind_existing_component_dir_writes_nothing(tmp_path):
    repo_root = tmp_path
    (repo_root / "specs" / "components" / "kind-sql").mkdir(parents=True)

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_kind(repo_root, "sql")

    assert not (repo_root / "specs" / "architecture").exists()
    assert not (repo_root / "specs" / "decisions").exists()


@pytest.mark.parametrize("kind", ["python", "Data_Schema", "9x", "sql-", "a--b"])
def test_new_kind_invalid_kind_raises_value_error(tmp_path, kind):
    repo_root = tmp_path
    specs = repo_root / "specs"
    specs.mkdir()
    before = all_files(specs)

    with pytest.raises(ValueError):
        spec_scaffolder.new_kind(repo_root, kind)

    assert all_files(specs) == before


def test_new_kind_hyphenated_kind(tmp_path):
    repo_root = tmp_path
    (repo_root / "specs").mkdir()

    result = list(spec_scaffolder.new_kind(repo_root, "data-schema"))
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