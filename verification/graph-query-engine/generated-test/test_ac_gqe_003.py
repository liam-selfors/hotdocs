"""AC-GQE-003: component_docs returns one row per real component, carrying
that component's own frontmatter fields and its full raw text as `body`."""

import glob
import os
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


KNOWN_COMPONENT_ID = "comp-graph-query-engine"


def _tool_root():
    here = Path(graph_query_engine.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _component_files(repo_root):
    return sorted(
        glob.glob(os.path.join(str(repo_root), "specs", "components", "*", "component.md"))
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_synthetic_corpus(root):
    """Fallback corpus, used only when the tool's own corpus can't be located."""
    for slug, title in (("alpha-widget", "Alpha Widget"), ("beta-gadget", "Beta Gadget")):
        cdir = root / "specs" / "components" / slug
        _write(
            cdir / "component.md",
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {title}\n"
            "status: draft\n"
            "owners: [test-team]\n"
            "depends_on: []\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            "---\n"
            "\n"
            f"# {title}\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"Distinctive body prose for {slug} unique-marker-{slug}.\n",
        )
        _write(cdir / "constraints.md", "# Constraints\n\nNone.\n")
        tag = slug.split("-")[0].upper()
        _write(
            cdir / "requirements" / f"R-{tag}-001.md",
            f"# R-{tag}-001\n\n**R-{tag}-001** — It MUST work.\n",
        )
        _write(
            cdir / "acceptance" / f"AC-{tag}-001.md",
            f"# AC-{tag}-001\n\nCovers: R-{tag}-001\nKind: generated-test\n\n"
            "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
        )
    return root


def _parse_frontmatter(text):
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "component.md must start with frontmatter"
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


@pytest.fixture
def repo_root(tmp_path):
    root = _tool_root()
    if root is not None and _component_files(root):
        return root
    return _build_synthetic_corpus(tmp_path / "repo")


@pytest.fixture
def con():
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    yield connection
    connection.close()


def _rows(con, sql, params=None):
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def test_component_docs_one_row_per_component_with_frontmatter_and_body(con, repo_root):
    files = _component_files(repo_root)
    assert files, "fixture corpus must contain at least one component"
    expected_count = len(files)

    graph_query_engine.load_views(con, Path(repo_root))

    count = con.execute("SELECT count(*) FROM component_docs").fetchone()[0]
    assert count == expected_count

    distinct_ids = con.execute("SELECT count(DISTINCT id) FROM component_docs").fetchone()[0]
    assert distinct_ids == expected_count

    # Pick a known component: this component itself if present, else the first one.
    by_id = {}
    for path in files:
        with open(path, encoding="utf-8", newline="") as fh:
            raw = fh.read()
        fm = _parse_frontmatter(raw)
        by_id[fm["id"]] = (fm, raw)
    known_id = KNOWN_COMPONENT_ID if KNOWN_COMPONENT_ID in by_id else sorted(by_id)[0]
    fm, raw = by_id[known_id]

    rows = _rows(con, "SELECT * FROM component_docs WHERE id = ?", [known_id])
    assert len(rows) == 1, f"expected exactly one component_docs row for {known_id}"
    row = rows[0]

    # Its own frontmatter fields are present.
    for col in ("id", "title", "status", "body"):
        assert col in row, f"component_docs missing column {col!r}"
    assert str(row["id"]) == fm["id"]
    assert str(row["title"]) == fm["title"]
    assert str(row["status"]) == fm["status"]

    # Its body is the full raw text, frontmatter included.
    body = row["body"]
    assert isinstance(body, str)
    assert body == raw
    assert body.startswith("---")
    assert f"id: {fm['id']}" in body
    body_after_fm = raw.split("---", 2)[2].strip()
    assert body_after_fm and body_after_fm in body