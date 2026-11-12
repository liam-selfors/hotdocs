import json
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

import graph_query_engine


PURPOSE_LINES = [
    "This component exists to exercise multi-line Purpose extraction.",
    "Its Purpose section deliberately spans several lines of prose,",
    "so that a regex lacking the DOTALL flag would silently extract",
    "an empty string instead of this full text.",
]
EXPECTED_PURPOSE = "\n".join(PURPOSE_LINES)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"

    # Component under examination: multi-line Purpose followed by another section.
    alpha_dir = specs / "components" / "alpha"
    _write(
        alpha_dir / "component.md",
        "---\n"
        "id: comp-alpha\n"
        "title: Alpha\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: [comp-beta]\n"
        "realizes: []\n"
        "uses_var: [VAR-FOO]\n"
        "depends_on_guarantees: []\n"
        "sealed: true\n"
        "source_path: legacy/alpha\n"
        "---\n"
        "\n"
        "# Alpha\n"
        "\n"
        "## Purpose\n"
        "\n"
        + EXPECTED_PURPOSE
        + "\n"
        "\n"
        "## Definitions\n"
        "\n"
        "Nothing extra.\n",
    )
    _write(alpha_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        alpha_dir / "requirements" / "R-ALPHA-001.md",
        "# R-ALPHA-001\n\n**R-ALPHA-001** — Alpha MUST do a thing.\n",
    )
    _write(
        alpha_dir / "acceptance" / "AC-ALPHA-001.md",
        "# AC-ALPHA-001\n\nCovers: R-ALPHA-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x\nWhen y\nThen z\n```\n",
    )
    _write(alpha_dir / "interface" / "library.md", "# Library\n\n```\nalpha() -> None\n```\n")

    # A second component so frontmatter list columns have varied content.
    beta_dir = specs / "components" / "beta"
    _write(
        beta_dir / "component.md",
        "---\n"
        "id: comp-beta\n"
        "title: Beta\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "depends_on_guarantees: []\n"
        "sealed: true\n"
        "source_path: legacy/beta\n"
        "---\n"
        "\n"
        "# Beta\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Beta is a single-line dependency.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n",
    )
    _write(beta_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        beta_dir / "requirements" / "R-BETA-001.md",
        "# R-BETA-001\n\n**R-BETA-001** — Beta MUST do a thing.\n",
    )
    _write(
        beta_dir / "acceptance" / "AC-BETA-001.md",
        "# AC-BETA-001\n\nCovers: R-BETA-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x\nWhen y\nThen z\n```\n",
    )
    _write(beta_dir / "interface" / "library.md", "# Library\n\n```\nbeta() -> None\n```\n")

    # Product capability, var, and decisions so every view's source glob has files.
    _write(
        specs / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Foo\n\n## Purpose\n\nA capability.\n\n## Scenarios\n\nNone.\n",
    )
    _write(
        specs / "vars" / "VAR-FOO.md",
        "---\n"
        "id: VAR-FOO\n"
        "title: Foo var\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# VAR-FOO\n\nA variable.\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: ratified\n"
        "owners: [test-team]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "supersedes: []\n"
        "builds_on: []\n"
        "---\n"
        "\n"
        "# D1\n\nFirst.\n",
    )
    _write(
        specs / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Second decision\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "supersedes: []\n"
        "builds_on: [D1]\n"
        "---\n"
        "\n"
        "# D2\n\nSecond.\n",
    )

    # Provenance manifests so component_provenance has something to read.
    for slug in ("alpha", "beta"):
        manifest = {
            "component_id": "comp-" + slug,
            "spec_bundle_hash": "deadbeef",
            "verification_report": {"result": "pass"},
            "license_scan": {"result": "pass"},
            "secret_scan": {"result": "pass"},
            "provenance_hit": False,
        }
        _write(repo_root / "gen" / slug / ".provenance.json", json.dumps(manifest, indent=2))


def _connect_with_yaml():
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment-dependent
        con.close()
        pytest.skip(f"DuckDB community 'yaml' extension unavailable: {exc}")
    return con


def test_ac_gqe_004_multiline_purpose_extracted_in_full(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    con = _connect_with_yaml()
    try:
        result = graph_query_engine.load_views(con, repo_root)
        assert result is None

        rows = con.execute(
            "SELECT component_id, purpose FROM component_context WHERE component_id = ?",
            ["comp-alpha"],
        ).fetchall()

        assert len(rows) == 1, f"expected exactly one component_context row for comp-alpha, got {rows!r}"
        component_id, purpose = rows[0]
        assert component_id == "comp-alpha"

        assert purpose is not None, "purpose must not be NULL for a multi-line Purpose section"
        assert purpose != "", "purpose extracted to an empty string (missing DOTALL flag?)"
        assert purpose.strip() != ""

        # Full multi-line text, verbatim (modulo surrounding blank-line whitespace).
        assert "\n" in purpose.strip(), "purpose should retain its internal newlines"
        assert purpose.strip() == EXPECTED_PURPOSE

        for line in PURPOSE_LINES:
            assert line in purpose

        # Must stop at the next section, not swallow it.
        assert "## Definitions" not in purpose
        assert "Nothing extra." not in purpose
        assert "## Purpose" not in purpose
    finally:
        con.close()


def test_ac_gqe_004_one_row_per_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    con = _connect_with_yaml()
    try:
        graph_query_engine.load_views(con, repo_root)

        rows = con.execute(
            "SELECT component_id, purpose FROM component_context ORDER BY component_id"
        ).fetchall()
        by_id = {}
        for cid, purpose in rows:
            assert cid not in by_id, f"duplicate component_context row for {cid}"
            by_id[cid] = purpose

        assert set(by_id) == {"comp-alpha", "comp-beta"}
        assert by_id["comp-alpha"] is not None
        assert by_id["comp-alpha"].strip() == EXPECTED_PURPOSE
        assert by_id["comp-beta"] is not None
        assert by_id["comp-beta"].strip() == "Beta is a single-line dependency."
    finally:
        con.close()