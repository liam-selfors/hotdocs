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
A test writes the fixture with these two functions, copied into its own
file exactly: `write_fixture(repo_root, component_files("foo"))`. A
dependent is `component_files("baz", depends_on="[comp-foo]")`, its id
`comp-baz` and its requirement `R-BAZ-001`, merged into the same dict.
Never retype the files: each requirement and acceptance file starts
with its `# <id>` heading, which lint checks (`R-LINT-007`), and every
file has `---` in column 0 of its first line, so never build one through
`textwrap.dedent` over interpolated text.

```python
def component_files(slug, depends_on="[]", extra_frontmatter="", purpose="Foo doubles a number."):
    """The files of one fixture component, keyed by path under repo_root."""
    upper = slug.upper()
    base = f"specs/components/{slug}/"
    return {
        base + "component.md": (
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            f"depends_on: {depends_on}\n"
            + extra_frontmatter +
            "---\n"
            "\n"
            f"# {slug.capitalize()}\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"{purpose}\n"
        ),
        base + f"requirements/R-{upper}-001.md": (
            f"# R-{upper}-001\n"
            "\n"
            f"**R-{upper}-001** — `foo(x)` MUST return `2 * x`.\n"
        ),
        base + f"acceptance/AC-{upper}-001.md": (
            f"# AC-{upper}-001\n"
            "\n"
            f"Covers: R-{upper}-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
            "```\n"
        ),
        base + "interface/library.md": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        base + "constraints.md": "# Constraints\n\nNone.\n",
    }


def write_fixture(repo_root, files):
    files = {"specs/glossary.md": "# Glossary\n\n- **Foo** — a test term.\n", **files}
    for rel, text in files.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
```

Deleting the `Kind:` line from an acceptance file is a hard lint
failure, the way to build a corpus `assemble` refuses. A sealed
component's real code goes under its `source_path`
(`legacy/foo/foo.py`), never `gen/`.

**The asset fixture** adds to the above: in foo's frontmatter, the line
`assets: [javascript:static/app.js]` after `depends_on`
(`component_files("foo", extra_frontmatter="assets: [javascript:static/app.js]\n")`), and
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
