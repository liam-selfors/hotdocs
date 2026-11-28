# hotdocs-criterion: sha256:72d8f98154b6db0c02c515b9d6c8a3ba4429a1430237916b79709b5d68845a0d
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


WEB_COMPONENT = (
    '---\n'
    'id: comp-web\n'
    'title: Web\n'
    'status: draft\n'
    'owners: [team-a]\n'
    'depends_on: []\n'
    'sealed: true\n'
    'source_path: legacy/web/\n'
    'assets: [nosuchkind-x9:a.js, demo:b.js]\n'
    '---\n'
    '\n'
    '# Web\n'
    '\n'
    '## Purpose\n'
    '\n'
    'Serves a web page.\n'
    '\n'
    '## Scope\n'
    '\n'
    '**In scope:** a page. **Out of scope:** everything else.\n'
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


DEMO_KIND = (
    '---\n'
    'id: arch-asset-kind-demo\n'
    'title: Asset Kind demo\n'
    'status: draft\n'
    'owners: [team-a]\n'
    'depends_on: []\n'
    '---\n'
    '\n'
    '# Asset Kind demo\n'
    '\n'
    '## Layout\n'
    '\n'
    'One file.\n'
    '\n'
    '## Environment\n'
    '\n'
    'Nothing needed.\n'
    '\n'
    '## Running criteria\n'
    '\n'
    'Calls the file.\n'
    '\n'
    '## Strength check\n'
    '## Test author guidance\n'
    '\n'
    'Use asset_runner.\n'
    '\n'
    '## Generator guidance\n'
    '\n'
    'Write plain code.\n'
)


def test_ac_lint_040(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_corpus(repo_root, {
        'specs/components/web/component.md': WEB_COMPONENT,
        'specs/architecture/asset-kind-demo.md': DEMO_KIND,
    })

    assets_line = None
    for index, line in enumerate(WEB_COMPONENT.splitlines(), start=1):
        if line.startswith('assets:'):
            assets_line = index
            break
    assert assets_line is not None

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")

    selected = [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-034"
        and field(f, "severity") == "fail"
        and field(f, "file") == "specs/components/web/component.md"
    ]
    messages = [field(f, "message") for f in selected]

    assert messages == [
        "asset kind 'nosuchkind-x9' has no definition; run hotdocs kind new nosuchkind-x9",
        "asset kind 'demo' definition lacks section 'Surface'",
        "asset kind 'demo' definition has empty section 'Strength check'",
        "asset kind 'demo' is defined in this repository; depends_on must list comp-kind-demo",
    ]
    for f in selected:
        assert field(f, "line") == assets_line