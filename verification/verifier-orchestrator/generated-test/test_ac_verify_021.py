import json
from pathlib import Path

import pytest

import verifier_orchestrator


GLOSSARY = """# Glossary

- **Foo** — a test term.
"""

COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
depends_on: []
realizes: [P-FOO]
---

# Foo

## Purpose

Foo doubles a number.

## Scope

- In scope: doubling a number.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

PRODUCT_MD = """---
id: P-FOO
title: Foo capability
status: draft
owners: [team-a]
---

# Foo capability

## Purpose

Doubling numbers.

## Scope

- In scope: doubling numbers.

## Capability scenarios

### CS-FOO-001

Covers: P-FOO
Kind: compiled

```gherkin
Given a n is 2
When double is invoked with n
Then value equals 4
```
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — `double(x)` MUST return a `Doubled` whose `value` is `2 * x`.
"""

LIBRARY_MD = """# Library

```
double(x: int) -> Doubled
```
"""

DOUBLED_MD = """# `Doubled`

```json
{ "value": 4 }
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

GEN_FOO_PY = """from dataclasses import dataclass


@dataclass
class Doubled:
    value: int


def double(x: int) -> Doubled:
    return Doubled(value=2 * x)
"""


def acceptance_md(expected):
    return (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a n is 2\n"
        "When double is invoked with n\n"
        "Then value equals " + str(expected) + "\n"
        "```\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(root, expected):
    write(root / "specs" / "glossary.md", GLOSSARY)
    write(root / "specs" / "product" / "foo.md", PRODUCT_MD)
    comp = root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "interface" / "data" / "Doubled.md", DOUBLED_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance_md(expected))
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(root / "gen" / "foo" / "foo.py", GEN_FOO_PY)
    return root


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def parse_json_output(out):
    start = out.find("{")
    assert start != -1, "no JSON object in output: %r" % out
    obj, _ = json.JSONDecoder().raw_decode(out[start:])
    return obj


def test_passing_component_json_and_text(tmp_path, monkeypatch, capsys):
    root = build_repo(tmp_path / "repo", 4)
    monkeypatch.chdir(tmp_path)

    rc_json = verifier_orchestrator.main(
        ["comp-foo", "--repo-root=" + str(root), "--format=json"]
    )
    out_json = capsys.readouterr().out
    assert rc_json == 0
    report = parse_json_output(out_json)
    assert report["overall"] == "pass"

    rc_text = verifier_orchestrator.main(
        ["comp-foo", "--repo-root", str(root), "--format", "text"]
    )
    out_text = capsys.readouterr().out
    assert rc_text == 0
    lines = out_text.splitlines()
    assert "comp-foo: pass" in [l.strip() for l in lines], out_text
    idx = [l.strip() for l in lines].index("comp-foo: pass")
    assert lines[idx] == "comp-foo: pass"
    following = lines[idx + 1:]
    assert following, "no criterion lines after header: %r" % out_text
    criterion_line = following[0]
    assert criterion_line[:1].isspace(), "criterion line not indented: %r" % criterion_line
    assert criterion_line.strip() == "AC-FOO-001: pass"


def test_failing_component_returns_1(tmp_path, monkeypatch, capsys):
    root = build_repo(tmp_path / "repo", 5)
    monkeypatch.chdir(tmp_path)

    rc = verifier_orchestrator.main(["comp-foo", "--repo-root=" + str(root)])
    capsys.readouterr()
    assert rc == 1


@pytest.mark.parametrize(
    "case",
    ["no-args", "bogus-format", "unknown-arg", "repo-root-last", "unknown-component"],
)
def test_usage_errors_return_2(tmp_path, monkeypatch, capsys, case):
    root = build_repo(tmp_path / "repo", 4)
    monkeypatch.chdir(tmp_path)

    argv = {
        "no-args": [],
        "bogus-format": ["comp-foo", "--repo-root=" + str(root), "--format=bogus"],
        "unknown-arg": ["comp-foo", "--repo-root=" + str(root), "--wat"],
        "repo-root-last": ["comp-foo", "--repo-root"],
        "unknown-component": ["comp-nope", "--repo-root=" + str(root)],
    }[case]

    rc = verifier_orchestrator.main(argv)
    err = capsys.readouterr().err
    assert rc == 2
    assert "hotdocs verify-component" in err