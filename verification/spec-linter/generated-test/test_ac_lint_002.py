# hotdocs-criterion: sha256:4c871c3ebcc2c8093e7780a8007ff5e65d0328f1b599d63a35e64d5af847c9c0
import json

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


COMPONENT = 'specs/components/foo/component.md'


def _ratified_component(open_questions_body):
    text = CLEAN_CORPUS[COMPONENT]
    text = text.replace(
        'status: draft\n',
        'status: ratified\nlast_ratified_commit: 0000000\n',
        1,
    )
    old = '## Open questions\n\nNone.\n\n## Change log\n'
    assert old in text
    new = '## Open questions\n\n' + open_questions_body + '## Change log\n'
    return text.replace(old, new, 1)


def _lint_002_fails(findings):
    return [
        f for f in findings
        if field(f, 'rule_id') == 'R-LINT-002'
        and field(f, 'severity') == 'fail'
    ]


def test_ratified_with_open_questions_fails_r_lint_002(tmp_path):
    write_corpus(tmp_path, {
        COMPONENT: _ratified_component(
            '- Should a foo also be able to make a bar?\n\n'
        ),
    })
    report = spec_linter.lint(None, tmp_path)
    hits = _lint_002_fails(field(report, 'findings'))
    assert hits, [
        (field(f, 'rule_id'), field(f, 'severity'), field(f, 'message'))
        for f in field(report, 'findings')
    ]
    assert any(
        str(field(f, 'file')).replace('\\', '/').endswith(COMPONENT)
        for f in hits
    )
    assert field(report, 'hard_failures') >= 1


def test_cli_reports_r_lint_002_and_exits_1(tmp_path, capsys):
    write_corpus(tmp_path, {
        COMPONENT: _ratified_component(
            '- Should a foo also be able to make a bar?\n\n'
        ),
    })
    code = spec_linter.main(['--format=json', '--repo-root=' + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    hits = _lint_002_fails(data['findings'])
    assert hits, data
    assert data['summary']['hard_failures'] >= 1


def test_ratified_with_empty_open_questions_has_no_r_lint_002(tmp_path):
    write_corpus(tmp_path, {
        COMPONENT: _ratified_component(''),
    })
    report = spec_linter.lint(None, tmp_path)
    assert not _lint_002_fails(field(report, 'findings'))