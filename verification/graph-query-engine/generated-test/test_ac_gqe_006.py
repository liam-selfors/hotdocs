# hotdocs-criterion: sha256:1578c35608b5190eaa3ee81899730c9a00a63d43311201415e6320ea7b29986c
"""AC-GQE-006 (covers R-GQE-006).

Given a repo root with a real spec corpus
When load_views runs and component_size is queried
Then every component's word_count matches spec-linter's own
  previously-verified component_doc_words value exactly.

The expected values are computed independently of the component under
test, from the data contract in R-GQE-006 / SPEC_GUIDELINES.md section 4:
every *.md doc under a component's directory (recursively, including
component.md), with a leading `---\\n...\\n---\\n` frontmatter block
stripped (DOTALL), split on RE2 `\\s+` whitespace ([\\t\\n\\f\\r ]), with
empty tokens dropped. One synthetic fixture also carries hand-verified
literal counts for a deliberately tricky component.
"""

import json
import re
import sys
from pathlib import Path

import pytest

import graph_query_engine


_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.S)
# RE2's \s is exactly [\t\n\f\r ] -- mirror it rather than Python's broader \s.
_RE2_WS_RE = re.compile(r"[\t\n\f\r ]+")


def _doc_words(text):
    stripped = _FRONTMATTER_RE.sub("", text, count=1)
    stripped = stripped.strip(" ")  # DuckDB trim(): spaces only
    return sum(1 for tok in _RE2_WS_RE.split(stripped) if tok != "")


def _is_hidden(path, base):
    try:
        rel = path.relative_to(base)
    except ValueError:
        return False
    return any(part.startswith(".") for part in rel.parts)


def _expected_sizes(repo_root):
    comps_dir = Path(repo_root) / "specs" / "components"
    expected = {}
    for comp_dir in sorted(p for p in comps_dir.iterdir() if p.is_dir()):
        if comp_dir.name.startswith("."):
            continue
        total = 0
        found = False
        for md in sorted(comp_dir.rglob("*.md")):
            if not md.is_file() or _is_hidden(md, comp_dir):
                continue
            found = True
            total += _doc_words(md.read_bytes().decode("utf-8"))
        if found:
            expected[comp_dir.name] = total
    return expected


def _connect():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment dependent
        try:
            con.execute("LOAD yaml")
        except Exception:
            con.close()
            pytest.skip(f"duckdb community 'yaml' extension unavailable: {exc!r}")
    return con


