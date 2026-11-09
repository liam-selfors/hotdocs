import spec_bundle_assembler


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _get_field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def test_ac_assemble_011_dependency_usage_real_code_vs_absent(tmp_path):
    repo_root = tmp_path

    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    # --- comp-foo (dependent, depends_on comp-bar and comp-baz) ---
    foo_dir = repo_root / "specs" / "components" / "foo"
    _write(
        foo_dir / "component.md",
        """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: [comp-bar, comp-baz]
---

# Foo

## Purpose

Foo doubles a number.
""",
    )
    _write(
        foo_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        foo_dir / "acceptance" / "AC-FOO-001.md",
        """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
""",
    )
    _write(
        foo_dir / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(foo_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # --- comp-bar (sealed, with real code at its source_path) ---
    bar_dir = repo_root / "specs" / "components" / "bar"
    _write(
        bar_dir / "component.md",
        """---
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

Bar looks up values by key.
""",
    )
    _write(
        bar_dir / "requirements" / "R-BAR-001.md",
        "# R-BAR-001\n\n**R-BAR-001** — `bar_get(key)` MUST return the value for `key`.\n",
    )
    _write(
        bar_dir / "acceptance" / "AC-BAR-001.md",
        """# AC-BAR-001

Covers: R-BAR-001
Kind: generated-test

```gherkin
Given key = "k"
When bar_get(key) is called
Then it returns the value for key
```
""",
    )
    _write(
        bar_dir / "interface" / "library.md",
        "# Library\n\n```\nbar_get(key: str) -> str\n```\n",
    )
    _write(bar_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # --- comp-baz (sealed, no real code anywhere under its source_path) ---
    baz_dir = repo_root / "specs" / "components" / "baz"
    _write(
        baz_dir / "component.md",
        """---
id: comp-baz
title: Baz
status: draft
owners: [team-a]
sealed: true
source_path: legacy/baz/
depends_on: []
---

# Baz

## Purpose

Baz is a spec-only dependency with nothing real to introspect yet.
""",
    )
    _write(
        baz_dir / "requirements" / "R-BAZ-001.md",
        "# R-BAZ-001\n\n**R-BAZ-001** — `baz_get(key)` MUST return the value for `key`.\n",
    )
    _write(
        baz_dir / "acceptance" / "AC-BAZ-001.md",
        """# AC-BAZ-001

Covers: R-BAZ-001
Kind: generated-test

```gherkin
Given key = "k"
When baz_get(key) is called
Then it returns the value for key
```
""",
    )
    _write(
        baz_dir / "interface" / "library.md",
        "# Library\n\n```\nbaz_get(key: str) -> str\n```\n",
    )
    _write(baz_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # Real code for comp-bar's sealed source_path.
    _write(
        repo_root / "legacy" / "bar" / "bar.py",
        '''def bar_get(key: str) -> str:
    """Look up a value by key.

    Returns the stored value associated with key.
    """
    return key
''',
    )

    # comp-foo's own sealed source_path exists (required by sealed
    # components, per D60) but holds nothing relevant to this test.
    (repo_root / "legacy" / "foo").mkdir(parents=True, exist_ok=True)

    # comp-baz has no file at all under its declared source_path.
    assert not (repo_root / "legacy" / "baz").exists()

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    component_id = _get_field(bundle, "component_id")
    assert component_id == "comp-foo"

    dependency_usage = _get_field(bundle, "dependency_usage")
    assert isinstance(dependency_usage, dict)
    assert "comp-bar" in dependency_usage
    assert "comp-baz" in dependency_usage

    bar_usage = dependency_usage["comp-bar"]
    assert isinstance(bar_usage, str)
    assert bar_usage != ""
    assert "bar_get" in bar_usage
    assert "key: str" in bar_usage
    assert "-> str" in bar_usage
    assert "Look up a value by key." in bar_usage
    assert any(
        marker in bar_usage
        for marker in ("legacy.bar.bar", "legacy/bar/bar.py", "legacy.bar", "legacy/bar")
    )

    baz_usage = dependency_usage["comp-baz"]
    assert baz_usage == ""