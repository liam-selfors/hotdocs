import subprocess
from pathlib import Path


GQE_MODULE_SOURCE = '''\
import subprocess
from pathlib import Path


def _parse_frontmatter_text(text):
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    result = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            value = [item.strip() for item in inner.split(",")] if inner else []
        elif value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        result[key] = value
    return result


def _parse_frontmatter(path):
    return _parse_frontmatter_text(path.read_text())


def _last_ratified_commit(repo_root, path):
    rel = path.relative_to(repo_root)
    log = subprocess.run(
        ["git", "log", "--format=%H", "--reverse", "--", str(rel)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    commits = [c for c in log.stdout.strip().splitlines() if c]
    for commit in commits:
        show = subprocess.run(
            ["git", "show", "{}:{}".format(commit, rel)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if show.returncode != 0:
            continue
        frontmatter = _parse_frontmatter_text(show.stdout)
        if frontmatter.get("status") == "ratified":
            return commit
    return None


def load_views(con, repo_root):
    repo_root = Path(repo_root)

    with open(repo_root / ".gqe-invocations.log", "a") as log_file:
        log_file.write("load_views called\\n")

    decisions_dir = repo_root / "specs" / "decisions"
    edges_rows = []
    lineage_rows = []
    nodes_rows = []

    if decisions_dir.is_dir():
        for path in sorted(decisions_dir.glob("D*.md")):
            frontmatter = _parse_frontmatter(path)
            decision_id = frontmatter.get("id")
            if not decision_id:
                continue
            status = frontmatter.get("status")
            for target in frontmatter.get("supersedes") or []:
                edges_rows.append((decision_id, target, "supersedes"))
            for target in frontmatter.get("builds_on") or []:
                edges_rows.append((decision_id, target, "builds_on"))
            last_commit = _last_ratified_commit(repo_root, path)
            lineage_rows.append((decision_id, last_commit))
            nodes_rows.append(
                (decision_id, frontmatter.get("title"), status, "decision", None)
            )

    for view_name in (
        "edges",
        "decision_lineage",
        "nodes",
        "component_docs",
        "component_context",
        "component_provenance",
        "component_size",
    ):
        con.execute(f"DROP VIEW IF EXISTS {view_name}")
        con.execute(f"DROP TABLE IF EXISTS _{view_name}_data")

    con.execute(
        "CREATE TABLE _edges_data (source_id VARCHAR, target_id VARCHAR, edge_type VARCHAR)"
    )
    if edges_rows:
        con.executemany("INSERT INTO _edges_data VALUES (?, ?, ?)", edges_rows)
    con.execute("CREATE VIEW edges AS SELECT * FROM _edges_data")

    con.execute(
        "CREATE TABLE _decision_lineage_data (id VARCHAR, last_ratified_commit VARCHAR)"
    )
    if lineage_rows:
        con.executemany("INSERT INTO _decision_lineage_data VALUES (?, ?)", lineage_rows)
    con.execute("CREATE VIEW decision_lineage AS SELECT * FROM _decision_lineage_data")

    con.execute(
        "CREATE TABLE _nodes_data (id VARCHAR, title VARCHAR, status VARCHAR, "
        "kind VARCHAR, owner_component_id VARCHAR)"
    )
    if nodes_rows:
        con.executemany("INSERT INTO _nodes_data VALUES (?, ?, ?, ?, ?)", nodes_rows)
    con.execute("CREATE VIEW nodes AS SELECT * FROM _nodes_data")

    con.execute(
        "CREATE TABLE _component_docs_data (id VARCHAR, title VARCHAR, status VARCHAR, body VARCHAR)"
    )
    con.execute("CREATE VIEW component_docs AS SELECT * FROM _component_docs_data")

    con.execute("CREATE TABLE _component_context_data (component_id VARCHAR, purpose VARCHAR)")
    con.execute("CREATE VIEW component_context AS SELECT * FROM _component_context_data")

    con.execute(
        "CREATE TABLE _component_provenance_data (component_id VARCHAR, provenance_hit BOOLEAN)"
    )
    con.execute(
        "CREATE VIEW component_provenance AS SELECT * FROM _component_provenance_data"
    )

    con.execute("CREATE TABLE _component_size_data (component_id VARCHAR, word_count BIGINT)")
    con.execute("CREATE VIEW component_size AS SELECT * FROM _component_size_data")
'''


COMPONENT_MD_TEMPLATE = """\
---
id: comp-{slug}
title: {slug}
status: ratified
owners: [alice]
sealed: true
source_path: legacy/{slug}
last_ratified_commit: "0000000"
---

# {slug}

## Purpose

Synthetic fixture component for drift detection testing.
"""

