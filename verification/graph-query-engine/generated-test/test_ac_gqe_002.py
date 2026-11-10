import re
from pathlib import Path

import duckdb

import graph_query_engine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    components = {
        "comp-alpha": (
            """---
id: comp-alpha
title: Alpha
status: draft
owners: [alice]
depends_on: [comp-beta, comp-gamma]
realizes: [P-widget]
uses_var: [VAR-FOO]
depends_on_guarantees: [G-bar]
sealed: false
---

# Alpha

## Purpose

Alpha does alpha things.
""",
            "R-ALPHA-001",
        ),
        "comp-beta": (
            """---
id: comp-beta
title: Beta
status: draft
owners: [bob]
depends_on: []
realizes: []
uses_var: [VAR-FOO, VAR-BAZ]
depends_on_guarantees: []
sealed: true
source_path: fixtures/beta
---

# Beta

## Purpose

Beta does beta things.
""",
            "R-BETA-001",
        ),
        "comp-gamma": (
            """---
id: comp-gamma
title: Gamma
status: draft
owners: [carol]
depends_on: [comp-alpha]
realizes: []
uses_var: []
depends_on_guarantees: [G-bar, G-baz]
sealed: true
source_path: fixtures/gamma
---

# Gamma

## Purpose

Gamma does gamma things.
""",
            "R-GAMMA-001",
        ),
    }

    for slug, (frontmatter, req_id) in components.items():
        comp_dir = repo_root / "specs" / "components" / slug
        _write(comp_dir / "component.md", frontmatter)
        _write(
            comp_dir / "requirements" / f"{req_id}.md",
            f"# {req_id}\n\nA requirement for {slug}.\n",
        )
        ac_id = req_id.replace("R-", "AC-")
        _write(
            comp_dir / "acceptance" / f"{ac_id}.md",
            f"# {ac_id}\n\nCovers: {req_id}\n\n"
            "```gherkin\nGiven a precondition\nWhen the action runs\n"
            "Then the outcome holds\n```\n",
        )

    _write(
        repo_root / "specs" / "product" / "widget.md",
        """---
id: P-widget
title: Widget
status: draft
owners: [dave]
---

# Widget

## Capability Scenarios

### CS-WIDGET-001
Covers: R-ALPHA-001
""",
    )

    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        """---
id: D1
title: Some Decision
status: ratified
owners: [eve]
last_ratified_commit: abc123
---

# D1

A decision with no supersedes or builds_on fields.
""",
    )


def _independent_edge_counts(repo_root: Path) -> dict:
    counts = {
        "depends_on": 0,
        "realizes": 0,
        "uses_var": 0,
        "depends_on_guarantees": 0,
        "covers": 0,
    }

    comp_dir = repo_root / "specs" / "components"
    for comp_path in sorted(comp_dir.glob("*/component.md")):
        text = comp_path.read_text(encoding="utf-8")
        for field in ("depends_on", "realizes", "uses_var", "depends_on_guarantees"):
            match = re.search(rf"{field}:\s*\[([^\]]*)\]", text)
            if not match:
                continue
            entries = [entry.strip() for entry in match.group(1).split(",") if entry.strip()]
            counts[field] += len(entries)

    for ac_path in sorted(comp_dir.glob("*/acceptance/*.md")):
        text = ac_path.read_text(encoding="utf-8")
        if re.search(r"Covers:\s*\S+", text):
            counts["covers"] += 1

    for prod_path in sorted((repo_root / "specs" / "product").glob("*.md")):
        text = prod_path.read_text(encoding="utf-8")
        counts["covers"] += len(
            re.findall(r"### CS-[A-Za-z0-9-]+\s*\nCovers:\s*\S+", text)
        )

    return counts


def test_edges_row_counts_match_independent_tag_counts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)

    expected = _independent_edge_counts(repo_root)
    assert expected == {
        "depends_on": 3,
        "realizes": 1,
        "uses_var": 3,
        "depends_on_guarantees": 3,
        "covers": 4,
    }

    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")

    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT edge_type, COUNT(*) FROM edges "
        "WHERE edge_type IN ('depends_on', 'realizes', 'uses_var', "
        "'depends_on_guarantees', 'covers') "
        "GROUP BY edge_type"
    ).fetchall()
    actual = {edge_type: count for edge_type, count in rows}

    for edge_type, expected_count in expected.items():
        assert actual.get(edge_type) == expected_count