import json
from datetime import datetime
from pathlib import Path

import pytest

import graph_query_engine


duckdb = pytest.importorskip("duckdb")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_component(repo_root: Path, slug: str, title: str) -> None:
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{title} does one small synthetic thing for testing.\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n",
    )
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — {title} MUST do its thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it does its thing\n"
        "```\n",
    )
    _write(
        base / "interface" / "library.md",
        f"# Library\n\n```\ndo_thing() -> None\n```\n\n{title}'s one function.\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _build_corpus(repo_root: Path) -> None:
    _make_component(repo_root, "foo", "Foo")
    _make_component(repo_root, "bar", "Bar")
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# D1\n\nA synthetic decision.\n",
    )
    _write(
        repo_root / "specs" / "vars" / "VAR-FOO.md",
        "---\n"
        "id: VAR-FOO\n"
        "title: Foo var\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# VAR-FOO\n\nA synthetic var.\n",
    )
    _write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# P-FOO\n\nA synthetic capability.\n",
    )
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a thing.\n")


def _provenance(bundle_hash: str, model: str, when: str, passed: bool, hit: bool, crit: str):
    return {
        "spec_bundle_hash": bundle_hash,
        "generator_model": model,
        "generated_at": when,
        "verification_report": {
            "passed": passed,
            "criteria_count": 3,
            "passed_criteria": [crit, crit + "-extra"],
        },
        "license_scan": {"status": "clean", "finding_count": 0},
        "secret_scan": {"status": "clean", "finding_count": 0},
        "provenance_hit": hit,
    }


def _parse_iso(value: str):
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _assert_matches(expected, actual, where):
    if isinstance(expected, dict):
        if isinstance(actual, str):
            actual = json.loads(actual)
        assert isinstance(actual, dict), f"{where}: expected dict, got {actual!r}"
        assert set(actual.keys()) == set(expected.keys()), (
            f"{where}: keys {sorted(actual.keys())} != {sorted(expected.keys())}"
        )
        for k, v in expected.items():
            _assert_matches(v, actual[k], f"{where}.{k}")
    elif isinstance(expected, list):
        if isinstance(actual, str):
            actual = json.loads(actual)
        assert isinstance(actual, (list, tuple)), f"{where}: expected list, got {actual!r}"
        assert len(actual) == len(expected), f"{where}: length mismatch {actual!r}"
        for i, (e, a) in enumerate(zip(expected, actual)):
            _assert_matches(e, a, f"{where}[{i}]")
    elif isinstance(expected, bool):
        assert isinstance(actual, bool), f"{where}: expected bool, got {actual!r}"
        assert actual is expected, f"{where}: {actual!r} != {expected!r}"
    elif isinstance(expected, str) and isinstance(actual, datetime):
        exp_dt = _parse_iso(expected)
        assert actual.tzinfo is not None, f"{where}: timestamp lost its timezone"
        assert actual == exp_dt, f"{where}: {actual!r} != {expected!r}"
    else:
        assert actual == expected, f"{where}: {actual!r} != {expected!r}"
        assert type(actual) is type(expected) or (
            isinstance(expected, (int, float)) and isinstance(actual, (int, float))
        ), f"{where}: type {type(actual)} != {type(expected)}"


@pytest.fixture
def connection():
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # environment cannot provide the required extension
        con.close()
        pytest.skip(f"yaml community extension unavailable: {exc}")
    yield con
    con.close()


def test_component_provenance_row_matches_committed_provenance_json(tmp_path, connection):
    # Materializing generated_at (TIMESTAMP WITH TIME ZONE) requires pytz (R-GQE-005).
    pytest.importorskip("pytz")

    repo_root = tmp_path
    _build_corpus(repo_root)

    foo_manifest = _provenance(
        "sha256:ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56abcd",
        "anthropic:claude-sonnet-5",
        "2026-03-04T05:06:07Z",
        True,
        False,
        "AC-FOO-001",
    )
    bar_manifest = _provenance(
        "sha256:ff00ee11dd22cc33bb44aa55ff00ee11dd22cc33bb44aa55ff00ee11dd22ffee",
        "ollama:llama3.1:8b",
        "2025-12-31T23:59:58Z",
        False,
        True,
        "AC-BAR-001",
    )
    foo_path = repo_root / "verification" / "foo" / ".provenance.json"
    bar_path = repo_root / "verification" / "bar" / ".provenance.json"
    _write(foo_path, json.dumps(foo_manifest, indent=2) + "\n")
    _write(bar_path, json.dumps(bar_manifest, indent=2) + "\n")

    graph_query_engine.load_views(connection, repo_root)

    for comp_id, path in (("comp-foo", foo_path), ("comp-bar", bar_path)):
        # The file's own JSON content, as committed on disk.
        expected = json.loads(path.read_text(encoding="utf-8"))

        cur = connection.execute(
            "SELECT * FROM component_provenance WHERE component_id = ?", [comp_id]
        )
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]

        assert len(rows) == 1, f"expected exactly one row for {comp_id}, got {rows!r}"
        row = dict(zip(columns, rows[0]))

        assert row["component_id"] == comp_id

        if "filename" in row:
            assert str(row["filename"]).replace("\\", "/").endswith(
                f"verification/{comp_id[len('comp-'):]}/.provenance.json"
            )

        passthrough = {k: v for k, v in row.items() if k not in ("component_id", "filename")}
        assert set(passthrough.keys()) == set(expected.keys()), (
            f"{comp_id}: view columns {sorted(passthrough.keys())} != "
            f"file keys {sorted(expected.keys())}"
        )
        for key, value in expected.items():
            _assert_matches(value, passthrough[key], f"{comp_id}.{key}")