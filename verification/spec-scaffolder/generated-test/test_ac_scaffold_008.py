# hotdocs-criterion: sha256:146399e5698d0bd7f86aa0b29f58e086f44835f8f853d638ad51726b54e97d0f
from pathlib import Path

import spec_scaffolder


def _files(root):
    root = Path(root)
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file()
    }


def _expected_library(kind, module):
    lines = [
        "# Library",
        "",
        "One module file, `kind_" + module + ".py`, never a package.",
        "",
        "```",
        "KIND: str           # \"" + kind + "\"",
        "GATE_VERSION: str   # \"kind-" + kind + "@0.1.0\"",
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


def _expected_requirement(kind, module, upper):
    rid = "R-KIND-" + upper + "-001"
    lines = [
        "# " + rid,
        "",
        "**" + rid + "** — TODO: `kind_" + module
        + "` MUST carry out `specs/architecture/asset-kind-" + kind
        + ".md`; replace this with one requirement per behaviour the definition states.",
    ]
    return "".join(line + "\n" for line in lines)


def _expected_acceptance(upper):
    aid = "AC-KIND-" + upper + "-001"
    rid = "R-KIND-" + upper + "-001"
    lines = [
        "# " + aid,
        "",
        "Covers: " + rid,
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
    spec_scaffolder.new_component(
        b, "kind-yaml", title="Kind YAML", realizes=["P-DATA"]
    )

    a_dir = a / "specs" / "components" / "kind-yaml"
    b_dir = b / "specs" / "components" / "kind-yaml"
    assert a_dir.is_dir()
    assert b_dir.is_dir()

    a_files = _files(a_dir)
    b_files = _files(b_dir)

    for rel, content in b_files.items():
        assert rel in a_files, rel
        assert a_files[rel] == content, rel

    extra = set(a_files) - set(b_files)
    assert extra == {
        "interface/library.md",
        "requirements/R-KIND-YAML-001.md",
        "acceptance/AC-KIND-YAML-001.md",
    }

    library = a_files["interface/library.md"]
    requirement = a_files["requirements/R-KIND-YAML-001.md"]
    acceptance = a_files["acceptance/AC-KIND-YAML-001.md"]

    assert library == _expected_library("yaml", "yaml").encode("utf-8")
    assert requirement == _expected_requirement("yaml", "yaml", "YAML").encode("utf-8")
    assert acceptance == _expected_acceptance("YAML").encode("utf-8")

    lib_lines = library.decode("utf-8").splitlines()
    assert "One module file, `kind_yaml.py`, never a package." in lib_lines
    assert "GATE_VERSION: str   # \"kind-yaml@0.1.0\"" in lib_lines
    assert (
        "Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-yaml.md`"
        in lib_lines
    )

    ac_lines = acceptance.decode("utf-8").splitlines()
    assert ac_lines[2] == "Covers: R-KIND-YAML-001"
    assert ac_lines[3] == "Kind: generated-test"


def test_new_kind_defaults(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)

    spec_scaffolder.new_kind(repo_root, "sql")

    comp_dir = repo_root / "specs" / "components" / "kind-sql"
    component_lines = (comp_dir / "component.md").read_text(encoding="utf-8").splitlines()
    assert "id: comp-kind-sql" in component_lines
    assert "title: Kind sql" in component_lines
    assert "owners: [unassigned]" in component_lines
    assert "realizes: []" in component_lines

    req = comp_dir / "requirements" / "R-KIND-SQL-001.md"
    assert req.is_file()
    first_line = req.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "# R-KIND-SQL-001"