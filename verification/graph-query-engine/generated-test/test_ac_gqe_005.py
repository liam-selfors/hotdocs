# hotdocs-criterion: sha256:56c7127b01d2251dfb7037b01dbc9105a7bfbd38e544422c1fcbd395b4d7089c
"""AC-GQE-005 (covers R-GQE-005).

Given a component with a committed verification/<component>/.provenance.json
When load_views runs and component_provenance is queried for it
Then the row's fields match that file's own JSON content exactly
"""

import datetime as _dt
import decimal
import json
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")
# R-GQE-005: any caller that queries component_provenance against real
# provenance data MUST have pytz installed (generated_at -> TIMESTAMPTZ).
pytest.importorskip("pytz")

import graph_query_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic spec-corpus fixture
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root: Path, slug: str, depends_on: str) -> None:
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} Component\n"
        "status: draft\n"
        "owners: [alice]\n"
        f"depends_on: {depends_on}\n"
        "uses_var: [VAR-DEMO]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}\n"
        "---\n"
        "\n"
        f"# {slug.capitalize()} Component\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"The {slug} component exists only as a synthetic test fixture.\n"
        "\n"
        "## Notes\n"
        "\n"
        "Nothing else to say.\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The {slug} component MUST exist.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        f"Given the {slug} component\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nnoop() -> None\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


def _build_corpus(repo_root: Path) -> None:
    _write_component(repo_root, "alpha", "[comp-beta]")
    _write_component(repo_root, "beta", "[]")

    _write(
        repo_root / "specs" / "product" / "P-DEMO.md",
        "---\n"
        "id: P-DEMO\n"
        "title: Demo Capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# Demo Capability\n"
        "\n"
        "A synthetic capability for this test fixture.\n",
    )
    _write(
        repo_root / "specs" / "vars" / "VAR-DEMO.md",
        "---\n"
        "id: VAR-DEMO\n"
        "title: Demo Var\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# Demo Var\n"
        "\n"
        "A synthetic var declaration.\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Demo Decision\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# D1 — Demo Decision\n"
        "\n"
        "A synthetic decision record.\n",
    )


ALPHA_MANIFEST = {
    "spec_bundle_hash": "sha256:" + "a1" * 32,
    "generated_at": "2026-03-04T05:06:07Z",
    "model": "anthropic:claude-sonnet-5",
    "generator_version": "1.2.3",
    "files": ["gen/alpha/alpha.py", "gen/alpha/helpers.py"],
    "verification_report": {
        "result": "pass",
        "criteria_total": 3,
        "criteria_passed": 3,
    },
    "license_scan": {"result": "pass", "findings": 0},
    "secret_scan": {"result": "pass", "findings": 0},
    "provenance_hit": False,
}

BETA_MANIFEST = {
    "spec_bundle_hash": "sha256:" + "b2" * 32,
    "generated_at": "2025-11-12T13:14:15Z",
    "model": "ollama:llama3.1:8b",
    "generator_version": "0.9.0",
    "files": ["gen/beta/beta.py"],
    "verification_report": {
        "result": "fail",
        "criteria_total": 5,
        "criteria_passed": 2,
    },
    "license_scan": {"result": "fail", "findings": 2},
    "secret_scan": {"result": "pass", "findings": 0},
    "provenance_hit": True,
}


