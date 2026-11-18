# hotdocs-criterion: sha256:c84a85f6271d974be40747434b792f66b58cb564d63c2ad1f66063ca721c8392
import json
import re
from collections import Counter
from pathlib import Path

import pytest

import graph_query_engine

duckdb = pytest.importorskip("duckdb")


FIVE_EDGE_TYPES = ("depends_on", "realizes", "uses_var", "depends_on_guarantees", "covers")
DECISION_EDGE_TYPES = ("supersedes", "builds_on")
ALL_EDGE_TYPES = FIVE_EDGE_TYPES + DECISION_EDGE_TYPES
COMPONENT_LIST_FIELDS = ("depends_on", "realizes", "uses_var", "depends_on_guarantees")


# ---------------------------------------------------------------------------
# Corpus location / synthetic fallback
# ---------------------------------------------------------------------------


def _looks_like_repo_root(p: Path) -> bool:
    return (
        (p / "specs" / "components").is_dir()
        and (p / "specs" / "decisions").is_dir()
        and (p / "specs" / "product").is_dir()
        and any((p / "specs" / "components").glob("*/component.md"))
    )


def _find_real_repo_root():
    starts = [Path(__file__).resolve().parent, Path.cwd().resolve()]
    seen = set()
    for start in starts:
        for cand in [start, *start.parents]:
            if cand in seen:
                continue
            seen.add(cand)
            if _looks_like_repo_root(cand):
                return cand
    return None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, depends_on, realizes, uses_var, dog, sealed):
    lines = [
        "---",
        f"id: comp-{slug}",
        f"title: {slug.capitalize()} Component",
        "status: draft",
        "owners: [team-a, team-b]",
        f"depends_on: [{', '.join(depends_on)}]",
        f"realizes: [{', '.join(realizes)}]",
        f"uses_var: [{', '.join(uses_var)}]",
        f"depends_on_guarantees: [{', '.join(dog)}]",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append(f"source_path: legacy/{slug}.py")
    lines.append("---")
    lines.append("")
    lines.append(f"# {slug.capitalize()} Component")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(f"The {slug} component does one small, well-defined thing.")
    lines.append("")
    return "\n".join(lines)


def _build_synthetic_corpus(root: Path) -> Path:
    comps = {
        "alpha": dict(
            depends_on=["comp-beta", "comp-gamma"],
            realizes=["P-ONE"],
            uses_var=["VAR-ALPHA-PATH"],
            dog=["G-BETA-001", "G-GAMMA-001"],
            sealed=False,
            reqs=["R-ALPHA-001", "R-ALPHA-002"],
        ),
        "beta": dict(
            depends_on=["comp-gamma"],
            realizes=["P-ONE", "P-TWO"],
            uses_var=[],
            dog=["G-GAMMA-001"],
            sealed=False,
            reqs=["R-BETA-001"],
        ),
        "gamma": dict(
            depends_on=[],
            realizes=[],
            uses_var=["VAR-ALPHA-PATH", "VAR-GAMMA-MODE"],
            dog=[],
            sealed=True,
            reqs=["R-GAMMA-001"],
        ),
    }
    for slug, c in comps.items():
        cdir = root / "specs" / "components" / slug
        _write(
            cdir / "component.md",
            _component_md(slug, c["depends_on"], c["realizes"], c["uses_var"], c["dog"], c["sealed"]),
        )
        _write(cdir / "constraints.md", "# Constraints\n\nNone beyond the defaults.\n")
        _write(
            cdir / "interface" / "library.md",
            f"# Library\n\n```\nrun_{slug}() -> None\n```\n\nRuns {slug}.\n",
        )
        _write(
            cdir / "interface" / f"G-{slug.upper()}-001.md",
            f"# G-{slug.upper()}-001\n\n**G-{slug.upper()}-001** — {slug} always returns.\n",
        )
        for i, rid in enumerate(c["reqs"], start=1):
            _write(
                cdir / "requirements" / f"{rid}.md",
                f"# {rid}\n\n**{rid}** — The {slug} component MUST do thing {i}.\n",
            )
            ac = rid.replace("R-", "AC-", 1)
            _write(
                cdir / "acceptance" / f"{ac}.md",
                f"# {ac}\n\nCovers: {rid}\nKind: generated-test\n\n"
                "```gherkin\nGiven something\nWhen it runs\nThen it works\n```\n",
            )
        _write(
            root / "gen" / slug / ".provenance.json",
            json.dumps(
                {
                    "component_id": f"comp-{slug}",
                    "spec_bundle_hash": "0" * 64,
                    "verification_report": {"passed": True},
                    "license_scan": {"passed": True},
                    "secret_scan": {"passed": True},
                    "provenance_hit": False,
                }
            ),
        )
        _write(root / "gen" / slug / f"{slug}.py", "def run():\n    return None\n")

    for var in ("VAR-ALPHA-PATH", "VAR-GAMMA-MODE"):
        _write(
            root / "specs" / "vars" / f"{var}.md",
            f"---\nid: {var}\ntitle: {var}\nstatus: draft\nowners: [team-a]\n---\n\n# {var}\n\nA var.\n",
        )

    _write(
        root / "specs" / "product" / "P-ONE.md",
        "---\nid: P-ONE\ntitle: Capability One\nstatus: draft\nowners: [team-a]\n---\n\n"
        "# Capability One\n\n## Scenarios\n\n"
        "### CS-ONE-001\nCovers: P-ONE\n\n```gherkin\nGiven a\nWhen b\nThen c\n```\n\n"
        "### CS-ONE-002\nCovers: P-ONE\n\n```gherkin\nGiven a\nWhen b\nThen c\n```\n",
    )
    _write(
        root / "specs" / "product" / "P-TWO.md",
        "---\nid: P-TWO\ntitle: Capability Two\nstatus: draft\nowners: [team-b]\n---\n\n"
        "# Capability Two\n\n## Scenarios\n\n"
        "### CS-TWO-001\nCovers: P-TWO\n\n```gherkin\nGiven a\nWhen b\nThen c\n```\n",
    )

    _write(
        root / "specs" / "decisions" / "D1.md",
        "---\nid: D1\ntitle: First decision\nstatus: ratified\nowners: [team-a]\n"
        "last_ratified_commit: abc1234\n---\n\n# D1\n\nThe first decision.\n",
    )
    _write(
        root / "specs" / "decisions" / "D2.md",
        "---\nid: D2\ntitle: Second decision\nstatus: draft\nowners: [team-a]\n"
        "supersedes: D1\nbuilds_on: [D1]\n---\n\n# D2\n\nReplaces D1.\n",
    )
    _write(
        root / "specs" / "decisions" / "D3.md",
        "---\nid: D3\ntitle: Third decision\nstatus: draft\nowners: [team-b]\n"
        "builds_on: [D1, D2]\n---\n\n# D3\n\n"
        "An earlier draft of this record wrote the following line verbatim:\n\n"
        "supersedes: D9\n\nbuilds_on: [D9]\n\nNeither is declared by this decision.\n",
    )
    _write(root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** — a thing.\n")
    return root


# ---------------------------------------------------------------------------
# Independent counting (plain Python over the files on disk)
# ---------------------------------------------------------------------------


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _frontmatter(text: str) -> str:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def _fm_id(fm: str) -> str:
    m = re.search(r"(?m)^id:\s*(\S+)", fm)
    return m.group(1) if m else ""


def _flow_list(fm: str, key: str):
    m = re.search(r"(?m)^" + re.escape(key) + r":[ \t]*\[([^\]]*)\]", fm)
    if not m:
        return []
    return [x.strip() for x in m.group(1).split(",") if x.strip() != ""]


def _independent_edges(repo_root: Path) -> Counter:
    expected = Counter()
    specs = repo_root / "specs"

    for comp_md in sorted(specs.glob("components/*/component.md")):
        fm = _frontmatter(_read(comp_md))
        src = _fm_id(fm)
        for key in COMPONENT_LIST_FIELDS:
            for target in _flow_list(fm, key):
                expected[(src, target, key)] += 1

    for ac in sorted(specs.glob("components/*/acceptance/*.md")):
        m = re.search(r"(AC-[A-Za-z0-9-]+)\.md$", ac.name)
        src = m.group(1) if m else ""
        cm = re.search(r"(?m)^Covers:\s*(\S+)", _read(ac))
        target = cm.group(1) if cm else ""
        expected[(src, target, "covers")] += 1

    cs_re = re.compile(r"### (CS-[A-Za-z0-9-]+)\s*\nCovers:\s*(\S+)")
    for prod in sorted(specs.glob("product/*.md")):
        for cs_id, target in cs_re.findall(_read(prod)):
            expected[(cs_id, target, "covers")] += 1

    for dec in sorted(specs.glob("decisions/*.md")):
        fm = _frontmatter(_read(dec))
        src = _fm_id(fm)
        sm = re.search(r"(?m)^supersedes:\s*(\S+)", fm)
        if sm and sm.group(1) != "":
            expected[(src, sm.group(1), "supersedes")] += 1
        for target in _flow_list(fm, "builds_on"):
            expected[(src, target, "builds_on")] += 1

    return expected


# ---------------------------------------------------------------------------
# Running the component under test
# ---------------------------------------------------------------------------


def _connect():
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # environment cannot provide the extension
        con.close()
        pytest.skip(f"DuckDB community 'yaml' extension unavailable: {exc}")
    return con


def _actual_edges(repo_root: Path) -> Counter:
    con = _connect()
    try:
        result = graph_query_engine.load_views(con, repo_root)
        assert result is None
        rows = con.execute("SELECT source_id, target_id, edge_type FROM edges").fetchall()
    finally:
        con.close()
    actual = Counter()
    for src, tgt, et in rows:
        actual[(src if src is not None else "", tgt if tgt is not None else "", et)] += 1
    return actual


def _per_type(counter: Counter) -> dict:
    out = {}
    for (_, _, et), n in counter.items():
        out[et] = out.get(et, 0) + n
    return out


def _assert_edges_match(repo_root: Path):
    expected = _independent_edges(repo_root)
    actual = _actual_edges(repo_root)

    unknown = sorted({et for (_, _, et) in actual} - set(ALL_EDGE_TYPES))
    assert not unknown, f"edges view produced unexpected edge_type values: {unknown}"

    exp_counts = _per_type(expected)
    act_counts = _per_type(actual)
    for et in FIVE_EDGE_TYPES:
        assert act_counts.get(et, 0) == exp_counts.get(et, 0), (
            f"edge_type {et!r}: edges view has {act_counts.get(et, 0)} rows, "
            f"independent frontmatter/Covers: count is {exp_counts.get(et, 0)}"
        )
    for et in DECISION_EDGE_TYPES:
        assert act_counts.get(et, 0) == exp_counts.get(et, 0), (
            f"edge_type {et!r}: edges view has {act_counts.get(et, 0)} rows, "
            f"independent decision-frontmatter count is {exp_counts.get(et, 0)}"
        )

    for et in ALL_EDGE_TYPES:
        exp_rows = Counter({k: v for k, v in expected.items() if k[2] == et})
        act_rows = Counter({k: v for k, v in actual.items() if k[2] == et})
        missing = exp_rows - act_rows
        extra = act_rows - exp_rows
        assert not missing and not extra, (
            f"edge_type {et!r} rows differ from the independent count; "
            f"missing={sorted(missing.elements())[:20]} extra={sorted(extra.elements())[:20]}"
        )
    return expected


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_edges_row_counts_match_independent_count_on_real_corpus(tmp_path):
    repo_root = _find_real_repo_root()
    if repo_root is None:
        repo_root = _build_synthetic_corpus(tmp_path / "repo")
    _assert_edges_match(repo_root)


def test_edges_row_counts_match_independent_count_on_synthetic_corpus(tmp_path):
    repo_root = _build_synthetic_corpus(tmp_path / "repo")
    expected = _assert_edges_match(repo_root)

    counts = _per_type(expected)
    # Sanity on the fixture itself: every one of the five edge types is exercised.
    assert counts.get("depends_on") == 3
    assert counts.get("realizes") == 3
    assert counts.get("uses_var") == 3
    assert counts.get("depends_on_guarantees") == 3
    # 4 acceptance files + 3 capability scenario headings
    assert counts.get("covers") == 7
    assert counts.get("supersedes") == 1
    assert counts.get("builds_on") == 3
    # Prose quoting a field never becomes an edge (frontmatter-only decision arms).
    assert ("D3", "D9", "supersedes") not in expected
    assert ("D3", "D9", "builds_on") not in expected