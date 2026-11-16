"""AC-GQE-001 (Covers: R-GQE-001).

Given a repo root with a real spec corpus
When load_views runs and nodes is queried
Then the row count per kind matches an independent file-system count
  for every kind, never counting the README.md in specs/product/,
  specs/vars/ or specs/decisions/.
"""

import glob
import os
import re
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


KINDS = (
    "component",
    "capability",
    "var",
    "decision",
    "guarantee",
    "requirement",
    "acceptance",
    "capability_scenario",
)

CS_HEADING = re.compile(r"### (CS-[A-Za-z0-9-]+)")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _connect():
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    return con


def _md_files(pattern):
    return sorted(p for p in glob.glob(pattern) if os.path.isfile(p))


def _non_readme(paths):
    return [p for p in paths if os.path.basename(p) != "README.md"]


def _independent_counts(repo_root: Path):
    root = str(repo_root)
    components = _md_files(os.path.join(root, "specs", "components", "*", "component.md"))
    product = _non_readme(_md_files(os.path.join(root, "specs", "product", "*.md")))
    vars_ = _non_readme(_md_files(os.path.join(root, "specs", "vars", "*.md")))
    decisions = _non_readme(_md_files(os.path.join(root, "specs", "decisions", "*.md")))
    guarantees = _md_files(
        os.path.join(root, "specs", "components", "*", "interface", "guarantees", "*.md")
    )
    requirements = _md_files(os.path.join(root, "specs", "components", "*", "requirements", "*.md"))
    acceptance = _md_files(os.path.join(root, "specs", "components", "*", "acceptance", "*.md"))

    scenarios = 0
    for p in product:
        with open(p, encoding="utf-8") as fh:
            scenarios += len(CS_HEADING.findall(fh.read()))

    return {
        "component": len(components),
        "capability": len(product),
        "var": len(vars_),
        "decision": len(decisions),
        "guarantee": len(guarantees),
        "requirement": len(requirements),
        "acceptance": len(acceptance),
        "capability_scenario": scenarios,
    }


def _view_counts(con):
    rows = con.execute("SELECT kind, count(*) FROM nodes GROUP BY kind").fetchall()
    counts = {k: 0 for k in KINDS}
    for kind, n in rows:
        counts[kind] = n
    return counts


