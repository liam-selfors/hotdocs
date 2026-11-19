# Testing spec-bundle-assembler

The library's test fixture, which the criteria name, is built as follows.

Every criterion's synthetic corpus lives under a fresh temporary
`repo_root`, and `assemble`/`assemble_criterion` lint it first
(`R-ASSEMBLE-005`), so it MUST pass lint. `spec_linter` is never importable by name; a test
that lints its fixture first loads it from the tool root, as `assemble`
does (`R-ASSEMBLE-015`):

```python
import importlib.util, sys
from pathlib import Path
gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
base = gen / "spec-linter"
path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
spec = importlib.util.spec_from_file_location("spec_linter", path)
spec_linter = importlib.util.module_from_spec(spec)
sys.modules["spec_linter"] = spec_linter
spec.loader.exec_module(spec_linter)
assert spec_linter.lint(None, repo_root).hard_failures == 0
```
Each file is written exactly as shown, `---` in column 0 of line 1,
never through `textwrap.dedent` over interpolated text.

`specs/glossary.md`:

```
# Glossary

- **Foo** — a test term.
```

`specs/components/foo/component.md` (a dependent adds
`depends_on: [comp-foo]` in place of `[]`, with its own id and
`source_path`):

```
---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
```

`requirements/R-FOO-001.md`: `# R-FOO-001`, a blank line, then
`**R-FOO-001** — \`foo(x)\` MUST return \`2 * x\`.`

`acceptance/AC-FOO-001.md`:

````
# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
````

`interface/library.md`: `# Library` and a fenced `foo(x: int) -> int`.
`constraints.md`: `# Constraints` and `None.`

Deleting the `Kind:` line from an acceptance file is a hard lint
failure, the way to build a corpus `assemble` refuses. A sealed
component's real code goes under its `source_path`
(`legacy/foo/foo.py`), never `gen/`.
