# hotdocs-criterion: sha256:aa9a04346650c3e605dd2698e51ee7e8335fc5e62ee69661ee2298d5ebe2808d
import io
import json
import contextlib

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


COMPONENT_REL = 'specs/components/foo/component.md'


def sealed_without_source_path():
    text = CLEAN_CORPUS[COMPONENT_REL]
    assert 'sealed: false\n' in text
    text = text.replace('sealed: false\n', 'sealed: true\n')
    assert 'source_path' not in text
    return text


def r005_fails(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-005" and field(f, "severity") == "fail"
    ]


def test_clean_corpus_has_no_r_lint_005_finding(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-005"
    ] == []


def test_sealed_true_without_source_path_fails_r_lint_005(tmp_path):
    write_corpus(tmp_path, {COMPONENT_REL: sealed_without_source_path()})
    report = spec_linter.lint(None, tmp_path)

    hits = r005_fails(report)
    assert hits, "expected a fail-severity R-LINT-005 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity")) for f in field(report, "findings")]
    )
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith(COMPONENT_REL)
        for f in hits
    )
    assert field(report, "hard_failures") >= 1


def test_cli_reports_r_lint_005_and_exits_1(tmp_path):
    write_corpus(tmp_path, {COMPONENT_REL: sealed_without_source_path()})
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    assert code == 1
    doc = json.loads(out.getvalue())
    assert any(
        f["rule_id"] == "R-LINT-005" and f["severity"] == "fail"
        for f in doc["findings"]
    )
    assert doc["summary"]["hard_failures"] >= 1