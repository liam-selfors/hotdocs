import graph_query_engine

import re
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")


FIVE_EDGE_TYPES = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "covers")
LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _connect():
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment dependent
        con.close()
        pytest.skip(f"DuckDB yaml community extension unavailable: {exc}")
    return con


def _edge_counts(con):
    rows = con.execute(
        "SELECT edge_type, count(*) FROM edges GROUP BY edge_type"
    ).fetchall()
    return {r[0]: int(r[1]) for r in rows}


def _edge_pairs(con, edge_type):
    rows = con.execute(
        "SELECT source_id, target_id FROM edges WHERE edge_type = ?", [edge_type]
    ).fetchall()
    return sorted((r[0], r[1]) for r in rows)


def _frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else None


def _list_field_count(fm, key):
    """Count non-empty entries of a flow-style `key: [a, b]` frontmatter line."""
    if fm is None:
        return 0
    for line in fm.splitlines():
        m = re.match(r"^" + re.escape(key) + r":[ \t]*\[([^\]]*)\]", line)
        if m:
            return len([e for e in (p.strip(" ") for p in m.group(1).split(",")) if e != ""])
    return 0


def _independent_counts(repo_root):
    """Count expected edges directly from frontmatter / Covers: tags."""
    repo_root = Path(repo_root)
    counts = {t: 0 for t in FIVE_EDGE_TYPES}
    counts["supersedes"] = 0
    counts["builds_on"] = 0

    for comp in sorted(repo_root.glob("specs/components/*/component.md")):
        fm = _frontmatter(comp.read_text(encoding="utf-8"))
        for key in LIST_FIELDS:
            counts[key] += _list_field_count(fm, key)

    for ac in sorted(repo_root.glob("specs/components/*/acceptance/*.md")):
        text = ac.read_text(encoding="utf-8")
        if re.search(r"(?m)^Covers:[ \t]*\S+", text):
            counts["covers"] += 1

    for prod in sorted(repo_root.glob("specs/product/*.md")):
        text = prod.read_text(encoding="utf-8")
        counts["covers"] += len(
            re.findall(r"### (CS-[A-Za-z0-9-]+)\s*\nCovers:\s*(\S+)", text)
        )

    for dec in sorted(repo_root.glob("specs/decisions/*.md")):
        fm = _frontmatter(dec.read_text(encoding="utf-8"))
        if fm is None:
            continue
        if re.search(r"(?m)^supersedes:[ \t]*\S+", fm):
            counts["supersedes"] += 1
        counts["builds_on"] += _list_field_count(fm, "builds_on")

    return counts


def _tool_root():
    here = Path(graph_query_engine.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(root, slug, extra_fm, purpose, req_ids):
    comp_dir = root / "specs" / "components" / slug
    fm = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        f"{extra_fm}"
        "---\n"
    )
    body = (
        f"\n# {slug.capitalize()}\n\n"
        "## Purpose\n\n"
        f"{purpose}\n\n"
        "## Change log\n\n"
        "- Initial draft.\n"
    )
    _write(comp_dir / "component.md", fm + body)
    _write(comp_dir / "constraints.md", "# Constraints\n\nNo network access.\n")
    _write(
        comp_dir / "interface" / "library.md",
        f"# Library\n\n```\nrun_{slug}() -> None\n```\n\nDoes the {slug} thing.\n",
    )
    for rid in req_ids:
        suffix = rid.split("-", 1)[1]
        _write(
            comp_dir / "requirements" / f"{rid}.md",
            f"# {rid}\n\n**{rid}** — The component MUST do thing {suffix}.\n",
        )
        ac_id = "AC-" + suffix
        _write(
            comp_dir / "acceptance" / f"{ac_id}.md",
            f"# {ac_id}\n\n"
            f"Covers: {rid}\n"
            "Kind: compiled\n\n"
            "```gherkin\n"
            "Given a thing\n"
            "When it runs\n"
            "Then it works\n"
            "```\n",
        )


def _provenance(root, slug):
    text = (
        "{\n"
        f'  "component_id": "comp-{slug}",\n'
        '  "spec_bundle_hash": "sha256:0000000000000000",\n'
        '  "generated_at": "2026-01-01T00:00:00Z",\n'
        '  "model": "anthropic:claude-sonnet-5",\n'
        '  "verification_report": {"result": "pass", "criteria": 1},\n'
        '  "license_scan": {"result": "pass", "findings": 0},\n'
        '  "secret_scan": {"result": "pass", "findings": 0},\n'
        '  "provenance_hit": false\n'
        "}\n"
    )
    _write(root / "gen" / slug / ".provenance.json", text)
    _write(root / "verification" / slug / ".provenance.json", text)


