# hotdocs-criterion: sha256:b8adea489fa2e0507ac4bebc62e197f8e4c210860da2b5ac64f0fbfe20fcef0e
"""AC-GQE-005: component_provenance rows match each committed .provenance.json exactly."""

import datetime
import importlib.util
import json
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _frontmatter(lines):
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n"


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        _frontmatter(
            [
                "id: comp-foo",
                "title: Foo",
                "status: draft",
                "owners: [team]",
                "depends_on: [comp-bar]",
                "realizes: [P-X]",
                "uses_var: [VAR-X]",
                "depends_on_guarantees: [G-BAR-001]",
            ]
        )
        + "\n# Foo\n\none two three\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        _frontmatter(
            [
                "id: comp-bar",
                "title: Bar",
                "status: draft",
                "owners: [team]",
                "realizes: [P-X]",
            ]
        )
        + "\n# Bar\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\nfoo MUST work.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\nfoo MUST stop.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        repo_root
        / "specs"
        / "components"
        / "foo"
        / "interface"
        / "guarantees"
        / "G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        repo_root / "specs" / "product" / "x.md",
        _frontmatter(["id: P-X", "title: X", "status: draft", "owners: [team]"])
        + "# X\n\n### CS-X-001\nCovers: P-X\n\n### CS-X-002\nCovers: P-X\n",
    )
    _write(
        repo_root / "specs" / "vars" / "x.md",
        _frontmatter(["id: VAR-X", "title: V", "status: draft", "owners: [team]"])
        + "# V\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        _frontmatter(
            [
                "id: D1",
                "title: One",
                "status: ratified",
                "owners: [team]",
                "last_ratified_commit: 0000000",
            ]
        )
        + "# D1\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D2.md",
        _frontmatter(
            [
                "id: D2",
                "title: Two",
                "status: draft",
                "owners: [team]",
                "supersedes: D1",
                "builds_on: [D1]",
            ]
        )
        + "# D2\n",
    )
    for sub in ("product", "vars", "decisions"):
        _write(repo_root / "specs" / sub / "README.md", "# Readme\n\nNotes.\n")


def _have_pytz() -> bool:
    return importlib.util.find_spec("pytz") is not None


def _manifest(slug: str, hit: bool, hash_suffix: str, include_generated_at: bool):
    manifest = {
        "spec_bundle_hash": "sha256-" + hash_suffix * 16,
        "generator_model": "anthropic:claude-sonnet-5",
        "generator_tool_version": "tool-v" + slug,
        "attempt_count": 2 if hit else 1,
        "verification_report": {
            "passed": True,
            "summary": "all gates passed for " + slug,
            "criteria": [
                {"criterion_id": "AC-" + slug.upper() + "-001", "result": "pass"},
            ],
        },
        "license_scan": {"passed": True, "findings_count": 0},
        "secret_scan": {"passed": hit, "findings_count": 0 if hit else 1},
        "provenance_hit": hit,
    }
    if include_generated_at:
        manifest["generated_at"] = "2026-01-02T03:04:05Z"
    return manifest


def _normalize(value):
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc)
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value


def _expected(key, value):
    if key == "generated_at" and isinstance(value, str):
        return datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
    return value


def _equal(key, actual, expected):
    actual = _normalize(actual)
    if key == "generated_at" and isinstance(actual, str):
        return actual == expected
    return actual == _normalize(_expected(key, expected))


def test_component_provenance_rows_match_their_own_json_files(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    include_generated_at = _have_pytz()
    manifests = {
        "foo": _manifest("foo", True, "a1", include_generated_at),
        "bar": _manifest("bar", False, "b2", include_generated_at),
    }
    for slug, manifest in manifests.items():
        _write(
            repo_root / "verification" / slug / ".provenance.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        for slug, manifest in manifests.items():
            # Re-read the file's own JSON content as the source of truth.
            on_disk = json.loads(
                (repo_root / "verification" / slug / ".provenance.json").read_text(
                    encoding="utf-8"
                )
            )
            assert on_disk == manifest

            cur = con.execute(
                "SELECT * FROM component_provenance WHERE component_id = ?",
                ["comp-" + slug],
            )
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
            assert len(rows) == 1, (slug, rows)
            row = dict(zip(columns, rows[0]))

            assert row["component_id"] == "comp-" + slug

            missing = set(on_disk) - set(columns)
            assert not missing, ("columns missing from view", slug, missing)
            extra = set(columns) - set(on_disk) - {"component_id", "filename"}
            assert not extra, ("unexpected columns in view", slug, extra)

            for key, expected in on_disk.items():
                assert _equal(key, row[key], expected), (
                    slug,
                    key,
                    row[key],
                    expected,
                )

        total = con.execute("SELECT count(*) FROM component_provenance").fetchone()[0]
        assert total == len(manifests)
    finally:
        con.close()