# hotdocs-criterion: sha256:7fccb7715658bb347289070c23acdd562af10b08cafe19417aebba9419b97a9f
"""AC-GQE-005: component_provenance rows match each committed
verification/<component>/.provenance.json file's own JSON content exactly."""

import json
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _lines(*lines):
    return "\n".join(lines) + "\n"


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "components" / "foo" / "component.md",
        _lines(
            "---",
            "id: comp-foo",
            "title: Foo",
            "status: draft",
            "owners: [team]",
            "depends_on: [comp-bar]",
            "realizes: [P-X]",
            "uses_var: [VAR-X]",
            "depends_on_guarantees: [G-BAR-001]",
            "---",
            "",
            "# Foo",
            "",
            "one two three",
        ),
    )
    _write(
        specs / "components" / "bar" / "component.md",
        _lines(
            "---",
            "id: comp-bar",
            "title: Bar",
            "status: draft",
            "owners: [team]",
            "realizes: [P-X]",
            "---",
            "",
            "# Bar",
        ),
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        _lines("# R-FOO-001", "", "foo MUST work."),
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-002.md",
        _lines("# R-FOO-002", "", "foo MUST stop."),
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        _lines("# AC-FOO-001", "", "Covers: R-FOO-001", "Kind: generated-test"),
    )
    _write(
        specs / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        _lines("# G-FOO-001", "", "foo never fails."),
    )
    _write(
        specs / "product" / "x.md",
        _lines(
            "---",
            "id: P-X",
            "title: X",
            "status: draft",
            "owners: [team]",
            "---",
            "# X",
            "",
            "### CS-X-001",
            "Covers: P-X",
            "",
            "### CS-X-002",
            "Covers: P-X",
        ),
    )
    _write(
        specs / "vars" / "x.md",
        _lines(
            "---",
            "id: VAR-X",
            "title: V",
            "status: draft",
            "owners: [team]",
            "---",
            "# V",
        ),
    )
    _write(
        specs / "decisions" / "D1.md",
        _lines(
            "---",
            "id: D1",
            "title: One",
            "status: ratified",
            "owners: [team]",
            "last_ratified_commit: 0000000",
            "---",
            "# D1",
        ),
    )
    _write(
        specs / "decisions" / "D2.md",
        _lines(
            "---",
            "id: D2",
            "title: Two",
            "status: draft",
            "owners: [team]",
            "supersedes: D1",
            "builds_on: [D1]",
            "---",
            "# D2",
        ),
    )
    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", _lines("# Readme", "", "Notes."))


# Values deliberately avoid date/timestamp-looking strings so read_json's
# auto-detection keeps them as plain VARCHAR and compares exactly.
FOO_PROVENANCE = {
    "component_id_hint": "foo",
    "spec_bundle_hash": "abc123def456",
    "generator_model": "anthropic:example-model",
    "attempt_count": 2,
    "verification_report": {
        "result": "pass",
        "passed": 3,
        "failed": 0,
    },
    "license_scan": {
        "result": "pass",
        "findings": 0,
    },
    "secret_scan": {
        "result": "pass",
        "findings": 0,
    },
    "provenance_hit": False,
}

BAR_PROVENANCE = {
    "component_id_hint": "bar",
    "spec_bundle_hash": "fff000eee111",
    "generator_model": "anthropic:other-model",
    "attempt_count": 1,
    "verification_report": {
        "result": "fail",
        "passed": 1,
        "failed": 2,
    },
    "license_scan": {
        "result": "pass",
        "findings": 1,
    },
    "secret_scan": {
        "result": "fail",
        "findings": 4,
    },
    "provenance_hit": True,
}


def _connect(repo_root):
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment dependent
        con.close()
        pytest.skip("yaml community extension unavailable: " + repr(exc))
    graph_query_engine.load_views(con, repo_root)
    return con


def _rows_by_component(con):
    cur = con.execute("SELECT * FROM component_provenance")
    cols = [d[0] for d in cur.description]
    out = {}
    for row in cur.fetchall():
        rec = dict(zip(cols, row))
        out[rec["component_id"]] = rec
    return cols, out


def test_component_provenance_row_matches_committed_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    foo_file = repo_root / "verification" / "foo" / ".provenance.json"
    bar_file = repo_root / "verification" / "bar" / ".provenance.json"
    _write(foo_file, json.dumps(FOO_PROVENANCE, indent=2, sort_keys=True) + "\n")
    _write(bar_file, json.dumps(BAR_PROVENANCE, indent=2, sort_keys=True) + "\n")

    con = _connect(repo_root)
    try:
        cols, rows = _rows_by_component(con)
    finally:
        con.close()

    assert "component_id" in cols
    assert set(rows) == {"comp-foo", "comp-bar"}

    for comp_id, path in (("comp-foo", foo_file), ("comp-bar", bar_file)):
        with open(path, "r", encoding="utf-8") as fh:
            expected = json.load(fh)
        row = rows[comp_id]
        assert field(row, "component_id") == comp_id
        for key, value in expected.items():
            assert key in row, "missing column " + repr(key)
            assert field(row, key) == value, (
                "field " + repr(key) + " of " + repr(comp_id)
                + ": " + repr(field(row, key)) + " != " + repr(value)
            )
        extra = set(row) - set(expected) - {"component_id", "filename"}
        assert not extra, "unexpected columns " + repr(sorted(extra))


def test_component_provenance_single_component_row_matches_file(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    foo_file = repo_root / "verification" / "foo" / ".provenance.json"
    _write(foo_file, json.dumps(FOO_PROVENANCE) + "\n")

    con = _connect(repo_root)
    try:
        cols, rows = _rows_by_component(con)
    finally:
        con.close()

    assert list(rows) == ["comp-foo"]
    row = rows["comp-foo"]
    with open(foo_file, "r", encoding="utf-8") as fh:
        expected = json.load(fh)
    for key, value in expected.items():
        assert field(row, key) == value
    assert field(row, "spec_bundle_hash") == "abc123def456"
    assert field(row, "provenance_hit") is False
    assert field(row, "verification_report") == {
        "result": "pass",
        "passed": 3,
        "failed": 0,
    }