def _build_fixture(root):
    _component(
        root,
        "alpha",
        "depends_on: []\nrealizes: [P-FOO]\nuses_var: [VAR-FOO-PATH]\n",
        "Alpha produces foo outputs.",
        ["R-ALPHA-001", "R-ALPHA-002"],
    )
    _write(
        root / "specs" / "components" / "alpha" / "guarantees" / "G-ALPHA-001.md",
        "# G-ALPHA-001\n\n**G-ALPHA-001** — Alpha's output is deterministic.\n",
    )
    _component(
        root,
        "beta",
        "depends_on: [comp-alpha]\nrealizes: [P-FOO]\ndepends_on_guarantees: [G-ALPHA-001]\n",
        "Beta consumes alpha's outputs.",
        ["R-BETA-001"],
    )
    _component(
        root,
        "gamma",
        "sealed: true\nsource_path: legacy/gamma/\ndepends_on: [comp-alpha, comp-beta]\n",
        "Gamma wraps legacy code.",
        ["R-GAMMA-001"],
    )
    _provenance(root, "alpha")
    _provenance(root, "beta")

    _write(
        root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n\n"
        "# Foo capability\n\n"
        "## Capability scenarios\n\n"
        "### CS-FOO-001\n"
        "Covers: P-FOO\n\n"
        "```gherkin\nGiven foo\nWhen bar\nThen baz\n```\n\n"
        "### CS-FOO-002\n"
        "Covers: P-FOO\n\n"
        "```gherkin\nGiven foo\nWhen qux\nThen quux\n```\n",
    )

    _write(
        root / "specs" / "vars" / "VAR-FOO-PATH.md",
        "---\n"
        "id: VAR-FOO-PATH\n"
        "title: Foo path\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n\n"
        "# VAR-FOO-PATH\n\nPath to the foo corpus.\n",
    )

    _write(
        root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: deprecated\n"
        "owners: [team-a]\n"
        "last_ratified_commit: abc1234\n"
        "---\n\n"
        "# D1\n\nThe original choice.\n",
    )
    _write(
        root / "specs" / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Second decision\n"
        "status: ratified\n"
        "owners: [team-a]\n"
        "last_ratified_commit: def5678\n"
        "supersedes: D1\n"
        "---\n\n"
        "# D2\n\nReplaces D1.\n",
    )
    _write(
        root / "specs" / "decisions" / "D3.md",
        "---\n"
        "id: D3\n"
        "title: Third decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "builds_on: [D1, D2]\n"
        "---\n\n"
        "# D3\n\n"
        "An earlier draft of this record declared, in its own frontmatter:\n\n"
        "supersedes: D9\n"
        "builds_on: [D7, D8]\n\n"
        "That quoted prose is not a declaration.\n",
    )

    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Thing** — a thing.\n",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_edges_counts_match_independent_count_on_synthetic_corpus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    independent = _independent_counts(repo_root)
    # Sanity-check the independent counter against hand-computed values.
    assert independent == {
        "depends_on": 3,
        "realizes": 2,
        "uses_var": 1,
        "depends_on_guarantees": 1,
        "covers": 6,
        "supersedes": 1,
        "builds_on": 2,
    }

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)
        counts = _edge_counts(con)

        for edge_type in FIVE_EDGE_TYPES:
            assert counts.get(edge_type, 0) == independent[edge_type], (
                edge_type,
                counts,
                independent,
            )
        for edge_type in ("supersedes", "builds_on"):
            assert counts.get(edge_type, 0) == independent[edge_type], (
                edge_type,
                counts,
                independent,
            )

        assert _edge_pairs(con, "depends_on") == sorted(
            [
                ("comp-beta", "comp-alpha"),
                ("comp-gamma", "comp-alpha"),
                ("comp-gamma", "comp-beta"),
            ]
        )
        assert _edge_pairs(con, "realizes") == sorted(
            [("comp-alpha", "P-FOO"), ("comp-beta", "P-FOO")]
        )
        assert _edge_pairs(con, "uses_var") == [("comp-alpha", "VAR-FOO-PATH")]
        assert _edge_pairs(con, "depends_on_guarantees") == [
            ("comp-beta", "G-ALPHA-001")
        ]
        assert _edge_pairs(con, "covers") == sorted(
            [
                ("AC-ALPHA-001", "R-ALPHA-001"),
                ("AC-ALPHA-002", "R-ALPHA-002"),
                ("AC-BETA-001", "R-BETA-001"),
                ("AC-GAMMA-001", "R-GAMMA-001"),
                ("CS-FOO-001", "P-FOO"),
                ("CS-FOO-002", "P-FOO"),
            ]
        )
        assert _edge_pairs(con, "supersedes") == [("D2", "D1")]
        assert _edge_pairs(con, "builds_on") == sorted(
            [("D3", "D1"), ("D3", "D2")]
        )
    finally:
        con.close()


def test_edges_counts_match_independent_count_on_real_corpus():
    tool_root = _tool_root()
    if tool_root is None:
        pytest.skip("module under test is not located under a gen/ directory")
    components = list(tool_root.glob("specs/components/*/component.md"))
    if not components:
        pytest.skip(f"no real spec corpus found under {tool_root}")

    independent = _independent_counts(tool_root)

    con = _connect()
    try:
        graph_query_engine.load_views(con, tool_root)
        counts = _edge_counts(con)
    finally:
        con.close()

    for edge_type in FIVE_EDGE_TYPES:
        assert counts.get(edge_type, 0) == independent[edge_type], (
            edge_type,
            counts.get(edge_type, 0),
            independent[edge_type],
        )
    # A real corpus exercises at least depends_on and covers edges.
    assert independent["depends_on"] > 0
    assert independent["covers"] > 0