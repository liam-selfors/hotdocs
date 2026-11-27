# hotdocs-criterion: sha256:2dc412cdc5a8e01ac6a2d269d06c70aaa7f5497c5542aa554c996f1f3b0a97b8
"""AC-LINT-038 — R-LINT-004: the corpus-wide depends_on graph has no cycles;
a cycle's finding names every node on it."""

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


def arch_doc(doc_id, depends_on):
    return (
        '---\n'
        'id: ' + doc_id + '\n'
        'title: Architecture ' + doc_id + '\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: [' + ', '.join(depends_on) + ']\n'
        '---\n'
        '\n'
        '# Architecture ' + doc_id + '\n'
        '\n'
        '## Purpose\n'
        '\n'
        'An architecture document.\n'
    )


def r004(report):
    return [f for f in field(report, "findings")
            if field(f, "rule_id") == "R-LINT-004"]


def test_cycle_between_arch_a_and_arch_b_reported_once(tmp_path):
    write_corpus(tmp_path, {
        'specs/architecture/arch-a.md': arch_doc('arch-a', ['arch-b']),
        'specs/architecture/arch-b.md': arch_doc('arch-b', ['arch-a']),
        'specs/architecture/arch-c.md': arch_doc('arch-c', ['arch-a']),
    })
    report = spec_linter.lint(None, tmp_path)
    fails = [f for f in r004(report) if field(f, "severity") == "fail"]
    assert len(fails) == 1, [field(f, "message") for f in r004(report)]
    message = field(fails[0], "message")
    assert "arch-a" in message
    assert "arch-b" in message
    assert "arch-c" not in message


def test_acyclic_chain_gives_no_r_lint_004(tmp_path):
    write_corpus(tmp_path, {
        'specs/architecture/arch-a.md': arch_doc('arch-a', []),
        'specs/architecture/arch-c.md': arch_doc('arch-c', ['arch-a']),
    })
    report = spec_linter.lint(None, tmp_path)
    assert r004(report) == [], [field(f, "message") for f in r004(report)]