# hotdocs-criterion: sha256:d022d4fc2fceb9daaefa3de0c577de9d324a11fb4f19a4313156736e820b1abd
"""AC-LINT-011b: a Definitions entry for a glossary term that adds genuinely
new, component-specific nuance (low textual overlap against the glossary's
definition) is a permitted delta, so lint reports no R-LINT-011 finding."""

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


GLOSSARY_DEFINITION = (
    'a reusable rendering unit shared across every component in the corpus.'
)

GLOSSARY = (
    '# Glossary\n'
    '\n'
    'Canonical vocabulary for this spec corpus.\n'
    '\n'
    '- **Widget** — ' + GLOSSARY_DEFINITION + '\n'
)

# Shares no tokens at all with GLOSSARY_DEFINITION: overlap ratio is 0.
DELTA_TEXT = (
    'within foo specifically, widgets carry an expiry timestamp; '
    'stale ones get purged nightly.'
)

COMPONENT_PATH = 'specs/components/foo/component.md'
NO_DELTAS_LINE = 'No deltas from `specs/glossary.md`.\n'


def component_with_definition(local_text):
    original = CLEAN_CORPUS[COMPONENT_PATH]
    assert NO_DELTAS_LINE in original
    return original.replace(
        NO_DELTAS_LINE,
        '- **Widget** — ' + local_text + '\n',
    )


def lint_011_findings(repo_root):
    report = spec_linter.lint(None, repo_root)
    findings = field(report, 'findings')
    return [f for f in findings if field(f, 'rule_id') == 'R-LINT-011']


def test_low_overlap_delta_is_not_a_redefinition(tmp_path):
    write_corpus(tmp_path, {
        'specs/glossary.md': GLOSSARY,
        COMPONENT_PATH: component_with_definition(DELTA_TEXT),
    })

    found = lint_011_findings(tmp_path)

    assert found == [], (
        'a genuinely new, low-overlap delta must not be reported as '
        'R-LINT-011; got: ' + repr(found)
    )


def test_control_near_verbatim_copy_is_reported(tmp_path):
    # Control: the same fixture shape with the glossary text copied
    # verbatim (overlap ratio 1.0) is a redefinition, so the check is live
    # and the absence above is due to low overlap, not to the rule never
    # firing.
    write_corpus(tmp_path, {
        'specs/glossary.md': GLOSSARY,
        COMPONENT_PATH: component_with_definition(GLOSSARY_DEFINITION),
    })

    found = lint_011_findings(tmp_path)

    assert len(found) >= 1
    assert all(field(f, 'severity') == 'fail' for f in found)