def _query_component_size(con):
    rows = con.execute(
        "SELECT component_id, word_count FROM component_size"
    ).fetchall()
    ids = [r[0] for r in rows]
    assert len(ids) == len(set(ids)), f"component_size has duplicate component rows: {ids}"
    return {r[0]: r[1] for r in rows}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _build_fixture(root):
    specs = root / "specs"

    _write(
        specs / "glossary.md",
        "---\nid: glossary\ntitle: Glossary\nstatus: draft\nowners: [alice]\n---\n# Glossary\n\n- **Thing** -- a thing.\n",
    )

    # Product capability
    _write(
        specs / "product" / "P-FIXTURE.md",
        "---\nid: P-FIXTURE\ntitle: Fixture Capability\nstatus: draft\nowners: [alice]\n---\n"
        "# Fixture Capability\n\n## Scenarios\n\n### CS-FIXTURE-001\n\nCovers: P-FIXTURE\n\n"
        "```gherkin\nGiven a fixture\nWhen it runs\nThen it works\n```\n",
    )

    # Var
    _write(
        specs / "vars" / "VAR-FIXTURE.md",
        "---\nid: VAR-FIXTURE\ntitle: Fixture Var\nstatus: draft\nowners: [alice]\n---\n"
        "# VAR-FIXTURE\n\nA fixture variable.\n",
    )

    # Decisions
    _write(
        specs / "decisions" / "D1.md",
        "---\nid: D1\ntitle: First Decision\nstatus: ratified\nowners: [alice]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "supersedes: []\nbuilds_on: []\n---\n# D1\n\nA first decision.\n",
    )
    _write(
        specs / "decisions" / "D2.md",
        "---\nid: D2\ntitle: Second Decision\nstatus: draft\nowners: [bob]\n"
        "supersedes: [D1]\nbuilds_on: [D1]\n---\n# D2\n\nA second decision.\n",
    )

    # Component alpha
    alpha = specs / "components" / "alpha"
    _write(
        alpha / "component.md",
        "---\nid: comp-alpha\ntitle: Alpha\nstatus: draft\nowners: [alice, bob]\n"
        "sealed: true\nsource_path: legacy/alpha\n"
        "depends_on: []\nrealizes: [P-FIXTURE]\nuses_var: [VAR-FIXTURE]\n"
        "depends_on_guarantees: []\n---\n"
        "# Alpha\n\n## Purpose\n\nAlpha does alpha things for its dependents.\n\n"
        "## Guarantees\n\n- **G-ALPHA-001** -- alpha always answers.\n",
    )
    _write(
        alpha / "requirements" / "R-ALPHA-001.md",
        "# R-ALPHA-001\n\n**R-ALPHA-001** -- Alpha MUST answer every request.\n",
    )
    _write(
        alpha / "requirements" / "R-ALPHA-002.md",
        "# R-ALPHA-002\n\n**R-ALPHA-002** -- Alpha MUST NOT\tcrash\n\n\n",
    )
    _write(
        alpha / "acceptance" / "AC-ALPHA-001.md",
        "# AC-ALPHA-001\n\nCovers: R-ALPHA-001\nKind: generated-test\n\n"
        "```gherkin\nGiven alpha\nWhen asked\nThen it answers\n```\n",
    )
    _write(
        alpha / "acceptance" / "AC-ALPHA-002.md",
        "# AC-ALPHA-002\n\nCovers: R-ALPHA-002\nKind: generated-test\n\n"
        "```gherkin\nGiven alpha\nWhen stressed\nThen it does not crash\n```\n",
    )
    _write(alpha / "interface" / "library.md", "# Library\n\n```\nanswer() -> str\n```\n")
    _write(alpha / "constraints.md", "# Constraints\n\n- No network access.\n")

    # Component beta
    beta = specs / "components" / "beta"
    _write(
        beta / "component.md",
        "---\nid: comp-beta\ntitle: Beta\nstatus: draft\nowners: [bob]\n"
        "sealed: true\nsource_path: legacy/beta\n"
        "depends_on: [comp-alpha]\nrealizes: [P-FIXTURE]\nuses_var: [VAR-FIXTURE]\n"
        "depends_on_guarantees: [G-ALPHA-001]\n---\n"
        "# Beta\n\n## Purpose\n\nBeta builds on alpha.\n",
    )
    _write(
        beta / "requirements" / "R-BETA-001.md",
        "# R-BETA-001\n\n**R-BETA-001** -- Beta MUST call alpha.\n",
    )
    _write(
        beta / "acceptance" / "AC-BETA-001.md",
        "# AC-BETA-001\n\nCovers: R-BETA-001\nKind: generated-test\n\n"
        "```gherkin\nGiven beta\nWhen run\nThen alpha is called\n```\n",
    )
    _write(beta / "interface" / "library.md", "# Library\n\n```\nrun() -> None\n```\n")
    _write(beta / "interface" / "data" / "BetaRecord.md", "# BetaRecord\n\n```\nname  TEXT\n```\n")

    # Component gamma: hand-verified tricky cases (total = 31 words)
    gamma = specs / "components" / "gamma"
    # Body after frontmatter: "# Gamma ## Purpose One two three." -> 7 words.
    # Multi-line frontmatter exercises the DOTALL ('s') flag.
    _write(
        gamma / "component.md",
        "---\nid: comp-gamma\ntitle: Gamma\nstatus: draft\nowners: [alice]\n"
        "sealed: true\nsource_path: legacy/gamma\n"
        "depends_on: [comp-alpha]\nrealizes: []\nuses_var: []\n"
        "depends_on_guarantees: []\n---\n"
        "# Gamma\n\n## Purpose\n\nOne two three.\n",
    )
    # 6 words; the em-dash is not whitespace.
    _write(
        gamma / "requirements" / "R-GAMMA-001.md",
        "**R-GAMMA-001** \u2014 The thing MUST work.\n",
    )
    # 6 words; multiple trailing newlines must not add tokens.
    _write(
        gamma / "acceptance" / "AC-GAMMA-001.md",
        "# AC-GAMMA-001\n\nCovers: R-GAMMA-001\nKind: generated-test\n\n\n",
    )
    # 4 words; leading spaces, tabs, trailing spaces.
    _write(gamma / "interface" / "library.md", "  leading\tspaces and\ttabs  \n")
    # 3 words; nested two levels deep, no trailing newline.
    _write(gamma / "interface" / "data" / "Thing.md", "nested doc words")
    # 5 words; '---' lines not at file start are NOT frontmatter.
    _write(gamma / "constraints.md", "Alpha ---\nbeta\n---\ngamma\n")

    # Provenance manifests for every component (read by component_provenance).
    for slug in ("alpha", "beta", "gamma"):
        manifest = {
            "component_id": f"comp-{slug}",
            "spec_bundle_hash": "0" * 64,
            "model": "anthropic:claude-fixture",
            "generated_at": "2026-01-01T00:00:00Z",
            "verification_report": {"result": "pass", "criteria": 1},
            "license_scan": {"result": "pass", "findings": 0},
            "secret_scan": {"result": "pass", "findings": 0},
            "provenance_hit": False,
        }
        _write(root / "gen" / slug / ".provenance.json", json.dumps(manifest, indent=2) + "\n")
        _write(root / "gen" / slug / f"{slug}.py", "def placeholder():\n    return None\n")

    _write(
        root / "SPEC_GUIDELINES.md",
        "# Spec Guidelines\n\nFixture placeholder.\n",
    )
    return root


