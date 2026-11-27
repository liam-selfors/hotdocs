# hotdocs-criterion: sha256:5816982b3f4a22d3d3ad31ceb459cb2d017a51de2ba7b5122dd8176e20c29249
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


DANGLING_ID = "comp-no-such-thing"
COMPONENT_MD = "specs/components/foo/component.md"


def _dangling_changes():
    original = CLEAN_CORPUS[COMPONENT_MD]
    changed = original.replace(
        "depends_on: []\n", "depends_on: [" + DANGLING_ID + "]\n"
    )
    assert changed != original
    return {COMPONENT_MD: changed}


def _r003_findings(findings):
    return [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-003"
        and field(f, "severity") == "fail"
        and DANGLING_ID in str(field(f, "message"))
    ]


def test_clean_corpus_has_no_hard_failures(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert field(report, "hard_failures") == 0


def test_lint_reports_dangling_depends_on(tmp_path):
    write_corpus(tmp_path)
    assert field(spec_linter.lint(None, tmp_path), "hard_failures") == 0

    write_corpus(tmp_path, _dangling_changes())
    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))
    matches = _r003_findings(findings)
    assert matches, "expected an R-LINT-003 fail finding naming " + repr(DANGLING_ID) + ", got " + repr(findings)
    assert any("component.md" in str(field(f, "file")) for f in matches)
    assert field(report, "hard_failures") >= 1


def test_cli_lint_reports_dangling_depends_on(tmp_path, capsys):
    write_corpus(tmp_path, _dangling_changes())
    capsys.readouterr()
    code = spec_linter.main(["--repo-root=" + str(tmp_path), "--format=json"])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    matches = _r003_findings(doc["findings"])
    assert matches, "expected an R-LINT-003 fail finding in " + repr(doc)
    assert doc["summary"]["hard_failures"] >= 1