"""AC-GQE-006: component_size's word_count matches spec-linter's own
component_doc_words value (R-SIZE-001) exactly, for every component of a
real spec corpus.

The expected per-component value is computed here independently, in plain
Python, from R-SIZE-001's own definition as restated by R-GQE-006: every
``*.md`` doc at any depth under ``specs/components/<slug>/``, a leading
YAML frontmatter block (``---\\n ... \\n---\\n``) stripped, split on
whitespace, and empty tokens dropped. Whitespace is RE2's ``\\s`` exactly
(``[\\t\\n\\f\\r ]``), which is what DuckDB's ``regexp_split_to_array``
uses.
"""

import os
import re
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


# RE2's \s class (DuckDB's regex engine): [\t\n\f\r ], no \v and no Unicode spaces.
_RE2_WHITESPACE = re.compile(r"[\t\n\f\r ]+")
# Same frontmatter pattern as the view, with DOTALL ('s' flag), first match
# only, anchored at the start of the text.
_FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.S)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root() -> Path:
    here = Path(graph_query_engine.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    for parent in here.parents:
        if (parent / "specs" / "components").is_dir():
            return parent
    pytest.skip("no real spec corpus found above the module under test")


def _doc_words(text: str) -> int:
    stripped = _FRONTMATTER.sub("", text, count=1)
    stripped = stripped.strip(" ")
    return len([tok for tok in _RE2_WHITESPACE.split(stripped) if tok != ""])


def _expected_component_doc_words(repo_root: Path) -> dict:
    """component slug -> summed word count, over specs/components/*/**/*.md."""
    components_dir = repo_root / "specs" / "components"
    expected = {}
    for comp_dir in sorted(components_dir.iterdir()):
        if not comp_dir.is_dir() or comp_dir.name.startswith("."):
            continue
        total = 0
        found_any = False
        for dirpath, dirnames, filenames in os.walk(comp_dir):
            # Glob matching does not descend into hidden directories.
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith(".") or not name.endswith(".md"):
                    continue
                path = Path(dirpath) / name
                if not path.is_file():
                    continue
                found_any = True
                total += _doc_words(path.read_bytes().decode("utf-8"))
        if found_any:
            expected[comp_dir.name] = total
    return expected


@pytest.fixture
def repo_root() -> Path:
    root = _tool_root()
    if not (root / "specs" / "components").is_dir():
        pytest.skip(f"{root} carries no specs/components/ corpus")
    return root


@pytest.fixture
def con():
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    try:
        yield connection
    finally:
        connection.close()


def test_component_size_word_count_matches_component_doc_words(con, repo_root):
    expected = _expected_component_doc_words(repo_root)
    assert expected, "real spec corpus has no component docs to measure"

    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT component_id, word_count FROM component_size ORDER BY component_id"
    ).fetchall()

    ids = [row[0] for row in rows]
    # One row per component.
    assert len(ids) == len(set(ids)), f"duplicate component rows: {ids}"

    # Bare slugs, never comp- prefixed.
    for component_id in ids:
        assert component_id is not None
        assert not component_id.startswith("comp-"), component_id

    actual = {}
    for component_id, word_count in rows:
        assert word_count is not None, component_id
        assert int(word_count) == word_count
        actual[component_id] = int(word_count)

    assert set(actual) == set(expected), (
        f"missing: {sorted(set(expected) - set(actual))}; "
        f"unexpected: {sorted(set(actual) - set(expected))}"
    )

    mismatches = {
        cid: (actual[cid], expected[cid])
        for cid in expected
        if actual[cid] != expected[cid]
    }
    assert not mismatches, (
        "component_size.word_count != component_doc_words (actual, expected): "
        f"{mismatches}"
    )


def test_component_size_counts_each_file_without_trailing_newline_token(
    con, repo_root
):
    """Every component's count is exact: an off-by-one per file (the spurious
    trailing empty token from each file's trailing newline) would surface as
    word_count exceeding the independent count by the component's file count."""
    expected = _expected_component_doc_words(repo_root)
    graph_query_engine.load_views(con, repo_root)

    rows = con.execute("SELECT component_id, word_count FROM component_size").fetchall()
    actual = {row[0]: int(row[1]) for row in rows}

    over = {cid: actual[cid] - expected[cid] for cid in expected
            if cid in actual and actual[cid] > expected[cid]}
    assert not over, f"word_count over-counts component_doc_words by: {over}"