import json
import tempfile
from pathlib import Path

import duckdb

import graph_query_engine


def _field(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _assert_matches(actual, expected, path):
    if isinstance(expected, dict):
        for key, expected_value in expected.items():
            actual_value = _field(actual, key)
            _assert_matches(actual_value, expected_value, f"{path}.{key}")
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"


def test_component_provenance_matches_committed_provenance_json_exactly():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        comp_dir = repo_root / "verification" / "sample-comp"
        comp_dir.mkdir(parents=True)

        provenance_content = {
            "spec_bundle_hash": "deadbeef1234567890",
            "verification_report": {
                "status": "pass",
                "gate_count": 5,
            },
            "license_scan": {
                "status": "pass",
                "violation_count": 0,
            },
            "secret_scan": {
                "status": "pass",
                "finding_count": 0,
            },
            "provenance_hit": True,
        }

        provenance_path = comp_dir / ".provenance.json"
        provenance_path.write_text(json.dumps(provenance_content))

        con = duckdb.connect(":memory:")
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)

        columns = [
            "component_id",
            "spec_bundle_hash",
            "verification_report",
            "license_scan",
            "secret_scan",
            "provenance_hit",
        ]
        rows = con.execute(
            "SELECT {} FROM component_provenance".format(", ".join(columns))
        ).fetchall()

        assert len(rows) == 1
        row = dict(zip(columns, rows[0]))

        assert row["component_id"] == "comp-sample-comp"

        for key, expected_value in provenance_content.items():
            _assert_matches(row[key], expected_value, key)