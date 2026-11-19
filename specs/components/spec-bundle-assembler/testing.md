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

**The asset fixture** adds to the above: in foo's frontmatter, the line
`assets: [javascript:static/app.js]` after `depends_on`, and
`interface/assets/app.js.md`:

````
# app.js

```
export function double(x)
```
````

**The project-kind asset fixture** adds to the asset fixture
`specs/architecture/asset-kind-javascript.md`: frontmatter `id: kind-javascript`,
`title: Asset kind javascript`, `status: draft`, `owners: [team-a]`,
`depends_on: []`, then `# Asset kind javascript` and, in this order, the
sections `Layout`, `Environment`, `Surface`, `Running criteria`,
`Strength check`, `Test author guidance`, `Generator guidance`, each a
`## <name>` line, a blank line, `<name> text.` and a blank line. It also
adds `specs/components/kind-javascript/`, built as foo with
`comp-kind-javascript`, `Kind javascript`, `R-KJS-001`, `AC-KJS-001`,
`source_path: legacy/kind-javascript/` and no `assets`, and foo's
`depends_on` becomes `[comp-kind-javascript]`. Its adapter, found under
`repo_root` before the tool's, is `gen/kind-javascript/kind_javascript.py`:

```python
KIND = "javascript"


def guidance():
    return {"generator": "Generator guidance text.\n",
            "test_author": "Test author guidance text.\n"}
```

The asset fixture alone takes the tool's own adapter,
`<tool_root>/gen/kind-javascript/kind_javascript.py` (the tool root the
parent of the nearest `gen` above `spec_bundle_assembler.__file__`); a
test loads it by path with `importlib.util.spec_from_file_location` and
calls its `guidance()` for the expected texts.
