import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "capability-scenario-verifier"))
import capability_scenario_verifier  # noqa: E402


def write_component(repo_root: Path, slug: str, realizes: list[str]) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    realizes_line = "[" + ", ".join(realizes) + "]"
    (comp_dir / "component.md").write_text(
        f"---\nid: comp-{slug}\ntitle: {slug.title()}\nstatus: draft\n"
        f"owners: [test-team]\nrealizes: {realizes_line}\nsealed: false\n---\n\n# {slug}\n",
        encoding="utf-8",
    )


def write_capability(repo_root: Path, p_id: str, scenario_blocks: str) -> None:
    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    slug = p_id[2:].lower().replace("_", "-")
    (product_dir / f"{slug}.md").write_text(
        f"---\nid: {p_id}\ntitle: {p_id}\nstatus: draft\nowners: [test-team]\n---\n\n"
        f"# {p_id}\n\n## Capability scenarios\n\n{scenario_blocks}\n",
        encoding="utf-8",
    )


def scenario_block(cs_id: str, covers: str, kind: str, gherkin: str) -> str:
    return f"### {cs_id}\nCovers: {covers}\nKind: {kind}\n\n```gherkin\n{gherkin}\n```\n\n"


@pytest.fixture
def repo_root(tmp_path):
    """run_capability_scenarios loads criterion-compiler/test-author
    dynamically from <repo_root>/gen/ per call -- real copies must exist
    under tmp_path for any kind: compiled / generated-test dispatch to
    reach past the first dependency load."""
    shutil.copytree(REPO_ROOT / "pipeline" / "criterion-compiler", tmp_path / "gen" / "criterion-compiler")
    shutil.copytree(REPO_ROOT / "gen" / "test-author", tmp_path / "gen" / "test-author")
    shutil.copytree(REPO_ROOT / "gen" / "cache-manager", tmp_path / "gen" / "cache-manager")
    shutil.copytree(REPO_ROOT / "gen" / "llm-endpoint", tmp_path / "gen" / "llm-endpoint")
    (tmp_path / "specs" / "glossary.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "specs" / "glossary.md").write_text("# Glossary\n", encoding="utf-8")
    return tmp_path
