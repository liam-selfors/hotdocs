"""AC-ASSEMBLE-004: a SpecBundle's glossary equals the current specs/glossary.md exactly.

Covers R-ASSEMBLE-004.
"""

import os
import re
from pathlib import Path

import pytest

import spec_bundle_assembler


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _is_repo_root(candidate):
    return (candidate / "specs" / "glossary.md").is_file() and (
        candidate / "specs" / "components"
    ).is_dir()


def _find_repo_root():
    starts = []
    env_root = os.environ.get("HOTDOCS_REPO_ROOT")
    if env_root:
        starts.append(Path(env_root).resolve())
    starts.append(Path(__file__).resolve().parent)
    starts.append(Path.cwd().resolve())
    for start in starts:
        for candidate in [start, *start.parents]:
            if _is_repo_root(candidate):
                return candidate
    return None


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(\n|\Z)", re.DOTALL)


def _component_id(component_md):
    text = component_md.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "id":
            value = value.strip().strip("'\"")
            return value or None
    return None


def _all_component_ids(repo_root):
    ids = []
    for component_md in sorted((repo_root / "specs" / "components").glob("*/component.md")):
        component_id = _component_id(component_md)
        if component_id:
            ids.append(component_id)
    return ids


REPO_ROOT = _find_repo_root()
COMPONENT_IDS = _all_component_ids(REPO_ROOT) if REPO_ROOT is not None else []


def test_repo_root_and_components_found():
    assert REPO_ROOT is not None, "could not locate a repo root containing specs/glossary.md"
    assert COMPONENT_IDS, "no components found under specs/components/"
    assert "comp-spec-bundle-assembler" in COMPONENT_IDS


@pytest.mark.parametrize("component_id", COMPONENT_IDS)
def test_bundle_glossary_equals_current_glossary_file(component_id):
    expected = (REPO_ROOT / "specs" / "glossary.md").read_text(encoding="utf-8")

    bundle = spec_bundle_assembler.assemble(component_id, REPO_ROOT)

    glossary = _get(bundle, "glossary")
    assert isinstance(glossary, str), (
        f"{component_id}: SpecBundle.glossary is not a string: {type(glossary)!r}"
    )
    assert glossary == expected, (
        f"{component_id}: SpecBundle.glossary does not exactly equal specs/glossary.md"
    )