def _write_manifest(repo_root: Path, slug: str, manifest: dict) -> None:
    _write(
        repo_root / "verification" / slug / ".provenance.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _parse_iso(value: str) -> _dt.datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = _dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def _assert_matches(actual, expected, where: str) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict), (
            f"{where}: expected a struct/dict, got {type(actual).__name__}: {actual!r}"
        )
        assert set(actual.keys()) == set(expected.keys()), (
            f"{where}: struct keys {sorted(actual.keys())} != "
            f"JSON keys {sorted(expected.keys())}"
        )
        for key, sub_expected in expected.items():
            _assert_matches(actual[key], sub_expected, f"{where}.{key}")
        return

    if isinstance(expected, list):
        assert isinstance(actual, (list, tuple)), (
            f"{where}: expected a list, got {type(actual).__name__}: {actual!r}"
        )
        assert len(actual) == len(expected), (
            f"{where}: list length {len(actual)} != {len(expected)}"
        )
        for i, (a, e) in enumerate(zip(actual, expected)):
            _assert_matches(a, e, f"{where}[{i}]")
        return

    if expected is None:
        assert actual is None, f"{where}: expected NULL, got {actual!r}"
        return

    if isinstance(expected, bool):
        assert isinstance(actual, bool), (
            f"{where}: expected a boolean, got {type(actual).__name__}: {actual!r}"
        )
        assert actual is expected, f"{where}: {actual!r} != {expected!r}"
        return

    if isinstance(expected, (int, float)):
        if isinstance(actual, decimal.Decimal):
            actual = float(actual)
        assert not isinstance(actual, bool), f"{where}: got boolean {actual!r}"
        assert isinstance(actual, (int, float)), (
            f"{where}: expected a number, got {type(actual).__name__}: {actual!r}"
        )
        assert actual == expected, f"{where}: {actual!r} != {expected!r}"
        return

    if isinstance(expected, str):
        if isinstance(actual, _dt.datetime):
            # read_json auto-detects ISO-8601 strings as TIMESTAMP(TZ);
            # the instant must be identical to the file's own value.
            actual_dt = actual
            if actual_dt.tzinfo is None:
                actual_dt = actual_dt.replace(tzinfo=_dt.timezone.utc)
            assert actual_dt == _parse_iso(expected), (
                f"{where}: {actual!r} != {expected!r}"
            )
            return
        if isinstance(actual, _dt.date):
            assert actual.isoformat() == expected, (
                f"{where}: {actual!r} != {expected!r}"
            )
            return
        assert actual == expected, f"{where}: {actual!r} != {expected!r}"
        return

    assert actual == expected, f"{where}: {actual!r} != {expected!r}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _build_corpus(root)
    _write_manifest(root, "alpha", ALPHA_MANIFEST)
    _write_manifest(root, "beta", BETA_MANIFEST)
    return root


@pytest.fixture
def con():
    connection = duckdb.connect()
    try:
        connection.execute("INSTALL yaml FROM community")
        connection.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment-dependent
        connection.close()
        pytest.skip(f"DuckDB community 'yaml' extension unavailable: {exc}")
    yield connection
    connection.close()


def _query_component(con, component_id: str):
    cursor = con.execute(
        "SELECT * FROM component_provenance WHERE component_id = ?",
        [component_id],
    )
    rows = cursor.fetchall()
    columns = [d[0] for d in cursor.description]
    return columns, rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slug, manifest",
    [("alpha", ALPHA_MANIFEST), ("beta", BETA_MANIFEST)],
)
def test_component_provenance_row_matches_manifest_json(con, repo_root, slug, manifest):
    graph_query_engine.load_views(con, repo_root)

    # Re-read the committed file itself, so the expectation is that file's
    # own content rather than the in-memory dict it was written from.
    manifest_path = repo_root / "verification" / slug / ".provenance.json"
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk == manifest

    columns, rows = _query_component(con, f"comp-{slug}")
    assert len(rows) == 1, (
        f"expected exactly one component_provenance row for comp-{slug}, got {len(rows)}"
    )
    row = dict(zip(columns, rows[0]))

    assert row.get("component_id") == f"comp-{slug}"

    for key, expected in on_disk.items():
        assert key in row, (
            f"component_provenance is missing passthrough field {key!r}; "
            f"columns present: {columns}"
        )
        _assert_matches(row[key], expected, f"comp-{slug}.{key}")


def test_component_provenance_has_one_row_per_component(con, repo_root):
    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT component_id FROM component_provenance ORDER BY component_id"
    ).fetchall()
    assert [r[0] for r in rows] == ["comp-alpha", "comp-beta"]


def test_component_provenance_rows_are_not_cross_contaminated(con, repo_root):
    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT component_id, spec_bundle_hash, provenance_hit "
        "FROM component_provenance ORDER BY component_id"
    ).fetchall()
    assert rows == [
        ("comp-alpha", ALPHA_MANIFEST["spec_bundle_hash"], False),
        ("comp-beta", BETA_MANIFEST["spec_bundle_hash"], True),
    ]