# hotdocs-criterion: sha256:7d8fa62ffd8db85c3457b7aad2f7373b37b2dd28e1a0196c26d480fc2bdd69a7
from pathlib import Path

import spec_scaffolder


def _tree(root):
    root = Path(root)
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def _library_md(kind, module):
    lines = [
        "# Library",
        "",
        "One module file, `kind_" + module + ".py`, never a package.",
        "",
        "```",
        'KIND: str           # "' + kind + '"',
        'GATE_VERSION: str   # "kind-' + kind + '@0.1.0"',
        "class AssetError(Exception)",
        "layout_errors(asset_file: Path) -> list[str]",
        "surface(asset_file: Path) -> dict",
        "provision(repo_root: Path) -> dict",
        "asset_runner(asset_file: Path) -> Callable[[str, list], object]",
        "strength_sites(asset_file: Path) -> list[dict]",
        "apply_site(asset_file: Path, site: dict) -> None",
        "guidance() -> dict",
        "```",
        "",
        "Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-"
        + kind
        + ".md`",
    ]
    return "".join(line + "\n" for line in lines)


def _requirement_md(kind, module, upper):
    rid = "R-KIND-" + upper + "-001"
    lines = [
        "# " + rid,
        "",
        "**" + rid + "** \u2014 TODO: `kind_" + module
        + "` MUST carry out `specs/architecture/asset-kind-" + kind
        + ".md`; replace this with one requirement per behaviour the definition states.",
    ]
    return "".join(line + "\n" for line in lines)


def _acceptance_md(upper):
    lines = [
        "# AC-KIND-" + upper + "-001",
        "",
        "Covers: R-KIND-" + upper + "-001",
        "Kind: generated-test",
        "",
        "```gherkin",
        "Given TODO: a correct asset with a suite that checks it, and the same asset with a weak suite",
        "When each site strength_sites lists is applied alone with apply_site and each suite is run",
        "Then the correct suite kills at least the bar's share of the sites and the weak suite fewer",
        "```",
    ]
    return "".join(line + "\n" for line in lines)


def test_new_kind_matches_new_component_plus_three_files(tmp_path):
    a = tmp_path / "A"
    b = tmp_path / "B"
    (a / "specs").mkdir(parents=True)
    (b / "specs").mkdir(parents=True)

    spec_scaffolder.new_kind(a, "yaml", title="YAML", realizes=["P-DATA"])
    spec_scaffolder.new_component(b, "kind-yaml", title="Kind YAML", realizes=["P-DATA"])

    a_dir = a / "specs" / "components" / "kind-yaml"
    b_dir = b / "specs" / "components" / "kind-yaml"
    assert a_dir.is_dir()
    assert b_dir.is_dir()

    a_files = _tree(a_dir)
    b_files = _tree(b_dir)

    for rel, data in b_files.items():
        assert rel in a_files, "missing in new_kind output: " + rel
        assert a_files[rel] == data, "bytes differ: " + rel

    extra = set(a_files) - set(b_files)
    assert extra == {
        "interface/library.md",
        "requirements/R-KIND-YAML-001.md",
        "acceptance/AC-KIND-YAML-001.md",
    }

    library = a_files["interface/library.md"].decode("utf-8")
    assert library == _library_md("yaml", "yaml")
    lib_lines = library.splitlines()
    assert "One module file, `kind_yaml.py`, never a package." in lib_lines
    assert 'GATE_VERSION: str   # "kind-yaml@0.1.0"' in lib_lines
    assert (
        "Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-yaml.md`"
        in lib_lines
    )

    requirement = a_files["requirements/R-KIND-YAML-001.md"].decode("utf-8")
    assert requirement == _requirement_md("yaml", "yaml", "YAML")

    acceptance = a_files["acceptance/AC-KIND-YAML-001.md"].decode("utf-8")
    assert acceptance == _acceptance_md("YAML")
    ac_lines = acceptance.splitlines()
    assert ac_lines[2] == "Covers: R-KIND-YAML-001"
    assert ac_lines[3] == "Kind: generated-test"


def test_new_kind_defaults(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)

    spec_scaffolder.new_kind(repo_root, "sql")

    comp_dir = repo_root / "specs" / "components" / "kind-sql"
    component_md = (comp_dir / "component.md").read_text(encoding="utf-8")
    lines = component_md.splitlines()
    assert "id: comp-kind-sql" in lines
    assert "title: Kind sql" in lines
    assert "owners: [unassigned]" in lines
    assert "realizes: []" in lines

    req_dir = comp_dir / "requirements"
    req_files = sorted(p.name for p in req_dir.iterdir() if p.is_file() and p.name != ".gitkeep")
    assert req_files == ["R-KIND-SQL-001.md"]
    req_text = (req_dir / "R-KIND-SQL-001.md").read_text(encoding="utf-8")
    assert req_text.splitlines()[0] == "# R-KIND-SQL-001"