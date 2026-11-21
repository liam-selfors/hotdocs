# hotdocs-criterion: sha256:d7bc8511809a52933a000629a593260fc026f74c34781560b5fe8d112904bfb9
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRODUCT_FOO = """---
id: P-FOO
title: Foo works
status: draft
owners: [team-a]
---

# Foo works

## Purpose

A foo can be made.

### CS-FOO-001
Covers: P-FOO
Kind: generated-test

```gherkin
Given nothing
When a foo is made
Then it exists
```
"""

FOO_COMPONENT = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
depends_on: []
realizes: [P-FOO]
sealed: false
---

# Foo

## Purpose

Makes a foo.

## Scope

**In scope:** making a foo. **Out of scope:** everything else.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
"""

FOO_REQ = """# R-FOO-001

**R-FOO-001** — `make_foo()` MUST return the string `"foo"`.
"""

FOO_LIB = """# Library

One module file, `foo.py`.

```
make_foo() -> str
```
"""

FOO_AC = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given nothing
When make_foo() is called
Then the result is "foo"
```
"""

FOO_CONSTRAINTS = """# Foo — Non-Functional Constraints

- **Pure.** No I/O.
"""

WEB_FRONTMATTER_LINES = [
    "---",
    "id: comp-web",
    "title: Web",
    "status: draft",
    "owners: [team-a]",
    "depends_on: []",
    "assets: [nosuchkind-x9:a.js, demo:b.js]",
    "sealed: true",
    "source_path: legacy/web/",
    "---",
]

WEB_BODY = """
# Web

## Purpose

Serves a web page.

## Scope

**In scope:** serving a page. **Out of scope:** everything else.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
"""

WEB_REQ = """# R-WEB-001

**R-WEB-001** — `serve()` MUST return the string `"page"`.
"""

WEB_AC = """# AC-WEB-001

Covers: R-WEB-001
Kind: generated-test

```gherkin
Given nothing
When serve() is called
Then the result is "page"
```
"""

WEB_CONSTRAINTS = """# Web — Non-Functional Constraints

- **Pure.** No I/O.
"""

DEMO_KIND = """---
id: arch-asset-kind-demo
title: Asset Kind demo
status: draft
owners: [team-a]
---

# Asset Kind demo

## Layout

One text file.

## Environment

No programs needed.

## Running criteria

The runner takes an entry point and arguments and returns a value.

## Strength check
## Test author guidance

Call asset_runner with the declared path.

## Generator guidance

Write plain text.
"""


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_corpus(root):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    write(root, "specs/components/foo/component.md", FOO_COMPONENT)
    write(root, "specs/components/foo/requirements/R-FOO-001.md", FOO_REQ)
    write(root, "specs/components/foo/interface/library.md", FOO_LIB)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", FOO_AC)
    write(root, "specs/components/foo/constraints.md", FOO_CONSTRAINTS)

    web_text = "\n".join(WEB_FRONTMATTER_LINES) + "\n" + WEB_BODY
    write(root, "specs/components/web/component.md", web_text)
    write(root, "specs/components/web/requirements/R-WEB-001.md", WEB_REQ)
    write(root, "specs/components/web/acceptance/AC-WEB-001.md", WEB_AC)
    write(root, "specs/components/web/constraints.md", WEB_CONSTRAINTS)

    write(root, "specs/architecture/asset-kind-demo.md", DEMO_KIND)

    assets_line = WEB_FRONTMATTER_LINES.index(
        "assets: [nosuchkind-x9:a.js, demo:b.js]"
    ) + 1
    return assets_line


def test_ac_lint_040_asset_kind_findings_in_order(tmp_path):
    repo_root = Path(tmp_path)
    assets_line = build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")

    target_file = "specs/components/web/component.md"
    relevant = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-034"
        and field(f, "severity") == "fail"
        and str(field(f, "file")).replace("\\", "/") == target_file
    ]

    messages = [field(f, "message") for f in relevant]
    expected = [
        "asset kind 'nosuchkind-x9' has no definition; run hotdocs kind new nosuchkind-x9",
        "asset kind 'demo' definition lacks section 'Surface'",
        "asset kind 'demo' definition has empty section 'Strength check'",
        "asset kind 'demo' is defined in this repository; depends_on must list comp-kind-demo",
    ]
    assert messages == expected

    for f in relevant:
        assert field(f, "line") == assets_line