# hotdocs-criterion: sha256:c01b30487dd9a1c93447acbfa52f2db02f321adec7d89fbae0f742dae6236564
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_linter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id: str, title: str, source_path: str) -> str:
    return (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        f"source_path: {source_path}\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"The {title} component provides a small fixture behavior for testing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the fixture behavior.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


def _requirement(rid: str) -> str:
    return (
        f"# {rid}\n"
        "\n"
        f"**{rid}** — The component MUST return the fixture value when asked.\n"
    )


def _acceptance(acid: str, covers: str) -> str:
    return (
        f"# {acid}\n"
        "\n"
        f"Covers: {covers}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the component is available\n"
        "When it is asked for the fixture value\n"
        "Then it returns the fixture value\n"
        "```\n"
    )


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test artifact.\n",
    )

    # comp-foo: one requirement, no acceptance criterion covering it.
    foo = specs / "components" / "foo"
    _write(foo / "component.md", _component_md("comp-foo", "Foo", "legacy/foo"))
    _write(foo / "requirements" / "R-FOO-001.md", _requirement("R-FOO-001"))
    _write(foo / "constraints.md", "# Constraints\n\nNone.\n")

    # comp-bar: R-BAR-001 covered by AC-BAR-001; AC-BAR-002 covers a
    # nonexistent R-BAR-999.
    bar = specs / "components" / "bar"
    _write(bar / "component.md", _component_md("comp-bar", "Bar", "legacy/bar"))
    _write(bar / "requirements" / "R-BAR-001.md", _requirement("R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-001.md", _acceptance("AC-BAR-001", "R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-002.md", _acceptance("AC-BAR-002", "R-BAR-999"))
    _write(bar / "constraints.md", "# Constraints\n\nNone.\n")


def _findings(report):
    findings = _get(report, "findings", None)
    assert findings is not None, "LintReport has no findings field"
    return list(findings)


def _by_rule(findings, rule_id):
    return [f for f in findings if _get(f, "rule_id") == rule_id]


def _mentions(finding, ident: str) -> bool:
    file_ = str(_get(finding, "file", "") or "")
    message = str(_get(finding, "message", "") or "")
    return Path(file_).name == f"{ident}.md" or ident in message


def _describe(findings):
    return [
        (
            _get(f, "rule_id"),
            _get(f, "severity"),
            _get(f, "file"),
            _get(f, "line"),
            _get(f, "message"),
        )
        for f in findings
    ]


# ---------------------------------------------------------------------------
# Behavioral test: exactly the expected R-LINT-008 / R-LINT-009 findings
# ---------------------------------------------------------------------------


def test_only_expected_traceability_findings(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = _findings(report)

    lint008 = _by_rule(findings, "R-LINT-008")
    lint009 = _by_rule(findings, "R-LINT-009")

    # R-LINT-008: exactly one, fail-severity, for R-FOO-001.
    assert len(lint008) == 1, _describe(lint008)
    f008 = lint008[0]
    assert _get(f008, "severity") == "fail", _describe(lint008)
    assert _mentions(f008, "R-FOO-001"), _describe(lint008)
    assert not _mentions(f008, "R-BAR-001"), _describe(lint008)

    # R-LINT-009: exactly one, fail-severity, for AC-BAR-002.
    assert len(lint009) == 1, _describe(lint009)
    f009 = lint009[0]
    assert _get(f009, "severity") == "fail", _describe(lint009)
    assert _mentions(f009, "AC-BAR-002"), _describe(lint009)
    assert not _mentions(f009, "AC-BAR-001"), _describe(lint009)

    # The report's own hard-failure count reflects at least these two.
    hard = _get(report, "hard_failures", None)
    if hard is not None:
        assert hard >= 2


# ---------------------------------------------------------------------------
# Implementation test: R-LINT-008/009 are resolved via nodes/edges views.
#
# A fake graph-query-engine is placed under the fixture's own gen/ directory.
# It delegates to the real load_views (located under the tool root), then
# replaces the `edges` view with one that hides both of comp-bar's `covers`
# edges. A linter that queries `edges` must then:
#   - report R-LINT-008 for R-BAR-001 (no covering edge visible), and
#   - NOT report R-LINT-009 for AC-BAR-002 (its edge is no longer visible).
# Independently-written traversal over the files would do the opposite.
# ---------------------------------------------------------------------------


def _tool_root():
    here = Path(spec_linter.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _real_gqe_path():
    root = _tool_root()
    if root is None:
        return None
    base = root / "gen" / "graph-query-engine"
    flat = base / "graph_query_engine.py"
    if flat.is_file():
        return flat
    pkg = base / "graph_query_engine" / "__init__.py"
    if pkg.is_file():
        return pkg
    return None


_FAKE_GQE_TEMPLATE = '''
import importlib.util
import sys
from pathlib import Path

_REAL_PATH = {real_path!r}
_LOG_PATH = {log_path!r}
_REAL_NAME = "_ac_lint_021_real_graph_query_engine"


def _real():
    mod = sys.modules.get(_REAL_NAME)
    if mod is not None:
        return mod
    real = Path(_REAL_PATH)
    if real.name == "__init__.py":
        spec = importlib.util.spec_from_file_location(
            _REAL_NAME, str(real), submodule_search_locations=[str(real.parent)]
        )
    else:
        spec = importlib.util.spec_from_file_location(_REAL_NAME, str(real))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_REAL_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


def load_views(con, repo_root):
    _real().load_views(con, repo_root)
    con.execute(
        "CREATE OR REPLACE TABLE __ac_lint_021_edges AS SELECT * FROM edges"
    )
    try:
        con.execute("DROP VIEW edges")
    except Exception:
        con.execute("DROP TABLE edges")
    con.execute(
        "CREATE VIEW edges AS SELECT * FROM __ac_lint_021_edges "
        "WHERE NOT (edge_type = 'covers' "
        "AND source_id IN ('AC-BAR-001', 'AC-BAR-002'))"
    )
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write("load_views " + str(repo_root) + "\\n")
'''


def test_traceability_rules_query_edges_view(tmp_path):
    real = _real_gqe_path()
    if real is None:
        pytest.skip("real graph-query-engine not locatable under the tool root")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    log_path = tmp_path / "gqe_calls.log"
    fake_path = repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py"
    _write(
        fake_path,
        _FAKE_GQE_TEMPLATE.format(real_path=str(real), log_path=str(log_path)),
    )

    report = spec_linter.lint(None, repo_root)
    findings = _findings(report)

    assert log_path.is_file(), "fake graph-query-engine load_views was never invoked"
    assert "load_views" in log_path.read_text(encoding="utf-8")

    lint008 = _by_rule(findings, "R-LINT-008")
    lint009 = _by_rule(findings, "R-LINT-009")

    # With comp-bar's covers edges hidden from `edges`, R-BAR-001 has zero
    # covering edges in the edges view, so it must be reported too.
    assert any(
        _mentions(f, "R-FOO-001") and _get(f, "severity") == "fail" for f in lint008
    ), _describe(lint008)
    assert any(
        _mentions(f, "R-BAR-001") and _get(f, "severity") == "fail" for f in lint008
    ), _describe(lint008)

    # AC-BAR-002's dangling covers edge is no longer in `edges`, so a
    # query-based R-LINT-009 has nothing to report for it.
    assert not any(_mentions(f, "AC-BAR-002") for f in lint009), _describe(lint009)