def _find_real_repo_root():
    """Tool root: parent of the nearest `gen` dir above the module, else any
    ancestor holding a spec corpus."""
    here = Path(graph_query_engine.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            candidate = parent.parent
            if (candidate / "specs" / "components").is_dir():
                return candidate
            break
    for parent in here.parents:
        if (parent / "specs" / "components").is_dir():
            return parent
    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        if (parent / "specs" / "components").is_dir():
            return parent
    return None


# --------------------------------------------------------------------------
# synthetic corpus fixture
# --------------------------------------------------------------------------


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(root: Path):
    specs = root / "specs"

    for slug, n_req, n_g in (("alpha", 2, 1), ("beta", 1, 2), ("gamma", 3, 0)):
        upper = slug.upper()
        _write(
            specs / "components" / slug / "component.md",
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()} Component\n"
            "status: draft\n"
            "owners: [test-team]\n"
            "depends_on: []\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            "---\n\n"
            f"# {slug.capitalize()}\n\n## Purpose\n\nDoes {slug} things.\n",
        )
        _write(
            specs / "components" / slug / "constraints.md",
            "# Constraints\n\nNone.\n",
        )
        for i in range(1, n_req + 1):
            rid = f"R-{upper}-{i:03d}"
            acid = f"AC-{upper}-{i:03d}"
            _write(
                specs / "components" / slug / "requirements" / f"{rid}.md",
                f"# {rid}\n\n**{rid}** — The component MUST do thing {i}.\n",
            )
            _write(
                specs / "components" / slug / "acceptance" / f"{acid}.md",
                f"# {acid}\n\nCovers: {rid}\nKind: generated-test\n\n"
                "```gherkin\nGiven x\nWhen y\nThen z\n```\n",
            )
        for i in range(1, n_g + 1):
            gid = f"G-{upper}-{i:03d}"
            _write(
                specs / "components" / slug / "interface" / "guarantees" / f"{gid}.md",
                f"# {gid}\n\nThe component guarantees property {i}.\n",
            )

    _write(
        specs / "product" / "P-ONE.md",
        "---\nid: P-ONE\ntitle: Capability One\nstatus: draft\nowners: [test-team]\n---\n\n"
        "# Capability One\n\n## Scenarios\n\n"
        "### CS-ONE-001\n\nCovers: P-ONE\n\n"
        "### CS-ONE-002\n\nCovers: P-ONE\n",
    )
    _write(
        specs / "product" / "P-TWO.md",
        "---\nid: P-TWO\ntitle: Capability Two\nstatus: draft\nowners: [test-team]\n---\n\n"
        "# Capability Two\n\n### CS-TWO-001\n\nCovers: P-TWO\n",
    )
    _write(
        specs / "product" / "README.md",
        "# Product capabilities\n\nEach file here is one product capability.\n\n"
        "### How to add one\n\nCopy an existing file.\n",
    )

    _write(
        specs / "vars" / "VAR-FOO.md",
        "---\nid: VAR-FOO\ntitle: Foo var\nstatus: draft\nowners: [test-team]\n---\n\n# VAR-FOO\n",
    )
    _write(
        specs / "vars" / "VAR-BAR-BAZ.md",
        "---\nid: VAR-BAR-BAZ\ntitle: Bar baz var\nstatus: draft\nowners: [test-team]\n---\n\n"
        "# VAR-BAR-BAZ\n",
    )
    _write(
        specs / "vars" / "README.md",
        "# Vars\n\nDeclarations only, never values.\n",
    )

    _write(
        specs / "decisions" / "D1.md",
        "---\nid: D1\ntitle: First decision\nstatus: ratified\nowners: [test-team]\n"
        "last_ratified_commit: abc1234\n---\n\n# D1\n",
    )
    _write(
        specs / "decisions" / "D2.md",
        "---\nid: D2\ntitle: Second decision\nstatus: draft\nowners: [test-team]\n---\n\n# D2\n",
    )
    _write(
        specs / "decisions" / "D3.md",
        "---\nid: D3\ntitle: Third decision\nstatus: deprecated\nowners: [test-team]\n---\n\n# D3\n",
    )
    _write(
        specs / "decisions" / "README.md",
        "# Decisions\n\nOne file per decision record.\n",
    )


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------


def test_nodes_counts_per_kind_match_filesystem_on_synthetic_corpus(tmp_path):
    repo_root = tmp_path.resolve()
    _build_corpus(repo_root)

    expected = _independent_counts(repo_root)
    # Sanity on the independent count itself (README.md excluded).
    assert expected == {
        "component": 3,
        "capability": 2,
        "var": 2,
        "decision": 3,
        "guarantee": 3,
        "requirement": 6,
        "acceptance": 6,
        "capability_scenario": 3,
    }

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)
        actual = _view_counts(con)

        for kind in KINDS:
            assert actual[kind] == expected[kind], (
                f"kind {kind!r}: nodes has {actual[kind]} rows, "
                f"file system has {expected[kind]}"
            )

        # No README-derived row sneaks in under any id (including a NULL id).
        for kind in ("capability", "var", "decision"):
            ids = {
                r[0]
                for r in con.execute("SELECT id FROM nodes WHERE kind = ?", [kind]).fetchall()
            }
            assert None not in ids, f"{kind} has a NULL-id row (README counted?)"
        assert {
            r[0] for r in con.execute("SELECT id FROM nodes WHERE kind = 'capability'").fetchall()
        } == {"P-ONE", "P-TWO"}
        assert {
            r[0] for r in con.execute("SELECT id FROM nodes WHERE kind = 'var'").fetchall()
        } == {"VAR-FOO", "VAR-BAR-BAZ"}
        assert {
            r[0] for r in con.execute("SELECT id FROM nodes WHERE kind = 'decision'").fetchall()
        } == {"D1", "D2", "D3"}
    finally:
        con.close()


def test_nodes_counts_per_kind_match_filesystem_on_real_corpus():
    repo_root = _find_real_repo_root()
    if repo_root is None:
        pytest.skip("no real spec corpus found above the module under test")
    repo_root = repo_root.resolve()

    expected = _independent_counts(repo_root)
    assert expected["component"] > 0

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)
        actual = _view_counts(con)
    finally:
        con.close()

    for kind in KINDS:
        assert actual[kind] == expected[kind], (
            f"kind {kind!r}: nodes has {actual[kind]} rows, "
            f"file system has {expected[kind]}"
        )