D17_RATIFIED = """\
---
id: D17
title: Original decision
status: ratified
owners: [alice]
last_ratified_commit: "0000000"
---

# D17

Original decision text.
"""

D17_DEPRECATED = """\
---
id: D17
title: Original decision
status: deprecated
owners: [alice]
last_ratified_commit: "0000000"
---

# D17

Original decision text.
"""

D31_SUPERSEDES_D17 = """\
---
id: D31
title: Superseding decision D31
status: ratified
owners: [alice]
supersedes: [D17]
last_ratified_commit: "0000000"
---

# D31

Supersedes D17.
"""

D32_SUPERSEDES_D17 = """\
---
id: D32
title: Superseding decision D32
status: ratified
owners: [alice]
supersedes: [D17]
last_ratified_commit: "0000000"
---

# D32

Supersedes D17.
"""


def _run_git(repo_root, *args):
    result = subprocess.run(
        ["git", *args], cwd=str(repo_root), capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _init_repo(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)
    _run_git(repo_root, "init", "-q")
    _run_git(repo_root, "config", "user.email", "test@example.com")
    _run_git(repo_root, "config", "user.name", "Test")


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _commit_all(repo_root, message):
    _run_git(repo_root, "add", "-A")
    _run_git(repo_root, "commit", "-q", "-m", message)
    return _run_git(repo_root, "rev-parse", "HEAD")


def _install_fake_graph_query_engine(repo_root):
    dep_dir = repo_root / "gen" / "graph-query-engine"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "graph_query_engine.py").write_text(GQE_MODULE_SOURCE)


def _dual_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _setup_repo_with_d17_citation(repo_root, component_slug, req_id, ac_id):
    _init_repo(repo_root)
    _install_fake_graph_query_engine(repo_root)

    component_dir = repo_root / "specs" / "components" / component_slug
    _write(
        component_dir / "component.md",
        COMPONENT_MD_TEMPLATE.format(slug=component_slug),
    )
    _write(
        component_dir / "requirements" / f"{req_id}.md",
        f"# {req_id}\n\nThis requirement follows decision D17.\n",
    )
    _write(
        component_dir / "acceptance" / f"{ac_id}.md",
        f"# {ac_id}\n\nCovers: {req_id}\n",
    )
    _write(repo_root / "specs" / "decisions" / "D17.md", D17_RATIFIED)

    _commit_all(repo_root, "initial: add component citing D17")

    return f"specs/components/{component_slug}/requirements/{req_id}.md"


import decision_drift_detector


def test_single_superseder_recorded_as_superseded_by(tmp_path):
    repo_root = tmp_path / "repo"
    rel_path = _setup_repo_with_d17_citation(repo_root, "foo", "R-FOO-001", "AC-FOO-001")

    _write(repo_root / "specs" / "decisions" / "D17.md", D17_DEPRECATED)
    _write(repo_root / "specs" / "decisions" / "D31.md", D31_SUPERSEDES_D17)
    _commit_all(repo_root, "deprecate D17, ratify D31 as its superseder")

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = _dual_get(report, "entries", [])

    matching = [e for e in entries if _dual_get(e, "file") == rel_path]

    assert len(matching) == 1
    entry = matching[0]
    assert _dual_get(entry, "cited_decision") == "D17"
    assert _dual_get(entry, "superseded_by") == "D31"

    invocation_log = repo_root / ".gqe-invocations.log"
    assert invocation_log.exists()
    assert invocation_log.read_text().strip() != ""


def test_multiple_superseders_picks_latest_ratified(tmp_path):
    repo_root = tmp_path / "repo"
    rel_path = _setup_repo_with_d17_citation(repo_root, "foo2", "R-FOO2-001", "AC-FOO2-001")

    _write(repo_root / "specs" / "decisions" / "D17.md", D17_DEPRECATED)
    _write(repo_root / "specs" / "decisions" / "D31.md", D31_SUPERSEDES_D17)
    _commit_all(repo_root, "deprecate D17, ratify D31 as a superseder")

    _write(repo_root / "specs" / "decisions" / "D32.md", D32_SUPERSEDES_D17)
    _commit_all(repo_root, "ratify D32, a later superseder of D17")

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = _dual_get(report, "entries", [])

    matching = [e for e in entries if _dual_get(e, "file") == rel_path]

    assert len(matching) == 1
    entry = matching[0]
    assert _dual_get(entry, "cited_decision") == "D17"
    assert _dual_get(entry, "superseded_by") == "D32"