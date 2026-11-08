import os
import subprocess
import textwrap

import decision_drift_detector


def _run_git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def test_file_committed_after_supersession_is_not_drift(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _run_git(repo_root, "init")

    decisions_dir = repo_root / "specs" / "decisions"
    _write(
        decisions_dir / "D17.md",
        textwrap.dedent(
            """\
            ---
            id: D17
            title: Old Decision
            status: deprecated
            owners: [alice]
            ---

            The old decision, later superseded.
            """
        ),
    )
    _write(
        decisions_dir / "D31.md",
        textwrap.dedent(
            """\
            ---
            id: D31
            title: New Decision
            status: ratified
            owners: [alice]
            supersedes: [D17]
            last_ratified_commit: PENDING
            ---

            The decision that supersedes D17.
            """
        ),
    )
    _run_git(repo_root, "add", "-A")
    _run_git(repo_root, "commit", "-m", "ratify D31, deprecate D17")
    ratification_commit = _run_git(repo_root, "rev-parse", "HEAD")

    d31_path = decisions_dir / "D31.md"
    d31_path.write_text(
        d31_path.read_text().replace(
            "last_ratified_commit: PENDING",
            "last_ratified_commit: %s" % ratification_commit,
        )
    )
    _run_git(repo_root, "add", "-A")
    _run_git(repo_root, "commit", "-m", "record D31 ratification commit")

    component_dir = repo_root / "specs" / "components" / "foo"
    _write(
        component_dir / "component.md",
        textwrap.dedent(
            """\
            ---
            id: comp-foo
            title: Foo Component
            status: draft
            owners: [alice]
            sealed: true
            source_path: fake/foo
            ---

            # Foo

            ## Purpose

            A fake component used only to host a citation of D17.
            """
        ),
    )
    _write(
        component_dir / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** -- Some behavior, carried over from decision D17.\n",
    )
    _write(
        component_dir / "acceptance" / "AC-FOO-001.md",
        textwrap.dedent(
            """\
            Covers: R-FOO-001

            ```gherkin
            Given a thing
            When it happens
            Then it works
            ```
            """
        ),
    )
    _run_git(repo_root, "add", "-A")
    _run_git(repo_root, "commit", "-m", "add citing spec file, after D31 ratification")
    citing_rel_path = "specs/components/foo/requirements/R-FOO-001.md"
    citing_file_commit = _run_git(
        repo_root, "log", "-1", "--format=%H", "--", citing_rel_path
    )

    # Sanity-check the exact precondition this AC describes: the citing
    # file's own last-touch commit must be a descendant of, not an
    # ancestor of, the superseding ratification commit.
    ancestor_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", citing_file_commit, ratification_commit],
        cwd=str(repo_root),
    )
    assert ancestor_check.returncode != 0

    gen_dir = repo_root / "gen" / "graph-query-engine"
    gen_dir.mkdir(parents=True)
    (gen_dir / "graph_query_engine.py").write_text(
        textwrap.dedent(
            """\
            def load_views(con, repo_root):
                con.execute(
                    "CREATE OR REPLACE VIEW decision_lineage AS "
                    "SELECT * FROM (VALUES "
                    "('D17', CAST(NULL AS VARCHAR)), "
                    "('D31', '{ratification_commit}')"
                    ") AS t(id, last_ratified_commit)"
                )
                con.execute(
                    "CREATE OR REPLACE VIEW edges AS "
                    "SELECT * FROM (VALUES "
                    "('D31', 'D17', 'supersedes')"
                    ") AS t(source_id, target_id, edge_type)"
                )
                con.execute(
                    "CREATE OR REPLACE VIEW nodes AS "
                    "SELECT CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
                    "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS kind, "
                    "CAST(NULL AS VARCHAR) AS owner_component_id WHERE FALSE"
                )
                con.execute(
                    "CREATE OR REPLACE VIEW component_docs AS "
                    "SELECT CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
                    "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS body WHERE FALSE"
                )
                con.execute(
                    "CREATE OR REPLACE VIEW component_context AS "
                    "SELECT CAST(NULL AS VARCHAR) AS component_id, "
                    "CAST(NULL AS VARCHAR) AS purpose WHERE FALSE"
                )
                con.execute(
                    "CREATE OR REPLACE VIEW component_provenance AS "
                    "SELECT CAST(NULL AS VARCHAR) AS component_id WHERE FALSE"
                )
                con.execute(
                    "CREATE OR REPLACE VIEW component_size AS "
                    "SELECT CAST(NULL AS VARCHAR) AS component_id, "
                    "CAST(0 AS BIGINT) AS word_count WHERE FALSE"
                )
            """
        ).format(ratification_commit=ratification_commit)
    )

    report = decision_drift_detector.find_decision_drift(repo_root)

    entries = _field(report, "entries")
    assert entries is not None

    matching = [
        entry
        for entry in entries
        if _field(entry, "file") in (citing_rel_path, str(repo_root / citing_rel_path))
    ]
    assert matching == []