GAMMA_HAND_VERIFIED_WORDS = 7 + 6 + 6 + 4 + 3 + 5  # 31


def test_component_size_matches_component_doc_words_on_fixture_corpus(tmp_path):
    repo_root = _build_fixture(tmp_path / "repo")
    expected = _expected_sizes(repo_root)

    # Sanity: the independent reference itself agrees with the hand count.
    assert expected["gamma"] == GAMMA_HAND_VERIFIED_WORDS

    con = _connect()
    try:
        result = graph_query_engine.load_views(con, repo_root)
        assert result is None
        actual = _query_component_size(con)
    finally:
        con.close()

    # One row per component, keyed by bare slug (no comp- prefix).
    assert set(actual) == {"alpha", "beta", "gamma"}, actual
    for cid in actual:
        assert not str(cid).startswith("comp-"), cid

    for cid, words in expected.items():
        assert actual[cid] is not None, f"{cid}: word_count is NULL"
        assert int(actual[cid]) == words, (
            f"{cid}: component_size.word_count={actual[cid]} != component_doc_words={words}"
        )

    assert int(actual["gamma"]) == GAMMA_HAND_VERIFIED_WORDS


def _find_real_repo_root():
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        comps = candidate / "specs" / "components"
        if comps.is_dir() and (candidate / "SPEC_GUIDELINES.md").is_file():
            if any(p.is_dir() for p in comps.iterdir()):
                return candidate
    return None


def test_component_size_matches_component_doc_words_on_real_corpus():
    repo_root = _find_real_repo_root()
    if repo_root is None:
        pytest.skip("no real spec corpus found above this test file")

    expected = _expected_sizes(repo_root)
    assert expected, "real corpus has no component docs"

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)
        actual = _query_component_size(con)
    finally:
        con.close()

    assert set(actual) == set(expected), (
        f"component set mismatch: only in view={sorted(set(actual) - set(expected))}, "
        f"only in corpus={sorted(set(expected) - set(actual))}"
    )
    mismatches = {
        cid: (actual[cid], words)
        for cid, words in expected.items()
        if actual[cid] is None or int(actual[cid]) != words
    }
    assert not mismatches, f"(view word_count, component_doc_words) mismatches: {mismatches}"