# hotdocs-criterion: sha256:cfa9e16527273441ebfe0e37183ba7cd7dbd13b83b38292ce58b58d18a005297
import json

import pytest

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
CLEAN_REALIZES = 'realizes: [P-FOO]\n'
CLEAN_SEALED = 'sealed: false\n'

VARIANTS = {
    "empty-realizes-sealed-false": (
        'realizes: []\n', 'sealed: false\n'),
    "absent-realizes-sealed-false": (
        '', 'sealed: false\n'),
    "empty-realizes-sealed-absent": (
        'realizes: []\n', ''),
    "absent-realizes-sealed-absent": (
        '', ''),
}


def component_text(realizes_line, sealed_line):
    text = CLEAN_CORPUS[COMPONENT]
    assert CLEAN_REALIZES in text and CLEAN_SEALED in text
    text = text.replace(CLEAN_REALIZES, realizes_line, 1)
    text = text.replace(CLEAN_SEALED, sealed_line, 1)
    return text


def r_lint_006_fails(findings):
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-LINT-006" and field(f, "severity") == "fail":
            out.append(f)
    return out


def test_clean_corpus_has_no_r_lint_006(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert r_lint_006_fails(field(report, "findings")) == []


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_unsealed_component_with_zero_realizes_fails_r_lint_006(tmp_path, variant):
    realizes_line, sealed_line = VARIANTS[variant]
    write_corpus(tmp_path, {COMPONENT: component_text(realizes_line, sealed_line)})

    report = spec_linter.lint(None, tmp_path)
    findings = field(report, "findings")
    hits = r_lint_006_fails(findings)
    assert hits, "expected a fail-severity R-LINT-006 finding, got: " + repr(findings)
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith(COMPONENT) for f in hits
    ), repr(hits)
    assert field(report, "hard_failures") >= 1


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_cli_json_reports_r_lint_006_fail(tmp_path, capsys, variant):
    realizes_line, sealed_line = VARIANTS[variant]
    write_corpus(tmp_path, {COMPONENT: component_text(realizes_line, sealed_line)})

    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-006" and f["severity"] == "fail"
    ]
    assert hits, "expected a fail-severity R-LINT-006 finding, got: " + repr(doc)
    assert doc["summary"]["hard_failures"] >= 1