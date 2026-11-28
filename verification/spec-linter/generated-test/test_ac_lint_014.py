# hotdocs-criterion: sha256:17c9a58a7487d321a59944daed003606f4f5c8ebff39da9c5f82d097c7f66da5
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


MAIN_GLOSSARY = (
    '# Glossary\n'
    '\n'
    'Canonical vocabulary for this spec corpus.\n'
    '\n'
    '- **Foo** — a thing a component makes.\n'
)

SECOND_GLOSSARY = (
    '# Glossary\n'
    '\n'
    'Canonical vocabulary for this spec corpus (billing).\n'
    '\n'
    '- **Invoice** — a bill sent to a customer.\n'
)

TWO_GLOSSARIES = {
    'specs/glossary.md': MAIN_GLOSSARY,
    'specs/glossary-billing.md': SECOND_GLOSSARY,
}


def lint014(report):
    return [f for f in field(report, 'findings')
            if field(f, 'rule_id') == 'R-LINT-014']


def norm(path):
    return str(path).replace('\\', '/')


def test_two_glossaries_without_split_decision_fail_r_lint_014(tmp_path):
    write_corpus(tmp_path, TWO_GLOSSARIES)

    report = spec_linter.lint(None, tmp_path)

    found = lint014(report)
    fails = [f for f in found if field(f, 'severity') == 'fail']
    assert fails, 'expected a fail-severity R-LINT-014 finding, got ' + repr(
        field(report, 'findings'))
    # Each glossary-like file but specs/glossary.md gets one finding.
    assert len(found) == 1, repr(found)
    files = [norm(field(f, 'file')) for f in fails]
    assert any(p.endswith('specs/glossary-billing.md') for p in files), repr(files)
    assert not any(p.endswith('specs/glossary.md') for p in files), repr(files)
    assert field(report, 'hard_failures') >= 1


def test_three_glossaries_give_one_finding_each_but_main(tmp_path):
    changes = dict(TWO_GLOSSARIES)
    changes['specs/glossary-ops.md'] = (
        '# Glossary\n\n- **Runbook** — an ops procedure.\n'
    )
    write_corpus(tmp_path, changes)

    found = lint014(spec_linter.lint(None, tmp_path))

    assert len(found) == 2, repr(found)
    assert all(field(f, 'severity') == 'fail' for f in found)
    files = sorted(norm(field(f, 'file')) for f in found)
    assert files[0].endswith('specs/glossary-billing.md')
    assert files[1].endswith('specs/glossary-ops.md')


def test_single_glossary_has_no_r_lint_014_finding(tmp_path):
    write_corpus(tmp_path, {'specs/glossary.md': MAIN_GLOSSARY})

    assert lint014(spec_linter.lint(None, tmp_path)) == []


def test_bounded_context_architecture_doc_suppresses_r_lint_014(tmp_path):
    changes = dict(TWO_GLOSSARIES)
    changes['specs/architecture/contexts.md'] = (
        '---\n'
        'id: arch-contexts\n'
        'title: Contexts\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: []\n'
        '---\n'
        '\n'
        '# Contexts\n'
        '\n'
        'Billing is a separate Bounded Context with its own vocabulary.\n'
    )
    write_corpus(tmp_path, changes)

    assert lint014(spec_linter.lint(None, tmp_path)) == []


def test_cli_reports_r_lint_014_and_exits_1(tmp_path, capsys):
    write_corpus(tmp_path, TWO_GLOSSARIES)

    code = spec_linter.main(['--format=json', '--repo-root=' + str(tmp_path)])

    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    rule = [f for f in data['findings'] if f['rule_id'] == 'R-LINT-014']
    assert rule and all(f['severity'] == 'fail' for f in rule), repr(data)
    assert data['summary']['hard_failures'] >= 1