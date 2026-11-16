import json
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

import graph_query_engine


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(did: str, title: str, extra_fm: str = "", body: str = "") -> str:
    fm_lines = [
        f"id: {did}",
        f"title: {title}",
        "status: ratified",
        "owners: [alice]",
        "last_ratified_commit: 0000000000000000000000000000000000000000",
    ]
    if extra_fm:
        fm_lines.append(extra_fm)
    return "---\n" + "\n".join(fm_lines) + "\n---\n\n" + f"# {did} — {title}\n\n" + body + "\n"


def _build_corpus(root: Path) -> None:
    specs = root / "specs"

    # Glossary
    _write(specs / "glossary.md", "# Glossary\n\n- **Thing** — a thing.\n")

    # One sealed component with a full set of unit files
    comp_dir = specs / "components" / "alpha"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-alpha\n"
        "title: Alpha\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/alpha\n"
        "---\n"
        "\n"
        "# Alpha\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Alpha does a small fixture thing.\n"
        "\n"
        "## Guarantees\n"
        "\n"
        "- **G-ALPHA-001** — Alpha is deterministic.\n",
    )
    _write(
        comp_dir / "requirements" / "R-ALPHA-001.md",
        "# R-ALPHA-001\n\n**R-ALPHA-001** — Alpha MUST return a value.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-ALPHA-001.md",
        "# AC-ALPHA-001\n\n"
        "Covers: R-ALPHA-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\nGiven alpha\nWhen called\nThen it returns a value\n```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nalpha() -> int\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # Product capability file with one capability scenario
    _write(
        specs / "product" / "P-ALPHA.md",
        "---\n"
        "id: P-ALPHA\n"
        "title: Alpha Capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# Alpha Capability\n"
        "\n"
        "### CS-ALPHA-001\n"
        "Covers: G-ALPHA-001\n"
        "\n"
        "```gherkin\nGiven alpha\nThen it works\n```\n",
    )

    # Var declaration
    _write(
        specs / "vars" / "VAR-ALPHA-PATH.md",
        "---\n"
        "id: VAR-ALPHA-PATH\n"
        "title: Alpha Path\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# VAR-ALPHA-PATH\n\nA path.\n",
    )

    # Decisions
    decisions = specs / "decisions"
    _write(decisions / "D1.md", _decision("D1", "First decision", body="Plain prose.\n"))
    _write(decisions / "D2.md", _decision("D2", "Second decision", body="More plain prose.\n"))
    # D3: prose quotes the fields (including at a line start), frontmatter declares neither
    _write(
        decisions / "D3.md",
        _decision(
            "D3",
            "Prose-quoting decision",
            body=(
                "This decision discusses another record whose frontmatter read:\n"
                "\n"
                "supersedes: D1\n"
                "builds_on: [D2]\n"
                "\n"
                "and also inline as `supersedes: D1` and `builds_on: [D2]`,\n"
                "but declares neither itself.\n"
            ),
        ),
    )
    # D4: frontmatter declares builds_on: [D1, D2]
    _write(
        decisions / "D4.md",
        _decision(
            "D4",
            "Building decision",
            extra_fm="builds_on: [D1, D2]",
            body="Builds on two prior decisions.\n",
        ),
    )
    # D5: declares supersedes so the column/field exists somewhere in the corpus
    _write(
        decisions / "D5.md",
        _decision("D5", "Superseding decision", extra_fm="supersedes: D2", body="Replaces D2.\n"),
    )

    # A provenance manifest for the component
    _write(
        root / "gen" / "alpha" / ".provenance.json",
        json.dumps(
            {
                "component_id": "comp-alpha",
                "spec_bundle_hash": "sha256:" + "0" * 64,
                "model": "anthropic:claude-sonnet-5",
                "generated_at": "2026-01-01T00:00:00Z",
                "verification_report": {"passed": True, "gates": []},
                "license_scan": {"passed": True, "findings": []},
                "secret_scan": {"passed": True, "findings": []},
                "provenance_hit": False,
            },
            indent=2,
        )
        + "\n",
    )


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    root = tmp_path_factory.mktemp("gqe_ac010_repo")
    _build_corpus(root)
    connection = duckdb.connect()
    try:
        connection.execute("INSTALL yaml FROM community")
        connection.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment-dependent
        connection.close()
        pytest.skip(f"DuckDB community 'yaml' extension unavailable: {exc}")
    graph_query_engine.load_views(connection, root)
    yield connection
    connection.close()


def _decision_edges(con, source_id):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = ? AND edge_type IN ('supersedes', 'builds_on') "
        "ORDER BY target_id, edge_type",
        [source_id],
    ).fetchall()
    return [tuple(r) for r in rows]


def test_prose_quoted_fields_produce_no_decision_edges(con):
    rows = _decision_edges(con, "D3")
    assert rows == [], (
        "D3's prose quotes `supersedes: D1` and `builds_on: [D2]` but its "
        f"frontmatter declares neither; expected no edges, got {rows!r}"
    )
    # No edge anywhere should point from D3 to D1/D2 via these types
    stray = con.execute(
        "SELECT count(*) FROM edges WHERE source_id = 'D3' "
        "AND target_id IN ('D1', 'D2', '[D2]')"
    ).fetchone()[0]
    assert stray == 0


def test_frontmatter_builds_on_list_produces_exact_rows(con):
    rows = _decision_edges(con, "D4")
    assert sorted(rows) == [
        ("D4", "D1", "builds_on"),
        ("D4", "D2", "builds_on"),
    ], f"unexpected decision edges for D4: {rows!r}"
    # Exactly one row per (source, target, edge_type) — no duplicates
    dup = con.execute(
        "SELECT count(*) FROM ("
        "  SELECT source_id, target_id, edge_type, count(*) AS n FROM edges "
        "  WHERE source_id = 'D4' GROUP BY 1, 2, 3 HAVING count(*) > 1"
        ")"
    ).fetchone()[0]
    assert dup == 0