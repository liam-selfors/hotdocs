# hotdocs-criterion: sha256:492a45cc57147e2e55921eaaa00f96bf06f0183408c9805a6fe18bf402c0c9c2
import json
from pathlib import Path

import duckdb

import graph_query_engine


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "depends_on: [comp-bar]\n"
        + "realizes: [P-X]\n"
        + "uses_var: [VAR-X]\n"
        + "depends_on_guarantees: [G-BAR-001]\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "one two three\n",
    )
    write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        "---\n"
        + "id: comp-bar\n"
        + "title: Bar\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "realizes: [P-X]\n"
        + "---\n"
        + "\n"
        + "# Bar\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n" + "\n" + "foo MUST work.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n" + "\n" + "foo MUST stop.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n" + "\n" + "Covers: R-FOO-001\n" + "Kind: generated-test\n",
    )
    write(
        repo_root
        / "specs"
        / "components"
        / "foo"
        / "interface"
        / "guarantees"
        / "G-FOO-001.md",
        "# G-FOO-001\n" + "\n" + "foo never fails.\n",
    )
    write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        + "id: P-X\n"
        + "title: X\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "# X\n"
        + "### CS-X-001\n"
        + "Covers: P-X\n"
        + "### CS-X-002\n"
        + "Covers: P-X\n",
    )
    write(
        repo_root / "specs" / "vars" / "x.md",
        "---\n"
        + "id: VAR-X\n"
        + "title: V\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "# V\n",
    )
    write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        + "id: D1\n"
        + "title: One\n"
        + "status: ratified\n"
        + "owners: [team]\n"
        + "last_ratified_commit: 0000000\n"
        + "---\n"
        + "# D1\n",
    )
    write(
        repo_root / "specs" / "decisions" / "D2.md",
        "---\n"
        + "id: D2\n"
        + "title: Two\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "supersedes: D1\n"
        + "builds_on: [D1]\n"
        + "---\n"
        + "# D2\n",
    )
    for sub in ("product", "vars", "decisions"):
        write(repo_root / "specs" / sub / "README.md", "# Readme\n" + "\n" + "Notes.\n")


# Deliberately avoids an ISO-8601 `generated_at` value so that read_json's
# auto-detection never infers TIMESTAMP WITH TIME ZONE (which would require
# pytz to materialize); every value here round-trips through DuckDB to the
# identical Python value.
PROVENANCE = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256-abcdef0123456789",
    "model": "anthropic:claude-sonnet-5",
    "generator_version": "gen-v-one",
    "verification_report": {
        "passed": True,
        "criteria_total": 3,
        "criteria_passed": 3,
        "summary": "all good",
    },
    "license_scan": {
        "passed": True,
        "findings_count": 0,
    },
    "secret_scan": {
        "passed": False,
        "findings_count": 2,
    },
    "provenance_hit": True,
}


def test_component_provenance_row_matches_provenance_json_exactly(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    prov_path = repo_root / "verification" / "foo" / ".provenance.json"
    write(prov_path, json.dumps(PROVENANCE, indent=2) + "\n")
    expected = json.loads(prov_path.read_text(encoding="utf-8"))

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        cur = con.execute(
            "SELECT * FROM component_provenance WHERE component_id = ?",
            ["comp-foo"],
        )
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()

    assert len(rows) == 1, "expected exactly one component_provenance row for comp-foo, got " + repr(rows)
    row = dict(zip(columns, rows[0]))

    assert field(row, "component_id") == "comp-foo"

    for key, value in expected.items():
        assert key in row, "column " + repr(key) + " missing from component_provenance; columns: " + repr(columns)
        assert field(row, key) == value, (
            "field " + repr(key) + " mismatch: view=" + repr(field(row, key)) + " file=" + repr(value)
        )

    # Struct-valued fields come back with exactly the file's own keys, no more, no fewer.
    for key in ("verification_report", "license_scan", "secret_scan"):
        got = field(row, key)
        assert isinstance(got, dict), "expected STRUCT for " + repr(key) + ", got " + repr(got)
        assert set(got.keys()) == set(expected[key].keys())

    assert field(row, "provenance_hit") is True