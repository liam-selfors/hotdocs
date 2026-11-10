import tempfile
from pathlib import Path

import duckdb

import graph_query_engine


def test_component_context_purpose_multiline():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        comp_dir = repo_root / "specs" / "components" / "fake-widget"
        comp_dir.mkdir(parents=True)

        purpose_lines = [
            "This is a multi-line purpose section.",
            "It spans several lines of text.",
            "Here is a third line for good measure.",
        ]
        purpose_body = "\n".join(purpose_lines)

        component_md = (
            "---\n"
            "id: comp-fake-widget\n"
            "title: Fake Widget\n"
            "status: draft\n"
            "owners: [alice, bob]\n"
            "depends_on: []\n"
            "sealed: true\n"
            "source_path: fake/fake_widget.py\n"
            "---\n"
            "\n"
            "# Fake Widget\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"{purpose_body}\n"
            "\n"
            "## Interface\n"
            "\n"
            "Some interface text.\n"
        )
        (comp_dir / "component.md").write_text(component_md)

        con = duckdb.connect()
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)

        rows = con.execute(
            "SELECT component_id, purpose FROM component_context WHERE component_id = ?",
            ["comp-fake-widget"],
        ).fetchall()

        assert len(rows) == 1
        component_id, purpose = rows[0]
        assert component_id == "comp-fake-widget"
        assert purpose is not None
        assert purpose.strip() != ""
        for line in purpose_lines:
            assert line in purpose