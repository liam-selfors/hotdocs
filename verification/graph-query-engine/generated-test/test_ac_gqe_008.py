# hotdocs-criterion: sha256:e0b48aff94edffb559380770e59586bb9b2beead36c6961b1ee5422fbcafc627
import json
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

import graph_query_engine


RATIFIED_COMMIT = "abc123def4567890abc123def4567890abc12345"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _build_corpus(root: Path) -> None:
    # A minimal but complete corpus so every view load_views creates has
    # something to bind against, not only decision_lineage.
    comp_dir = root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small thing for testing.\n"
        "\n"
        "## Notes\n"
        "\n"
        "Nothing else here.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do its small thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given foo\n"
        "When foo runs\n"
        "Then foo works\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nfoo() -> None\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    _write(
        root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: []\n"
        "---\n"
        "\n"
        "# Foo capability\n",
    )
    _write(
        root / "specs" / "vars" / "VAR-FOO.md",
        "---\n"
        "id: VAR-FOO\n"
        "title: Foo var\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# VAR-FOO\n",
    )

    # Decision WITH last_ratified_commit set.
    _write(
        root / "specs" / "decisions" / "D901.md",
        "---\n"
        "id: D901\n"
        "title: Ratified decision\n"
        "status: ratified\n"
        "owners: [alice]\n"
        f"last_ratified_commit: {RATIFIED_COMMIT}\n"
        "---\n"
        "\n"
        "# D901\n\nA ratified decision.\n",
    )
    # Decision with NO last_ratified_commit field at all.
    _write(
        root / "specs" / "decisions" / "D902.md",
        "---\n"
        "id: D902\n"
        "title: Draft decision\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# D902\n\nA draft decision, never ratified.\n",
    )

    _write(
        root / "gen" / "foo" / ".provenance.json",
        json.dumps(
            {
                "component_id": "comp-foo",
                "spec_bundle_hash": "sha256:0000",
                "verification_report": {"passed": True},
                "license_scan": {"passed": True},
                "secret_scan": {"passed": True},
                "provenance_hit": False,
            }
        ),
    )


def _connect_with_yaml():
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # environment cannot provide the extension
        con.close()
        pytest.skip(f"yaml community extension unavailable: {exc}")
    return con


def test_ac_gqe_008_decision_lineage_ratified_commit_and_null(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    con = _connect_with_yaml()
    try:
        graph_query_engine.load_views(con, repo_root)

        cur = con.execute("SELECT * FROM decision_lineage")
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()

        # The view has exactly the two columns, nothing else.
        assert sorted(columns) == sorted(["id", "last_ratified_commit"]), columns
        assert len(columns) == 2, columns

        id_idx = columns.index("id")
        commit_idx = columns.index("last_ratified_commit")
        by_id = {}
        for row in rows:
            by_id.setdefault(row[id_idx], []).append(row[commit_idx])

        # One row per decision file.
        assert set(by_id.keys()) == {"D901", "D902"}, by_id
        assert len(by_id["D901"]) == 1, by_id
        assert len(by_id["D902"]) == 1, by_id

        # Ratified decision carries its commit.
        assert by_id["D901"][0] == RATIFIED_COMMIT

        # Decision without the field yields NULL, never an empty string.
        assert by_id["D902"][0] is None
        assert by_id["D902"][0] != ""

        # Confirm NULL-ness at the SQL level as well.
        null_count = con.execute(
            "SELECT count(*) FROM decision_lineage "
            "WHERE id = 'D902' AND last_ratified_commit IS NULL"
        ).fetchone()[0]
        assert null_count == 1
        empty_count = con.execute(
            "SELECT count(*) FROM decision_lineage WHERE last_ratified_commit = ''"
        ).fetchone()[0]
        assert empty_count == 0
    finally:
        con.close()