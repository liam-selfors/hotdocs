"""AC-GQE-001 (covers R-GQE-001).

Given a repo root with a real spec corpus
When load_views runs and nodes is queried
Then the row count per kind matches an independent file-system count
  for every one of the seven file-based kinds, never counting the
  README.md in specs/product/, specs/vars/ or specs/decisions/.
"""

import json
import os
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


SEVEN_KINDS = (
    "component",
    "capability",
    "var",
    "decision",
    "guarantee",
    "requirement",
    "acceptance",
)


def _looks_like_corpus_root(path: Path) -> bool:
    specs = path / "specs"
    return (
        (specs / "components").is_dir()
        and (specs / "product").is_dir()
        and (specs / "vars").is_dir()
        and (specs / "decisions").is_dir()
        and any((specs / "components").glob("*/component.md"))
    )


def _find_real_repo_root():
    candidates = []
    try:
        here = Path(__file__).resolve()
        candidates.extend([here.parent] + list(here.parents))
    except NameError:
        pass
    try:
        cwd = Path(os.getcwd()).resolve()
        candidates.extend([cwd] + list(cwd.parents))
    except OSError:
        pass
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if _looks_like_corpus_root(candidate):
            return candidate
    return None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fallback_corpus(root: Path) -> Path:
    """A small on-disk corpus, used only if no real corpus is reachable."""
    specs = root / "specs"

    components = {
        "alpha": {
            "requirements": ["R-ALPHA-001", "R-ALPHA-002"],
            "guarantees": ["G-ALPHA-001"],
        },
        "beta": {
            "requirements": ["R-BETA-001"],
            "guarantees": [],
        },
    }
    for slug, parts in components.items():
        comp_dir = specs / "components" / slug
        _write(
            comp_dir / "component.md",
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "depends_on: []\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}\n"
            "---\n\n"
            f"# {slug.capitalize()}\n\n"
            "## Purpose\n\n"
            f"{slug.capitalize()} does one small thing.\n",
        )
        _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
        _write(comp_dir / "interface" / "library.md", "# Library\n\nNothing.\n")
        for gid in parts["guarantees"]:
            _write(
                comp_dir / "interface" / "guarantees" / f"{gid}.md",
                f"# {gid}\n\nA guarantee.\n",
            )
        for idx, rid in enumerate(parts["requirements"], start=1):
            _write(
                comp_dir / "requirements" / f"{rid}.md",
                f"# {rid}\n\n**{rid}** — It MUST do a thing.\n",
            )
            ac_id = rid.replace("R-", "AC-", 1)
            _write(
                comp_dir / "acceptance" / f"{ac_id}.md",
                f"# {ac_id}\n\nCovers: {rid}\nKind: judged\n\n"
                "```gherkin\nGiven x\nWhen y\nThen z\n```\n",
            )
        _write(
            root / "gen" / slug / ".provenance.json",
            json.dumps(
                {
                    "component_id": f"comp-{slug}",
                    "spec_bundle_hash": "0" * 64,
                    "verification_report": {"passed": True},
                    "license_scan": {"passed": True},
                    "secret_scan": {"passed": True},
                    "provenance_hit": False,
                }
            ),
        )

    _write(
        specs / "product" / "P-ALPHA.md",
        "---\n"
        "id: P-ALPHA\n"
        "title: Alpha Capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n\n"
        "# Alpha Capability\n\n"
        "### CS-ALPHA-001\n\nCovers: P-ALPHA\n",
    )
    _write(specs / "product" / "README.md", "# Product\n\nIndex of capabilities.\n")

    _write(
        specs / "vars" / "VAR-ALPHA-PATH.md",
        "---\n"
        "id: VAR-ALPHA-PATH\n"
        "title: Alpha Path\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n\n"
        "# VAR-ALPHA-PATH\n",
    )
    _write(specs / "vars" / "README.md", "# Vars\n\nIndex of vars.\n")

    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First Decision\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "last_ratified_commit: abc1234\n"
        "supersedes: []\n"
        "builds_on: []\n"
        "---\n\n"
        "# D1\n",
    )
    _write(
        specs / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Second Decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "supersedes: [D1]\n"
        "builds_on: []\n"
        "---\n\n"
        "# D2\n",
    )
    _write(specs / "decisions" / "README.md", "# Decisions\n\nIndex of decisions.\n")

    _write(specs / "glossary.md", "# Glossary\n")
    return root


def _md_files_excluding_readme(directory: Path):
    if not directory.is_dir():
        return []
    return [
        p
        for p in directory.glob("*.md")
        if p.is_file() and p.name != "README.md"
    ]


def _independent_counts(repo_root: Path) -> dict:
    specs = repo_root / "specs"
    comp_root = specs / "components"
    return {
        "component": len([p for p in comp_root.glob("*/component.md") if p.is_file()]),
        "capability": len(_md_files_excluding_readme(specs / "product")),
        "var": len(_md_files_excluding_readme(specs / "vars")),
        "decision": len(_md_files_excluding_readme(specs / "decisions")),
        "guarantee": len(
            [p for p in comp_root.glob("*/interface/guarantees/*.md") if p.is_file()]
        ),
        "requirement": len(
            [p for p in comp_root.glob("*/requirements/*.md") if p.is_file()]
        ),
        "acceptance": len(
            [p for p in comp_root.glob("*/acceptance/*.md") if p.is_file()]
        ),
    }


@pytest.fixture
def repo_root(tmp_path):
    real = _find_real_repo_root()
    if real is not None:
        return real.resolve()
    return _build_fallback_corpus(tmp_path / "repo").resolve()


@pytest.fixture
def con():
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    try:
        yield connection
    finally:
        connection.close()


def test_nodes_row_count_per_kind_matches_filesystem(repo_root, con):
    expected = _independent_counts(repo_root)
    assert expected["component"] > 0, "corpus must contain at least one component"

    result = graph_query_engine.load_views(con, repo_root)
    assert result is None

    rows = con.execute(
        "SELECT kind, COUNT(*) FROM nodes GROUP BY kind"
    ).fetchall()
    actual = {kind: int(count) for kind, count in rows}

    mismatches = {}
    for kind in SEVEN_KINDS:
        got = actual.get(kind, 0)
        if got != expected[kind]:
            mismatches[kind] = {"expected": expected[kind], "actual": got}

    assert not mismatches, (
        "nodes row count per kind disagrees with independent file-system "
        f"count (README.md excluded): {mismatches}"
    )


def test_readme_files_never_become_nodes(repo_root, con):
    graph_query_engine.load_views(con, repo_root)

    for kind in ("capability", "var", "decision"):
        null_ids = con.execute(
            "SELECT COUNT(*) FROM nodes WHERE kind = ? AND id IS NULL", [kind]
        ).fetchone()[0]
        assert null_ids == 0, f"{kind} rows include {null_ids} NULL-id row(s) (README.md?)"

        readme_ids = con.execute(
            "SELECT COUNT(*) FROM nodes WHERE kind = ? AND lower(CAST(id AS VARCHAR)) LIKE '%readme%'",
            [kind],
        ).fetchone()[0]
        assert readme_ids == 0, f"{kind} rows include a README-derived id"