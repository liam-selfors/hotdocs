# hotdocs-criterion: sha256:78cc07302daf27b6f14bc52e2cb47c43c6c8a9100530c89b77d5982139ee920f
from pathlib import Path

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


WEB_PATH = 'specs/components/web/component.md'

SECTIONS = [
    'Layout',
    'Environment',
    'Surface',
    'Running criteria',
    'Strength check',
    'Test author guidance',
    'Generator guidance',
]


def component_body(title):
    return (
        '\n'
        '# ' + title + '\n'
        '\n'
        '## Purpose\n'
        '\n'
        'Does ' + title + ' things.\n'
        '\n'
        '## Scope\n'
        '\n'
        '**In scope:** its things. **Out of scope:** everything else.\n'
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


def web_component(assets_line):
    return (
        '---\n'
        'id: comp-web\n'
        'title: Web\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: [comp-kind-demo]\n'
        + assets_line + '\n'
        'sealed: true\n'
        'source_path: legacy/web/\n'
        '---\n'
        + component_body('Web')
    )


def kind_demo_component():
    return (
        '---\n'
        'id: comp-kind-demo\n'
        'title: Kind demo\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: []\n'
        'sealed: true\n'
        'source_path: legacy/kind-demo/\n'
        '---\n'
        + component_body('Kind demo')
    )


def definition_text():
    text = (
        '---\n'
        'id: arch-asset-kind-demo\n'
        'title: Asset Kind demo\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: []\n'
        '---\n'
        '\n'
        '# Asset Kind demo\n'
    )
    for name in SECTIONS:
        text += '\n## ' + name + '\n\nOne line of ' + name.lower() + ' text.\n'
    return text


def unit_files(slug, prefix):
    rid = 'R-' + prefix + '-001'
    aid = 'AC-' + prefix + '-001'
    return {
        'specs/components/' + slug + '/requirements/' + rid + '.md': (
            '# ' + rid + '\n'
            '\n'
            '**' + rid + '** — The component MUST do its thing.\n'
        ),
        'specs/components/' + slug + '/acceptance/' + aid + '.md': (
            '# ' + aid + '\n'
            '\n'
            'Covers: ' + rid + '\n'
            'Kind: generated-test\n'
            '\n'
            '```gherkin\n'
            'Given nothing\n'
            'When the thing is done\n'
            'Then it is done\n'
            '```\n'
        ),
        'specs/components/' + slug + '/constraints.md': (
            '# ' + slug + ' — Non-Functional Constraints\n'
            '\n'
            '- **Pure.** No I/O.\n'
        ),
    }


def build(repo_root, assets_line):
    changes = {
        WEB_PATH: web_component(assets_line),
        'specs/components/kind-demo/component.md': kind_demo_component(),
        'specs/architecture/asset-kind-demo.md': definition_text(),
    }
    changes.update(unit_files('web', 'WEB'))
    changes.update(unit_files('kind-demo', 'KIND-DEMO'))
    write_corpus(repo_root, changes)


def assets_line_number(repo_root):
    lines = (repo_root / WEB_PATH).read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines):
        if line.startswith('assets:'):
            return i + 1
    raise AssertionError('no assets line')


def lint034(repo_root):
    report = spec_linter.lint(None, repo_root)
    return [
        f for f in field(report, 'findings')
        if field(f, 'rule_id') == 'R-LINT-034'
    ]


def test_valid_asset_has_no_finding(tmp_path):
    repo_root = Path(tmp_path)
    build(repo_root, 'assets: [demo:static/app.js]')
    assert lint034(repo_root) == []


def test_invalid_entries_reported_in_order(tmp_path):
    repo_root = Path(tmp_path)
    entries = [
        'demo',
        'Demo:a.js',
        'demo:/abs.js',
        'demo:a\\b.js',
        'demo:x/../y.js',
        'demo:static/m.py',
        'python:pkg',
    ]
    build(repo_root, 'assets: [' + ', '.join(entries) + ']')
    findings = lint034(repo_root)
    expected = [
        "asset 'demo' is not <kind>:<path>",
        "asset 'Demo:a.js' is not <kind>:<path>",
        "asset 'demo:/abs.js': path must be relative with / separators",
        "asset 'demo:a\\b.js': path must be relative with / separators",
        "asset 'demo:x/../y.js': path contains ..",
        "asset 'demo:static/m.py': path ends in .py",
        "asset 'python:pkg': python is never declared",
    ]
    web_findings = [f for f in findings if field(f, 'file') == WEB_PATH]
    assert [field(f, 'message') for f in web_findings] == expected
    assert len(findings) == len(expected)
    line = assets_line_number(repo_root)
    for f in web_findings:
        assert field(f, 'severity') == 'fail'
        assert field(f, 'line') == line


def test_assets_not_a_list(tmp_path):
    repo_root = Path(tmp_path)
    build(repo_root, 'assets: demo:static/app.js')
    findings = lint034(repo_root)
    assert [field(f, 'message') for f in findings] == [
        'assets must be a list of <kind>:<path> strings'
    ]
    f = findings[0]
    assert field(f, 'severity') == 'fail'
    assert field(f, 'file') == WEB_PATH
    assert field(f, 'line') == assets_line_number(repo_root)