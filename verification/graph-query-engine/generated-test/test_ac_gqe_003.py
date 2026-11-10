import shutil
import tempfile
from pathlib import Path

import duckdb

import graph_query_engine


def test_ac_gqe_003():
    repo_root = Path(tempfile.mkdtemp())
    try:
        components_dir = repo_root / "specs" / "components"
        components = {
            "alpha": ("Alpha Component", "ALPHA_BODY_MARKER_TEXT"),
            "beta": ("Beta Component", "BETA_BODY_MARKER_TEXT"),
            "gamma": ("Gamma Component", "GAMMA_BODY_MARKER_TEXT"),
        }
        for slug, (title, marker) in components.items():
            comp_dir = components_dir / slug
            comp_dir.mkdir(parents=True, exist_ok=True)
            content = (
                "---\n"
                f"id: comp-{slug}\n"
                f"title: {title}\n"
                "status: draft\n"
                "owners: [alice]\n"
                "sealed: true\n"
                f"source_path: fake/{slug}.py\n"
                "depends_on: []\n"
                "---\n"
                "\n"
                f"# {title}\n"
                "\n"
                "## Purpose\n"
                "\n"
                f"This is the {slug} component's purpose paragraph, marker {marker}.\n"
            )
            (comp_dir / "component.md").write_text(content)

        real_component_count = len(list(components_dir.glob("*/component.md")))
        assert real_component_count == 3

        con = duckdb.connect()
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)

        row_count = con.execute("SELECT COUNT(*) FROM component_docs").fetchone()[0]
        assert row_count == real_component_count

        result = con.execute(
            "SELECT title, status, body FROM component_docs WHERE id = 'comp-alpha'"
        ).fetchone()
        assert result is not None
        title, status, body = result

        assert title == "Alpha Component"
        assert status == "draft"
        assert "ALPHA_BODY_MARKER_TEXT" in body
        assert "id: comp-alpha" in body
        assert "---" in body
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)