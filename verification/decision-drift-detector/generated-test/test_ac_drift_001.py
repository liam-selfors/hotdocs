import subprocess
import tempfile
from pathlib import Path


def run_git(repo_root, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def init_repo(repo_root):
    run_git(repo_root, "init", "-q")
    run_git(repo_root, "config", "user.email", "lselfors@gmail.com")
    run_git(repo_root, "config", "user.name", "lselfors")


def commit_all(repo_root, message):
    run_git(repo_root, "add", "-A")
    run_git(repo_root, "commit", "-q", "-m", message)
    return run_git(repo_root, "rev-parse", "HEAD")


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def frontmatter(id_, title, status, owners, extra=None):
    lines = [
        "---",
        f"id: {id_}",
        f"title: {title}",
        f"status: {status}",
        f"owners: [{', '.join(owners)}]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: TBD")
    if extra:
        for key, value in extra.items():
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def write_fake_graph_query_engine(repo_root, nodes, edges, lineage):
    module_dir = repo_root / "gen" / "graph-query-engine"
    module_dir.mkdir(parents=True, exist_ok=True)
    module_path = module_dir / "graph_query_engine.py"
    source = f'''
NODES = {nodes!r}
EDGES = {edges!r}
LINEAGE = {lineage!r}


def load_views(con, repo_root):
    con.execute(
        "CREATE OR REPLACE TABLE nodes "
        "(id VARCHAR, title VARCHAR, status VARCHAR, kind VARCHAR, owner_component_id VARCHAR)"
    )
    con.execute(
        "CREATE OR REPLACE TABLE edges "
        "(source_id VARCHAR, target_id VARCHAR, edge_type VARCHAR)"
    )
    con.execute(
        "CREATE OR REPLACE TABLE decision_lineage (id VARCHAR, last_ratified_commit VARCHAR)"
    )
    for row in NODES:
        con.execute("INSERT INTO nodes VALUES (?, ?, ?, ?, ?)", row)
    for row in EDGES:
        con.execute("INSERT INTO edges VALUES (?, ?, ?)", row)
    for row in LINEAGE:
        con.execute("INSERT INTO decision_lineage VALUES (?, ?)", row)
'''
    module_path.write_text(source)


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def commit_matches(actual, expected_full_hash):
    if not actual:
        return False
    return expected_full_hash == actual or expected_full_hash.startswith(actual)


def test_direct_superseder_identified_for_single_citation():
    import decision_drift_detector

    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        init_repo(repo_root)

        write(
            repo_root / "specs/components/foo/component.md",
            frontmatter(
                "comp-foo", "Foo", "ratified", ["lselfors"],
                extra={"sealed": "true", "source_path": "fake/foo.py"},
            ) + "\n# Foo\n\nFoo component.\n",
        )
        write(
            repo_root / "specs/components/foo/requirements/R-FOO-001.md",
            "The component MUST behave per D17.\n",
        )
        write(
            repo_root / "specs/components/foo/acceptance/AC-FOO-001.md",
            "Covers: R-FOO-001\n\nGiven the component\nWhen it runs\nThen it behaves\n",
        )
        write(
            repo_root / "specs/decisions/D17.md",
            frontmatter("D17", "Old decision", "ratified", ["lselfors"]),
        )
        commit1 = commit_all(repo_root, "initial corpus citing D17")

        write(
            repo_root / "specs/decisions/D17.md",
            frontmatter("D17", "Old decision", "deprecated", ["lselfors"]),
        )
        write(
            repo_root / "specs/decisions/D31.md",
            frontmatter(
                "D31", "New decision", "ratified", ["lselfors"],
                extra={"supersedes": "[D17]"},
            ),
        )
        commit2 = commit_all(repo_root, "deprecate D17, ratify D31")

        write_fake_graph_query_engine(
            repo_root,
            nodes=[
                ("D17", "Old decision", "deprecated", "decision", None),
                ("D31", "New decision", "ratified", "decision", None),
            ],
            edges=[("D31", "D17", "supersedes")],
            lineage=[("D17", commit1), ("D31", commit2)],
        )

        report = decision_drift_detector.find_decision_drift(repo_root)
        entries = field(report, "entries")

        assert len(entries) == 1
        entry = entries[0]
        assert field(entry, "file") == "specs/components/foo/requirements/R-FOO-001.md"
        assert field(entry, "cited_decision") == "D17"
        assert field(entry, "superseded_by") == "D31"
        assert commit_matches(field(entry, "file_commit"), commit1)
        assert commit_matches(field(entry, "superseder_ratified_commit"), commit2)


def test_later_ratified_superseder_wins_over_earlier_one():
    import decision_drift_detector

    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        init_repo(repo_root)

        write(
            repo_root / "specs/components/bar/component.md",
            frontmatter(
                "comp-bar", "Bar", "ratified", ["lselfors"],
                extra={"sealed": "true", "source_path": "fake/bar.py"},
            ) + "\n# Bar\n\nBar component.\n",
        )
        write(
            repo_root / "specs/components/bar/requirements/R-BAR-001.md",
            "The component MUST behave per D17.\n",
        )
        write(
            repo_root / "specs/components/bar/acceptance/AC-BAR-001.md",
            "Covers: R-BAR-001\n\nGiven the component\nWhen it runs\nThen it behaves\n",
        )
        write(
            repo_root / "specs/decisions/D17.md",
            frontmatter("D17", "Old decision", "ratified", ["lselfors"]),
        )
        commit1 = commit_all(repo_root, "initial corpus citing D17")

        write(
            repo_root / "specs/decisions/D17.md",
            frontmatter("D17", "Old decision", "deprecated", ["lselfors"]),
        )
        write(
            repo_root / "specs/decisions/D31.md",
            frontmatter(
                "D31", "First superseder", "ratified", ["lselfors"],
                extra={"supersedes": "[D17]"},
            ),
        )
        commit2 = commit_all(repo_root, "deprecate D17, ratify D31")

        write(
            repo_root / "specs/decisions/D32.md",
            frontmatter(
                "D32", "Second superseder", "ratified", ["lselfors"],
                extra={"supersedes": "[D17]"},
            ),
        )
        commit3 = commit_all(repo_root, "ratify D32 as descendant of D31's commit")

        write_fake_graph_query_engine(
            repo_root,
            nodes=[
                ("D17", "Old decision", "deprecated", "decision", None),
                ("D31", "First superseder", "ratified", "decision", None),
                ("D32", "Second superseder", "ratified", "decision", None),
            ],
            edges=[
                ("D31", "D17", "supersedes"),
                ("D32", "D17", "supersedes"),
            ],
            lineage=[("D17", commit1), ("D31", commit2), ("D32", commit3)],
        )

        report = decision_drift_detector.find_decision_drift(repo_root)
        entries = field(report, "entries")

        assert len(entries) == 1
        entry = entries[0]
        assert field(entry, "file") == "specs/components/bar/requirements/R-BAR-001.md"
        assert field(entry, "cited_decision") == "D17"
        assert field(entry, "superseded_by") == "D32"
        assert commit_matches(field(entry, "file_commit"), commit1)
        assert commit_matches(field(entry, "superseder_ratified_commit"), commit3)