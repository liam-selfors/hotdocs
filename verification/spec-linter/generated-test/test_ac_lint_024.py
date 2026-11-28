# hotdocs-criterion: sha256:de09b7acc231284b56b09e4f5d9bc3453daebd2b85e925241d2fb573b541a898
"""AC-LINT-024: a component's Purpose section citing a decision id fails R-LINT-024;
the same citation moved to the Rationale section produces no R-LINT-024 finding."""

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


COMPONENT_MD = 'specs/components/foo/component.md'
CITATION_TEXT = 'extracted once D30 found a real coupling'


def _purpose_cites_decision():
    original = CLEAN_CORPUS[COMPONENT_MD]
    old = '## Purpose\n\nMakes a foo.\n'
    assert old in original
    new = '## Purpose\n\nMakes a foo, ' + CITATION_TEXT + '.\n'
    text = original.replace(old, new)
    assert CITATION_TEXT in text
    return text


def _rationale_cites_decision():
    original = CLEAN_CORPUS[COMPONENT_MD]
    old = '## Scope\n'
    assert old in original
    new = '## Rationale\n\nThis component was ' + CITATION_TEXT + '.\n\n## Scope\n'
    text = original.replace(old, new, 1)
    # Purpose itself stays free of any decision citation.
    purpose = text.split('## Purpose\n', 1)[1].split('## Rationale\n', 1)[0]
    assert 'D30' not in purpose
    assert CITATION_TEXT in text
    return text


def _lint024(report):
    return [f for f in field(report, 'findings') if field(f, 'rule_id') == 'R-LINT-024']


def test_purpose_with_decision_citation_fails_r_lint_024(tmp_path):
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    write_corpus(repo_root, {COMPONENT_MD: _purpose_cites_decision()})

    report = spec_linter.lint(None, repo_root)
    findings = _lint024(report)

    assert findings, 'expected an R-LINT-024 finding for a Purpose citing D30'
    for f in findings:
        assert field(f, 'severity') == 'fail'
        assert str(field(f, 'file')).replace('\\', '/').endswith(COMPONENT_MD)
    assert field(report, 'hard_failures') >= 1


def test_purpose_with_decision_citation_main_exits_1(tmp_path):
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    write_corpus(repo_root, {COMPONENT_MD: _purpose_cites_decision()})

    code = spec_linter.main(['--repo-root=' + str(repo_root)])
    assert code == 1


def test_citation_moved_to_rationale_gives_no_r_lint_024(tmp_path):
    repo_root = tmp_path / 'repo2'
    repo_root.mkdir()
    write_corpus(repo_root, {COMPONENT_MD: _rationale_cites_decision()})

    report = spec_linter.lint(None, repo_root)
    findings = _lint024(report)

    assert findings == [], 'unexpected R-LINT-024 findings: ' + repr(
        [field(f, 'message') for f in findings]
    )