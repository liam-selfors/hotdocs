# hotdocs-criterion: sha256:f125617776b2b2e25367bc302215a0718b17087f81a72571a6df80060fb9eda6
import os
import re
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

import graph_query_engine


KNOWN_SLUG = "graph-query-engine"
KNOWN_ID = "comp-graph-query-engine"


def _find_repo_root():
    candidates = []
    env_root = os.environ.get("HOTDOCS_REPO_ROOT") or os.environ.get("REPO_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    here = Path(__file__).resolve()
    candidates.extend(here.parents)
    cwd = Path.cwd().resolve()
    candidates.append(cwd)
    candidates.extend(cwd.parents)
    seen = set()
    for c in candidates:
        try:
            c = c.resolve()
        except Exception:
            continue
        if c in seen:
            continue
        seen.add(c)
        comp_dir = c / "specs" / "components"
        if comp_dir.is_dir() and (comp_dir / KNOWN_SLUG / "component.md").is_file():
            return c
    return None


def _split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1:])
    return None, text


def _parse_frontmatter(text):
    fm_lines, rest = _split_frontmatter(text)
    fields = {}
    if fm_lines is None:
        return fields, rest
    for line in fm_lines:
        if not line or line[0].isspace():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        fields[key] = value
    return fields, rest


def _connect():
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment dependent
        con.close()
        pytest.skip("yaml community extension unavailable: %r" % (exc,))
    return con


def _rows(con, sql, params=None):
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return cols, [dict(zip(cols, r)) for r in cur.fetchall()]


@pytest.fixture(scope="module")
def repo_root():
    root = _find_repo_root()
    if root is None:
        pytest.skip("could not locate a real spec corpus repo root")
    return root


@pytest.fixture(scope="module")
def loaded_con(repo_root):
    con = _connect()
    result = graph_query_engine.load_views(con, repo_root)
    assert result is None
    yield con
    con.close()


def _real_component_files(repo_root):
    return sorted(
        p for p in (repo_root / "specs" / "components").glob("*/component.md")
        if p.is_file()
    )


def test_component_docs_row_count_equals_real_component_count(repo_root, loaded_con):
    files = _real_component_files(repo_root)
    assert len(files) > 0
    count = loaded_con.execute("SELECT count(*) FROM component_docs").fetchone()[0]
    assert count == len(files)


def test_component_docs_one_row_per_component_id(repo_root, loaded_con):
    expected_ids = []
    for p in _real_component_files(repo_root):
        fields, _ = _parse_frontmatter(p.read_text(encoding="utf-8"))
        expected_ids.append(fields.get("id"))
    assert all(expected_ids)
    _, rows = _rows(loaded_con, "SELECT id FROM component_docs")
    actual_ids = [str(r["id"]) for r in rows]
    assert sorted(actual_ids) == sorted(expected_ids)
    assert len(set(actual_ids)) == len(actual_ids)


def test_known_component_frontmatter_and_body_present(repo_root, loaded_con):
    path = repo_root / "specs" / "components" / KNOWN_SLUG / "component.md"
    raw = path.read_text(encoding="utf-8")
    fields, rest = _parse_frontmatter(raw)
    assert fields.get("id") == KNOWN_ID

    cols, rows = _rows(
        loaded_con, "SELECT * FROM component_docs WHERE id = ?", [KNOWN_ID]
    )
    assert len(rows) == 1
    row = rows[0]

    for required in ("id", "title", "status", "body"):
        assert required in cols, "missing column %r in %r" % (required, cols)

    # Every top-level frontmatter key of the known component is passed through.
    for key in fields:
        assert key in cols, "frontmatter field %r not a column in %r" % (key, cols)

    # Scalar frontmatter fields match the file's own values.
    assert str(row["id"]) == KNOWN_ID
    if "title" in fields and fields["title"]:
        assert row["title"] is not None
        assert str(row["title"]).strip() == fields["title"].strip()
    if "status" in fields and fields["status"]:
        assert row["status"] is not None
        assert str(row["status"]).strip() == fields["status"].strip()

    # Body is the full raw text, frontmatter included.
    body = row["body"]
    assert isinstance(body, str)
    assert body.lstrip().startswith("---")
    norm_body = body.replace("\r\n", "\n")
    norm_raw = raw.replace("\r\n", "\n")
    assert norm_body.strip() == norm_raw.strip()
    fm_lines, _ = _split_frontmatter(raw)
    for line in fm_lines or []:
        if line.strip():
            assert line.rstrip() in norm_body
    rest_stripped = rest.replace("\r\n", "\n").strip()
    if rest_stripped:
        assert rest_stripped in norm_body