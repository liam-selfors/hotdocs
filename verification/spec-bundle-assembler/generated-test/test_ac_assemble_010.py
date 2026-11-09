from pathlib import Path

import spec_bundle_assembler


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def test_ac_assemble_010_dependency_context_is_purpose_only(tmp_path):
    repo_root = tmp_path

    glossary_md = """# Glossary

- **Foo** — a test term.
"""

    d13_md = """---
id: D13
title: Test Decision Thirteen
status: ratified
owners: [team-a]
last_ratified_commit: abc1234
---

# D13

This is a synthetic decision used only so that Bar's Rationale section
has something to cite.
"""

    foo_component_md = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: [comp-bar]
---

# Foo

## Purpose

Foo doubles a number.
"""

    foo_requirement_md = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

    foo_acceptance_md = '''# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
'''

    foo_library_md = """# Library

```
foo(x: int) -> int
```
"""

    foo_constraints_md = """# Constraints

None.
"""

    bar_component_md = """---
id: comp-bar
title: Bar
status: draft
owners: [team-a]
sealed: true
source_path: legacy/bar/
depends_on: []
---

# Bar

## Purpose

Caches results.

## Rationale

This caching strategy follows the design established in D13.
"""

    bar_requirement_md = """# R-BAR-001

**R-BAR-001** — `bar(x)` MUST return the cached value for `x` if present.
"""

    bar_acceptance_md = '''# AC-BAR-001

Covers: R-BAR-001
Kind: generated-test

```gherkin
Given x is already cached
When bar(x) is called
Then it returns the cached value
```
'''

    bar_library_md = """# Library

```
bar(x: int) -> int
```
"""

    bar_constraints_md = """# Constraints

None.
"""

    specs = repo_root / "specs"
    (specs).mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(glossary_md)

    decisions_dir = specs / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / "D13.md").write_text(d13_md)

    foo_dir = specs / "components" / "foo"
    (foo_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (foo_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (foo_dir / "interface").mkdir(parents=True, exist_ok=True)
    (foo_dir / "component.md").write_text(foo_component_md)
    (foo_dir / "requirements" / "R-FOO-001.md").write_text(foo_requirement_md)
    (foo_dir / "acceptance" / "AC-FOO-001.md").write_text(foo_acceptance_md)
    (foo_dir / "interface" / "library.md").write_text(foo_library_md)
    (foo_dir / "constraints.md").write_text(foo_constraints_md)

    bar_dir = specs / "components" / "bar"
    (bar_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (bar_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (bar_dir / "interface").mkdir(parents=True, exist_ok=True)
    (bar_dir / "component.md").write_text(bar_component_md)
    (bar_dir / "requirements" / "R-BAR-001.md").write_text(bar_requirement_md)
    (bar_dir / "acceptance" / "AC-BAR-001.md").write_text(bar_acceptance_md)
    (bar_dir / "interface" / "library.md").write_text(bar_library_md)
    (bar_dir / "constraints.md").write_text(bar_constraints_md)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    dependency_context = _field(bundle, "dependency_context") or {}

    assert set(dependency_context.keys()) == {"comp-bar"}
    assert dependency_context["comp-bar"] == "Caches results."
    assert "D13" not in dependency_context["comp-bar"]
    assert "Rationale" not in dependency_context["comp-bar"]

    text_fields = []
    for name in ["spec", "interface", "constraints", "glossary"]:
        value = _field(bundle, name)
        if value:
            text_fields.append(value)

    for name in ["dependency_interfaces", "dependency_context", "dependency_usage", "vars"]:
        value = _field(bundle, name) or {}
        for v in value.values():
            if v:
                text_fields.append(v)

    hint_code = _field(bundle, "hint_code")
    if hint_code:
        for v in hint_code.values():
            if v:
                text_fields.append(v)

    full_text = "\n".join(text_fields)

    assert "D13" not in full_text
    assert "Rationale" not in full_text
    assert "caching strategy" not in full_text