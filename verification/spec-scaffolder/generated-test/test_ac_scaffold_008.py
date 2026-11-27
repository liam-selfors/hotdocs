# hotdocs-criterion: sha256:cd8636f8c6c06aa3a78704a9cca18f140872ca2830160c8ce4a96653d2d3bbcd
import os
from pathlib import Path

import spec_scaffolder


FENCE = "```"


def _files_under(directory):
    result = {}
    for dirpath, _dirnames, filenames in os.walk(str(directory)):
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(directory).as_posix()
            result[rel] = full.read_bytes()
    return result


def _expected_library(kind, module):
    lines = [
        "# Library",
        "",
        "One module file, `kind_" + module + ".py`, never a package.",
        "",
        FENCE,
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
        FENCE,
        "",
        "Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-"
        + kind
        + ".md`",
    ]
    return "\n".join(lines) + "\n"


def _expected_requirement(kind, module, upper):
    rid = "R-KIND-" + upper + "-001"
    lines = [
        "# " + rid,
        "",
        "**" + rid + "** — TODO: `kind_" + module + "` MUST carry out `specs/architecture/asset-kind-"
        + kind
        + ".md`; replace this with one requirement per behaviour the definition states.",
    ]
    return "\n".join(lines) + "\n"


def _expected_acceptance(upper):
    aid = "AC-KIND-" + upper + "-001"
    rid = "R-KIND-" + upper + "-001"
    lines = [
        "# " + aid,
        "",
        "Covers: " + rid,
        "Kind: generated-test",
        "",
        FENCE + "gherkin",
        "Given TODO: a correct asset with a suite that checks it, and the same asset with a weak suite",
        "When each site strength_sites lists is applied alone with apply_site and each suite is run",
        "Then the correct suite kills at least the bar's share of the sites and the weak suite fewer",
        FENCE,
    ]
    return "\n".join(lines) + "\n"


def test_new_kind_matches_new_component_plus_three_files(tmp_path):
    repo_a = tmp_path / "A"
    repo_b = tmp_path / "B"
    (repo_a / "specs").mkdir(parents=True)
    (repo_b / "specs").mkdir(parents=True)

    spec_scaffolder.new_kind(repo_a, "yaml", title="YAML", realizes=["P-DATA"])
    spec_scaffolder.new_component(
        repo_b, "kind-yaml", title="Kind YAML", realizes=["P-DATA"]
    )

    dir_a = repo_a / "specs" / "components" / "kind-yaml"
    dir_b = repo_b / "specs" / "components" / "kind-yaml"
    assert dir_a.is_dir()
    assert dir_b.is_dir()

    files_a = _files_under(dir_a)
    files_b = _files_under(dir_b)

    for rel, data in files_b.items():
        assert rel in files_a, "missing in new_kind output: " + rel
        assert files_a[rel] == data, "bytes differ for " + rel

    extra = set(files_a) - set(files_b)
    assert extra == {
        "interface/library.md",
        "requirements/R-KIND-YAML-001.md",
        "acceptance/AC-KIND-YAML-001.md",
    }

    library = files_a["interface/library.md"].decode("utf-8")
    requirement = files_a["requirements/R-KIND-YAML-001.md"].decode("utf-8")
    acceptance = files_a["acceptance/AC-KIND-YAML-001.md"].decode("utf-8")

    assert library == _expected_library("yaml", "yaml")
    assert requirement == _expected_requirement("yaml", "yaml", "YAML")
    assert acceptance == _expected_acceptance("YAML")

    lib_lines = library.splitlines()
    assert "One module file, `kind_yaml.py`, never a package." in lib_lines
    assert "GATE_VERSION: str   # \"kind-yaml@0.1.0\"" in lib_lines
    assert (
        "Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-yaml.md`"
        in lib_lines
    )

    ac_lines = acceptance.splitlines()
    assert ac_lines[2] == "Covers: R-KIND-YAML-001"
    assert ac_lines[3] == "Kind: generated-test"

    for content in (library, requirement, acceptance):
        assert content.endswith("\n")


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

    req = comp_dir / "requirements" / "R-KIND-SQL-001.md"
    assert req.is_file()
    assert req.read_text(encoding="utf-8").splitlines()[0] == "# R-KIND-SQL-001"