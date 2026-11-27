# hotdocs-criterion: sha256:6a5a35477dffc689628482d4d2a050856410f8adcaea46a2ce194826b8d36107
"""AC-LINT-021: R-LINT-008 / R-LINT-009 resolved over nodes/edges views."""

import spec_linter


CLEAN_CORPUS = {
    'specs/product/foo.md': (
        '---\n'
        'id: P-FOO\n'
        'title: Foo works\n'
        'status: draft\n'
        'owners: [team-a]\n'
        '---\n'
        '\n'
        '# Foo works\n'
        '\n'
        '## Purpose\n'
        '\n'
        'A foo can be made.\n'
        '\n'
        '### CS-FOO-001\n'
        'Covers: P-FOO\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When a foo is made\n'
        'Then it exists\n'
        '```\n'
    ),
    'specs/components/foo/component.md': (
        '---\n'
        'id: comp-foo\n'
        'title: Foo\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: []\n'
        'realizes: [P-FOO]\n'
        'sealed: false\n'
        '---\n'
        '\n'
        '# Foo\n'
        '\n'
        '## Purpose\n'
        '\n'
        'Makes a foo.\n'
        '\n'
        '## Scope\n'
        '\n'
        '**In scope:** making a foo. **Out of scope:** everything else.\n'
        '\n'
        '## Definitions\n'
        '\n'
        'No deltas from `specs/glossary.md`.\n'
        '\n'
        '## Behavior\n'
        '\n'
        'See `requirements/`.\n'
        '\n'
        '## Interfaces\n'
        '\n'
        'See `interface/`.\n'
        '\n'
        '## Data\n'
        '\n'
        'None.\n'
        '\n'
        '## Acceptance criteria\n'
        '\n'
        'See `acceptance/`.\n'
        '\n'
        '## Non-functional constraints\n'
        '\n'
        'See `constraints.md`.\n'
        '\n'
        '## Open questions\n'
        '\n'
        'None.\n'
        '\n'
        '## Change log\n'
        '\n'
        '- Initial draft.\n'
    ),
    'specs/components/foo/requirements/R-FOO-001.md': (
        '# R-FOO-001\n'
        '\n'
        '**R-FOO-001** — `make_foo()` MUST return the string `"foo"`.\n'
    ),
    'specs/components/foo/interface/library.md': (
        '# Library\n'
        '\n'
        'One module file, `foo.py`.\n'
        '\n'
        '```\n'
        'make_foo() -> str\n'
        '```\n'
    ),
    'specs/components/foo/acceptance/AC-FOO-001.md': (
        '# AC-FOO-001\n'
        '\n'
        'Covers: R-FOO-001\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When make_foo() is called\n'
        'Then the result is "foo"\n'
        '```\n'
    ),
    'specs/components/foo/constraints.md': (
        '# Foo — Non-Functional Constraints\n'
        '\n'
        '- **Pure.** No I/O.\n'
    ),
}


def write_corpus(repo_root, changes=None):
    files = {**CLEAN_CORPUS, **(changes or {})}
    for rel, text in files.items():
        if text is not None:
            path = repo_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BAR_COMPONENT = (
    '---\n'
    'id: comp-bar\n'
    'title: Bar\n'
    'status: draft\n'
    'owners: [team-a]\n'
    'depends_on: []\n'
    'sealed: true\n'
    'source_path: legacy/bar/\n'
    '---\n'
    '\n'
    '# Bar\n'
    '\n'
    '## Purpose\n'
    '\n'
    'Makes a bar.\n'
    '\n'
    '## Scope\n'
    '\n'
    '**In scope:** making a bar. **Out of scope:** everything else.\n'
    '\n'
    '## Definitions\n'
    '\n'
    'No deltas from `specs/glossary.md`.\n'
    '\n'
    '## Behavior\n'
    '\n'
    'See `requirements/`.\n'
    '\n'
    '## Interfaces\n'
    '\n'
    'See `interface/`.\n'
    '\n'
    '## Data\n'
    '\n'
    'None.\n'
    '\n'
    '## Acceptance criteria\n'
    '\n'
    'See `acceptance/`.\n'
    '\n'
    '## Non-functional constraints\n'
    '\n'
    'See `constraints.md`.\n'
    '\n'
    '## Open questions\n'
    '\n'
    'None.\n'
    '\n'
    '## Change log\n'
    '\n'
    '- Initial draft.\n'
)

