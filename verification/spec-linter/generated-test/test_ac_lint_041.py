# hotdocs-criterion: sha256:7161b23b9328c088d241735f20e77ce2dbaeb399c3122300e5b86721038c5a86
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


WARN_CHANGES = {
    'specs/components/foo/interface/cli.md': (
        '# CLI\n'
        '\n'
        '```\n'
        'foo [--bar]\n'
        '```\n'
    ),
}

FAIL_CHANGES = {
    'specs/components/foo/acceptance/AC-FOO-001.md':
        CLEAN_CORPUS['specs/components/foo/acceptance/AC-FOO-001.md'].replace(
            'Kind: generated-test\n', ''
        ),
}


def _run(argv, capsys):
    capsys.readouterr()
    code = spec_linter.main(argv)
    out = capsys.readouterr().out
    return code, out


def test_clean_corpus_json_exit_0(tmp_path, capsys):
    write_corpus(tmp_path)
    code, out = _run(["--repo-root=" + str(tmp_path), "--format=json"], capsys)
    assert code == 0
    report = json.loads(out)
    assert report["summary"]["hard_failures"] == 0


def test_one_warn_exit_0_then_strict_exit_1(tmp_path, capsys):
    write_corpus(tmp_path, WARN_CHANGES)
    args = ["--repo-root=" + str(tmp_path), "--format=json"]
    code, out = _run(list(args), capsys)
    assert code == 0
    json.loads(out)
    code_strict, out_strict = _run(list(args) + ["--strict"], capsys)
    assert code_strict == 1
    json.loads(out_strict)


def test_one_fail_exit_1_with_one_r_lint_010_finding(tmp_path, capsys):
    write_corpus(tmp_path, FAIL_CHANGES)
    code, out = _run(["--repo-root=" + str(tmp_path), "--format=json"], capsys)
    assert code == 1
    report = json.loads(out)
    lint010 = [f for f in report["findings"] if f["rule_id"] == "R-LINT-010"]
    assert len(lint010) == 1
    assert lint010[0]["severity"] == "fail"


def test_bad_format_exit_2(tmp_path, capsys, monkeypatch):
    write_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)
    capsys.readouterr()
    assert spec_linter.main(["--format=xml"]) == 2
    capsys.readouterr()
    assert spec_linter.main(["--repo-root=" + str(tmp_path), "--format=xml"]) == 2