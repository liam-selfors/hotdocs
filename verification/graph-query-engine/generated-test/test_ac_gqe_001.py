import glob
import os
import re
import tempfile
from pathlib import Path

import duckdb

import graph_query_engine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_corpus(repo_root: Path) -> None:
    # -- components (kind=component) --
    _write(
        repo_root / "specs/components/foo-comp/component.md",
        "---\n"
        "id: comp-foo-comp\n"
        "title: Foo Comp\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: fake/src/foo-comp\n"
        "---\n\n"
        "# Foo Comp\n\n"
        "## Purpose\n\n"
        "Does foo things.\n",
    )
    _write(
        repo_root / "specs/components/bar-comp/component.md",
        "---\n"
        "id: comp-bar-comp\n"
        "title: Bar Comp\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: fake/src/bar-comp\n"
        "---\n\n"
        "# Bar Comp\n\n"
        "## Purpose\n\n"
        "Does bar things.\n",
    )

    # -- product capability (kind=capability), also carries capability_scenario headings --
    _write(
        repo_root / "specs/product/widgets.md",
        "---\n"
        "id: P-WIDGETS\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "# Widgets\n\n"
        "### CS-WIDGETS-001\n\n"
        "Some scenario text.\n\n"
        "### CS-WIDGETS-002\n\n"
        "Another scenario text.\n",
    )

    # -- var (kind=var) --
    _write(
        repo_root / "specs/vars/VAR-FOO-PATH.md",
        "---\n"
        "id: VAR-FOO-PATH\n"
        "title: Foo Path\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "Some var description.\n",
    )

    # -- decisions (kind=decision) --
    _write(
        repo_root / "specs/decisions/D1.md",
        "---\n"
        "id: D1\n"
        "title: Some decision\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: deadbeef\n"
        "---\n\n"
        "Some decision text.\n",
    )
    _write(
        repo_root / "specs/decisions/D2.md",
        "---\n"
        "id: D2\n"
        "title: Another decision\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "Another decision text.\n",
    )

    # -- unit files: guarantee/requirement/acceptance, two components each --
    _write(
        repo_root / "specs/components/foo-comp/interface/guarantees/G-FOO-001.md",
        "# G-FOO-001\n\nSome guarantee text.\n",
    )
    _write(
        repo_root / "specs/components/bar-comp/interface/guarantees/G-BAR-001.md",
        "# G-BAR-001\n\nSome guarantee text.\n",
    )

    _write(
        repo_root / "specs/components/foo-comp/requirements/R-FOO-001.md",
        "# R-FOO-001\n\nSome requirement text.\n",
    )
    _write(
        repo_root / "specs/components/bar-comp/requirements/R-BAR-001.md",
        "# R-BAR-001\n\nSome requirement text.\n",
    )

    _write(
        repo_root / "specs/components/foo-comp/acceptance/AC-FOO-001.md",
        "Covers: R-FOO-001\n\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it happens\n"
        "Then it works\n"
        "```\n",
    )
    _write(
        repo_root / "specs/components/bar-comp/acceptance/AC-BAR-001.md",
        "Covers: R-BAR-001\n\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it happens\n"
        "Then it works\n"
        "```\n",
    )


def _independent_counts(repo_root: Path) -> dict:
    counts = {}

    counts["component"] = len(
        glob.glob(os.path.join(str(repo_root), "specs", "components", "*", "component.md"))
    )
    counts["capability"] = len(
        glob.glob(os.path.join(str(repo_root), "specs", "product", "*.md"))
    )
    counts["var"] = len(
        glob.glob(os.path.join(str(repo_root), "specs", "vars", "*.md"))
    )
    counts["decision"] = len(
        glob.glob(os.path.join(str(repo_root), "specs", "decisions", "*.md"))
    )
    counts["guarantee"] = len(
        glob.glob(
            os.path.join(
                str(repo_root), "specs", "components", "*", "interface", "guarantees", "*.md"
            )
        )
    )
    counts["requirement"] = len(
        glob.glob(
            os.path.join(str(repo_root), "specs", "components", "*", "requirements", "*.md")
        )
    )
    counts["acceptance"] = len(
        glob.glob(
            os.path.join(str(repo_root), "specs", "components", "*", "acceptance", "*.md")
        )
    )

    scenario_total = 0
    for path in glob.glob(os.path.join(str(repo_root), "specs", "product", "*.md")):
        text = Path(path).read_text()
        scenario_total += len(re.findall(r"### (CS-[A-Za-z0-9-]+)", text))
    counts["capability_scenario"] = scenario_total

    return counts


def test_ac_gqe_001_node_counts_match_filesystem_per_kind():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _build_corpus(repo_root)

        expected_counts = _independent_counts(repo_root)

        con = duckdb.connect()
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)

        rows = con.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind").fetchall()
        actual_counts = {kind: count for kind, count in rows}

        expected_kinds = {
            "component",
            "capability",
            "var",
            "decision",
            "guarantee",
            "requirement",
            "acceptance",
            "capability_scenario",
        }

        assert expected_kinds == set(expected_counts.keys())

        for kind in expected_kinds:
            assert kind in actual_counts, (
                f"kind {kind!r} missing from nodes view; "
                f"expected filesystem count {expected_counts[kind]}"
            )
            assert actual_counts[kind] == expected_counts[kind], (
                f"kind {kind!r}: nodes view reported {actual_counts[kind]} rows, "
                f"independent filesystem count found {expected_counts[kind]}"
            )