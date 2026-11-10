import tempfile
from pathlib import Path

import duckdb

import graph_query_engine


def test_ac_gqe_008_decision_lineage_last_ratified_commit():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        decisions_dir = repo_root / "specs" / "decisions"
        decisions_dir.mkdir(parents=True)

        (decisions_dir / "D001.md").write_text(
            "---\n"
            "id: D001\n"
            "title: First Decision\n"
            "status: ratified\n"
            "owners: [alice]\n"
            "last_ratified_commit: abc123def\n"
            "---\n"
            "\n"
            "# D001\n"
            "\n"
            "Body text for the first decision.\n"
        )

        (decisions_dir / "D002.md").write_text(
            "---\n"
            "id: D002\n"
            "title: Second Decision\n"
            "status: draft\n"
            "owners: [bob]\n"
            "---\n"
            "\n"
            "# D002\n"
            "\n"
            "Body text for the second decision, never ratified.\n"
        )

        con = duckdb.connect()
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)

        result = con.execute("SELECT * FROM decision_lineage ORDER BY id")
        columns = [d[0] for d in result.description]
        rows = result.fetchall()

        assert columns == ["id", "last_ratified_commit"]
        assert len(rows) == 2

        first_row, second_row = rows

        assert first_row[0] == "D001"
        assert first_row[1] == "abc123def"

        assert second_row[0] == "D002"
        assert second_row[1] is None