"""Shared fixtures for graph-query-engine's test suite.

Deliberately tests against this repository's own real spec corpus, not
a synthetic fixture — these views exist specifically to query the real
corpus, and a synthetic fixture would validate nothing about whether
the SQL actually runs against real, organically-authored content
(the same lesson spec-linter's own BOOTSTRAP.md already draws from a
real bug a complete fixture suite failed to catch).
"""

import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "graph-query-engine"))
import graph_query_engine  # noqa: E402


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute("INSTALL yaml FROM community")
    c.execute("LOAD yaml")
    graph_query_engine.load_views(c, REPO_ROOT)
    return c