CHANGES = {
    # comp-foo: R-FOO-001 left with no covering acceptance file.
    'specs/components/foo/acceptance/AC-FOO-001.md': None,
    # comp-bar: one requirement, covered by AC-BAR-001; AC-BAR-002 dangles.
    'specs/components/bar/component.md': BAR_COMPONENT,
    'specs/components/bar/requirements/R-BAR-001.md': (
        '# R-BAR-001\n'
        '\n'
        '**R-BAR-001** — `make_bar()` MUST return the string `"bar"`.\n'
    ),
    'specs/components/bar/interface/library.md': (
        '# Library\n'
        '\n'
        'One module file, `bar.py`.\n'
        '\n'
        '```\n'
        'make_bar() -> str\n'
        '```\n'
    ),
    'specs/components/bar/acceptance/AC-BAR-001.md': (
        '# AC-BAR-001\n'
        '\n'
        'Covers: R-BAR-001\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When make_bar() is called\n'
        'Then the result is "bar"\n'
        '```\n'
    ),
    'specs/components/bar/acceptance/AC-BAR-002.md': (
        '# AC-BAR-002\n'
        '\n'
        'Covers: R-BAR-999\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When make_bar() is called twice\n'
        'Then both results are "bar"\n'
        '```\n'
    ),
    'specs/components/bar/constraints.md': (
        '# Bar — Non-Functional Constraints\n'
        '\n'
        '- **Pure.** No I/O.\n'
    ),
}


def _mentions(finding, ident):
    file_ = field(finding, "file") or ""
    message = field(finding, "message") or ""
    return ident in str(file_) or ident in str(message)


def test_traceability_findings_resolved_via_nodes_edges(tmp_path):
    write_corpus(tmp_path, CHANGES)

    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))

    trace = [
        f for f in findings
        if field(f, "rule_id") in ("R-LINT-008", "R-LINT-009")
    ]
    r008 = [f for f in trace if field(f, "rule_id") == "R-LINT-008"]
    r009 = [f for f in trace if field(f, "rule_id") == "R-LINT-009"]

    assert len(trace) == 2, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in trace
    ]
    assert len(r008) == 1, r008
    assert len(r009) == 1, r009

    f8 = r008[0]
    assert field(f8, "severity") == "fail"
    assert _mentions(f8, "R-FOO-001")
    assert not _mentions(f8, "R-BAR-001")

    f9 = r009[0]
    assert field(f9, "severity") == "fail"
    assert _mentions(f9, "AC-BAR-002")
    assert not _mentions(f9, "AC-BAR-001")

    assert field(report, "hard_failures") >= 2

    # The findings agree with the shared nodes/edges views of the same corpus.
    corpus = spec_linter.load_corpus(tmp_path)
    con = field(corpus, "graph")

    req_nodes = {
        row[0] for row in con.execute(
            "SELECT id FROM nodes WHERE kind = 'requirement'"
        ).fetchall()
    }
    assert "R-FOO-001" in req_nodes
    assert "R-BAR-001" in req_nodes
    assert "R-BAR-999" not in req_nodes

    foo_cover_count = con.execute(
        "SELECT count(*) FROM edges "
        "WHERE edge_type = 'covers' AND target_id = 'R-FOO-001'"
    ).fetchone()[0]
    assert foo_cover_count == 0

    bar_cover_count = con.execute(
        "SELECT count(*) FROM edges "
        "WHERE edge_type = 'covers' AND target_id = 'R-BAR-001'"
    ).fetchone()[0]
    assert bar_cover_count >= 1

    dangling = con.execute(
        "SELECT e.source_id FROM edges e "
        "WHERE e.edge_type = 'covers' AND NOT EXISTS ("
        "  SELECT 1 FROM nodes n WHERE n.id = e.target_id "
        "  AND n.kind IN ('requirement', 'capability'))"
    ).fetchall()
    assert {row[0] for row in dangling} == {"AC-BAR-002"}