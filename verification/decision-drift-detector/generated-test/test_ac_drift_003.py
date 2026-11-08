import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import decision_drift_detector


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test Author",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    subprocess.run(
        ["git", "-C", str(repo_root)] + list(args),
        check=True,
        capture_output=True,
        env=env,
    )


GRAPH_QUERY_ENGINE_FAKE = textwrap.dedent(
    '''
    from pathlib import Path


    def _parse_frontmatter(text):
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        fm_text = parts[1]
        body = parts[2]
        fm = {}
        for line in fm_text.strip().splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip() for v in value[1:-1].split(",") if v.strip()]
                fm[key] = items
            else:
                fm[key] = value
        return fm, body


    def load_views(con, repo_root):
        repo_root = Path(repo_root)
        decisions_dir = repo_root / "specs" / "decisions"
        nodes_rows = []
        edges_rows = []
        lineage_rows = []
        if decisions_dir.is_dir():
            for path in sorted(decisions_dir.glob("D*.md")):
                text = path.read_text()
                fm, _ = _parse_frontmatter(text)
                did = fm.get("id", path.stem)
                title = fm.get("title")
                status = fm.get("status")
                nodes_rows.append((did, title, status, "decision", None))
                for edge_type in ("supersedes", "builds_on"):
                    for target in fm.get(edge_type, []) or []:
                        edges_rows.append((did, target, edge_type))
                last_commit = fm.get("last_ratified_commit") if status == "ratified" else None
                lineage_rows.append((did, last_commit))

        for view in (
            "nodes",
            "edges",
            "decision_lineage",
            "component_docs",
            "component_context",
            "component_provenance",
            "component_size",
        ):
            con.execute("DROP VIEW IF EXISTS " + view)
        for table in ("_nodes_data", "_edges_data", "_lineage_data"):
            con.execute("DROP TABLE IF EXISTS " + table)

        con.execute(
            "CREATE TABLE _nodes_data (id VARCHAR, title VARCHAR, status VARCHAR, "
            "kind VARCHAR, owner_component_id VARCHAR)"
        )
        for row in nodes_rows:
            con.execute("INSERT INTO _nodes_data VALUES (?, ?, ?, ?, ?)", row)
        con.execute("CREATE VIEW nodes AS SELECT * FROM _nodes_data")

        con.execute(
            "CREATE TABLE _edges_data (source_id VARCHAR, target_id VARCHAR, edge_type VARCHAR)"
        )
        for row in edges_rows:
            con.execute("INSERT INTO _edges_data VALUES (?, ?, ?)", row)
        con.execute("CREATE VIEW edges AS SELECT * FROM _edges_data")

        con.execute(
            "CREATE TABLE _lineage_data (id VARCHAR, last_ratified_commit VARCHAR)"
        )
        for row in lineage_rows:
            con.execute("INSERT INTO _lineage_data VALUES (?, ?)", row)
        con.execute("CREATE VIEW decision_lineage AS SELECT * FROM _lineage_data")

        con.execute(
            "CREATE VIEW component_docs AS SELECT "
            "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
            "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS body "
            "WHERE FALSE"
        )
        con.execute(
            "CREATE VIEW component_context AS SELECT "
            "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS VARCHAR) AS purpose "
            "WHERE FALSE"
        )
        con.execute(
            "CREATE VIEW component_provenance AS SELECT "
            "CAST(NULL AS VARCHAR) AS component_id, "
            "CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
            "CAST(NULL AS BOOLEAN) AS provenance_hit WHERE FALSE"
        )
        con.execute(
            "CREATE VIEW component_size AS SELECT "
            "CAST(NULL AS VARCHAR) AS component_id, "
            "CAST(NULL AS BIGINT) AS word_count WHERE FALSE"
        )
    '''
)


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


class TestAcDrift003(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name) / "repo"
        self.repo_root.mkdir()
        _git(self.repo_root, "init", "-q")

        gen_dir = self.repo_root / "gen" / "graph-query-engine"
        gen_dir.mkdir(parents=True)
        (gen_dir / "graph_query_engine.py").write_text(GRAPH_QUERY_ENGINE_FAKE)

        decisions_dir = self.repo_root / "specs" / "decisions"
        decisions_dir.mkdir(parents=True)
        (decisions_dir / "D1.md").write_text(
            textwrap.dedent(
                """\
                ---
                id: D1
                title: Original Decision
                status: ratified
                owners: [alice]
                last_ratified_commit: 0000000000000000000000000000000000000001
                ---

                The original decision body text.
                """
            )
        )

        component_dir = self.repo_root / "specs" / "components" / "foo"
        (component_dir / "requirements").mkdir(parents=True)
        (component_dir / "acceptance").mkdir(parents=True)
        (component_dir / "component.md").write_text(
            textwrap.dedent(
                """\
                ---
                id: comp-foo
                title: Foo Component
                status: ratified
                owners: [alice]
                sealed: true
                source_path: fixtures/foo
                ---

                ## Purpose

                Does foo things.
                """
            )
        )
        self.live_spec_file = component_dir / "requirements" / "R-FOO-001.md"
        self.live_spec_file.write_text(
            "**R-FOO-001** -- This requirement follows directly from decision "
            "D1 and must be honored accordingly.\n"
        )
        (component_dir / "acceptance" / "AC-FOO-001.md").write_text(
            "Covers: R-FOO-001\n\n"
            "```gherkin\n"
            "Given a precondition\n"
            "When an action happens\n"
            "Then an outcome holds\n"
            "```\n"
        )

        _git(self.repo_root, "add", "-A")
        _git(self.repo_root, "commit", "-q", "-m", "add D1 and foo component citing it")

        (decisions_dir / "D2.md").write_text(
            textwrap.dedent(
                """\
                ---
                id: D2
                title: Superseding Decision
                status: ratified
                owners: [alice]
                supersedes: [D1]
                last_ratified_commit: 0000000000000000000000000000000000000002
                ---

                The superseding decision body text.
                """
            )
        )
        _git(self.repo_root, "add", "-A")
        _git(self.repo_root, "commit", "-q", "-m", "add D2 superseding D1")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_impact_includes_superseding_decision_and_live_citation(self):
        report = decision_drift_detector.find_decision_impact(self.repo_root, "D1")

        dependent_decisions = _field(report, "dependent_decisions") or []
        citing_files = _field(report, "citing_files") or []

        self.assertIn("D2", list(dependent_decisions))

        live_file_str = str(
            self.live_spec_file.relative_to(self.repo_root)
        ).replace(os.sep, "/")
        normalized_citing_files = [
            str(f).replace(os.sep, "/").lstrip("/") for f in citing_files
        ]
        matched = any(
            entry == live_file_str or entry.endswith("/" + live_file_str)
            for entry in normalized_citing_files
        )
        self.assertTrue(
            matched,
            "expected citing_files to contain %r, got %r"
            % (live_file_str, citing_files),
        )


if __name__ == "__main__":
    unittest.main()