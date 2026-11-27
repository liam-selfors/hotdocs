# hotdocs-criterion: sha256:d19de7eba90fab958007b66a4fdab7a2a12eb02a8ec14c95d34c796b7ddc29e7
import os
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


def component_files(name, upper, missing):
    root = 'specs/components/' + name + '/'
    req_id = 'R-' + upper + '-001'
    ac_id = 'AC-' + upper + '-001'
    return {
        root + 'component.md': (
            '---\n'
            'id: comp-' + name + '\n'
            'title: Component ' + upper + '\n'
            'status: draft\n'
            'owners: [team-a]\n'
            'depends_on: [' + missing + ']\n'
            'sealed: true\n'
            'source_path: legacy/' + name + '/\n'
            '---\n'
            '\n'
            '# Component ' + upper + '\n'
            '\n'
            '## Purpose\n'
            '\n'
            'Does ' + name + ' things.\n'
            '\n'
            '## Scope\n'
            '\n'
            '**In scope:** ' + name + ' things. **Out of scope:** everything else.\n'
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
        root + 'requirements/' + req_id + '.md': (
            '# ' + req_id + '\n'
            '\n'
            '**' + req_id + '** — `do_' + name + '()` MUST return `' + repr(name) + '`.\n'
        ),
        root + 'acceptance/' + ac_id + '.md': (
            '# ' + ac_id + '\n'
            '\n'
            'Covers: ' + req_id + '\n'
            'Kind: generated-test\n'
            '\n'
            '```gherkin\n'
            'Given nothing\n'
            'When do_' + name + '() is called\n'
            'Then the result is ' + repr(name) + '\n'
            '```\n'
        ),
        root + 'constraints.md': (
            '# Component ' + upper + ' — Non-Functional Constraints\n'
            '\n'
            '- **Pure.** No I/O.\n'
        ),
    }


def rel_file(finding, repo_root):
    raw = str(field(finding, "file")).replace("\\", "/")
    p = Path(raw)
    if p.is_absolute():
        try:
            raw = p.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            raw = p.as_posix()
    if raw.startswith("./"):
        raw = raw[2:]
    return raw


def build(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    changes = {}
    changes.update(component_files("a", "A", "comp-missing-alpha"))
    changes.update(component_files("b", "B", "comp-missing-beta"))
    write_corpus(repo_root, changes)
    return repo_root


def test_lint_directory_path_limits_findings_to_component_a(tmp_path, monkeypatch):
    repo_root = build(tmp_path)
    monkeypatch.chdir(repo_root)

    report = spec_linter.lint([Path("specs/components/a")], repo_root)
    findings = list(field(report, "findings"))

    assert findings, "expected at least one finding"
    files = [rel_file(f, repo_root) for f in findings]
    for f in files:
        assert f.startswith("specs/components/a/"), (
            "finding outside specs/components/a/: " + repr(f) + " in " + repr(files)
        )
    assert any(
        field(f, "rule_id") == "R-LINT-003"
        and rel_file(f, repo_root) == "specs/components/a/component.md"
        for f in findings
    ), "no R-LINT-003 finding for component a: " + repr(
        [(field(f, "rule_id"), rel_file(f, repo_root)) for f in findings]
    )


def test_lint_file_path_limits_findings_to_component_b_root(tmp_path, monkeypatch):
    repo_root = build(tmp_path)
    monkeypatch.chdir(repo_root)

    report = spec_linter.lint([Path("specs/components/b/component.md")], repo_root)
    findings = list(field(report, "findings"))

    assert findings, "expected at least one finding"
    for f in findings:
        assert rel_file(f, repo_root) == "specs/components/b/component.md", (
            "finding outside specs/components/b/component.md: "
            + repr((field(f, "rule_id"), rel_file(f, repo_root)))
        )
    assert any(field(f, "rule_id") == "R-LINT-003" for f in findings), (
        "no R-LINT-003 finding: " + repr([field(f, "rule_id") for f in findings])
    )