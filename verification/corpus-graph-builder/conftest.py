"""Shared fixture-corpus builder for corpus-graph-builder's test suite.

Unlike graph-query-engine's own suite (which deliberately tests against
this repo's real corpus), several of corpus-graph-builder's acceptance
criteria require a specific, controlled "Given" state — an orphan
capability, an unused var, a known provenance manifest — that this
repo's real corpus does not currently have (its own orphan rates are all
0.0, verified independently before this suite was written). A synthetic
fixture, mirroring spec-linter's own conftest.py pattern, is the only way
to actually exercise those branches.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "corpus-graph-builder"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "graph-query-engine"))
import corpus_graph_builder  # noqa: E402


def write_component(root: Path, name: str, depends_on=(), realizes=(), uses_var=(), sealed=False) -> None:
    comp_dir = root / "specs" / "components" / name
    comp_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        "---\n"
        f"id: comp-{name}\n"
        f"title: {name.title()}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        f"depends_on: [{', '.join(depends_on)}]\n"
        f"realizes: [{', '.join(realizes)}]\n"
        f"uses_var: [{', '.join(uses_var)}]\n"
        f"sealed: {'true' if sealed else 'false'}\n"
        "---\n\n"
        f"# {name.title()}\n\n## Purpose\n\nA minimal fixture component.\n"
    )
    (comp_dir / "component.md").write_text(frontmatter)


def write_product(root: Path, pid: str) -> None:
    (root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        f"id: {pid}\n"
        f"title: {pid.title()}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n\n"
        f"# {pid}\n\n## Purpose\n\nA minimal fixture capability.\n"
    )
    (root / "specs" / "product" / f"{pid.lower()}.md").write_text(text)


def write_var(root: Path, vid: str) -> None:
    (root / "specs" / "vars").mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        f"id: {vid}\n"
        f"title: {vid.title()}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n\n"
        f"# {vid}\n\n- **required:** no\n"
    )
    (root / "specs" / "vars" / f"{vid.lower()}.md").write_text(text)


def write_provenance(root: Path, component_name: str, **fields) -> None:
    out_dir = root / "verification" / component_name
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": "sha256:deadbeef",
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": {},
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-1",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
    manifest.update(fields)
    (out_dir / ".provenance.json").write_text(json.dumps(manifest))


def write_baseline(root: Path) -> None:
    """comp-foo realizes P-ONE and uses VAR-ONE — nothing orphaned."""
    write_component(root, "foo", realizes=["P-ONE"], uses_var=["VAR-ONE"])
    write_product(root, "P-ONE")
    write_var(root, "VAR-ONE")


@pytest.fixture
def corpus_root(tmp_path):
    write_baseline(tmp_path)
    return tmp_path


def build(root: Path):
    return corpus_graph_builder.build_corpus_graph(root)
