# hotdocs-criterion: sha256:1650aa7fc86bf14bed1bfbdc121e683c59e4ac0a2192a81d4cbf11ba35797442
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


def cli_doc(name):
    return (
        '# CLI\n'
        '\n'
        '```\n'
        + name + ' [--format=json|text]\n'
        '```\n'
    )


def sealed_component(slug, title):
    return (
        '---\n'
        'id: comp-' + slug + '\n'
        'title: ' + title + '\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: []\n'
        'sealed: true\n'
        'source_path: legacy/' + slug + '/\n'
        '---\n'
        '\n'
        '# ' + title + '\n'
        '\n'
        '## Purpose\n'
        '\n'
        'Does ' + slug + ' things.\n'
        '\n'
        '## Scope\n'
        '\n'
        '**In scope:** ' + slug + '. **Out of scope:** everything else.\n'
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


def constraints(title):
    return (
        '# ' + title + ' — Non-Functional Constraints\n'
        '\n'
        '- **Pure.** No I/O.\n'
    )


CLI_REQ_TEXT = (
    ' — The CLI in `interface/cli.md` MUST accept `--format=json` and '
    '`--format json`; `--format` given with no value MUST be a usage error '
    'returning exit code `2`; an unknown argument MUST be a usage error '
    'returning `2`; `--format` MUST pass through to the library call; '
    'exit code `0` MUST mean success and `1` a reported failure.\n'
)


CHANGES = {
    # Component one: foo — cli.md, a citing requirement, and a covering criterion.
    'specs/components/foo/interface/cli.md': cli_doc('foo'),
    'specs/components/foo/requirements/R-FOO-002.md': (
        '# R-FOO-002\n'
        '\n'
        '**R-FOO-002**' + CLI_REQ_TEXT
    ),
    'specs/components/foo/acceptance/AC-FOO-002.md': (
        '# AC-FOO-002\n'
        '\n'
        'Covers: R-FOO-002\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given the foo CLI\n'
        'When it is run with --format=json, --format json, a bare --format and an unknown argument\n'
        'Then it exits 0, 0, 2 and 2 respectively\n'
        '```\n'
    ),
    # Component two: bar — cli.md and a citing requirement with no covering criterion.
    'specs/components/bar/component.md': sealed_component('bar', 'Bar'),
    'specs/components/bar/interface/cli.md': cli_doc('bar'),
    'specs/components/bar/requirements/R-BAR-001.md': (
        '# R-BAR-001\n'
        '\n'
        '**R-BAR-001**' + CLI_REQ_TEXT
    ),
    'specs/components/bar/constraints.md': constraints('Bar'),
    # Component three: baz — cli.md, but no requirement cites it.
    'specs/components/baz/component.md': sealed_component('baz', 'Baz'),
    'specs/components/baz/interface/cli.md': cli_doc('baz'),
    'specs/components/baz/requirements/R-BAZ-001.md': (
        '# R-BAZ-001\n'
        '\n'
        '**R-BAZ-001** — `make_baz()` MUST return the string `"baz"`.\n'
    ),
    'specs/components/baz/acceptance/AC-BAZ-001.md': (
        '# AC-BAZ-001\n'
        '\n'
        'Covers: R-BAZ-001\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When make_baz() is called\n'
        'Then the result is "baz"\n'
        '```\n'
    ),
    'specs/components/baz/constraints.md': constraints('Baz'),
}


def test_ac_lint_031_cli_without_covered_citing_requirement_warns(tmp_path):
    repo_root = tmp_path
    write_corpus(repo_root, CHANGES)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    r031 = [f for f in findings if field(f, "rule_id") == "R-LINT-031"]

    assert len(r031) == 2, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in r031
    ]

    for f in r031:
        assert field(f, "severity") == "warn"
        assert "specs/architecture/acceptance-criteria.md" in field(f, "message")

    messages = [field(f, "message") for f in r031]
    assert not any("comp-foo" in m for m in messages)
    assert sum("comp-bar" in m for m in messages) == 1
    assert sum("comp-baz" in m for m in messages) == 1

    files = sorted(str(field(f, "file")).replace("\\", "/") for f in r031)
    assert files == [
        "specs/components/bar/interface/cli.md",
        "specs/components/baz/interface/cli.md",
    ]
    assert not any(
        "specs/components/foo/" in str(field(f, "file")).replace("\\", "/")
        for f in r031
    )