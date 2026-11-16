# Library

One module file, `surface_checker.py`, never a package.

```
check_surface(component_id: str, repo_root: Path, code_dir: Path | None = None) -> SurfaceReport
GATE_VERSION: str  # "surface-checker@1.0.0"
```

`code_dir` is the candidate's directory, default
`<repo_root>/gen/<slug>/`; `<module>` is the slug with hyphens replaced
by underscores, a `<module>.py` or `<module>/__init__.py` in `code_dir`.
A direct dependency's module is found at
`<repo_root>/gen/<dep-slug>/`, or, for a component whose `component.md`
has `sealed: true`, at `<repo_root>/<source_path>`; a dependency with no
such directory is skipped. Each subprocess is `sys.executable` with
`PYTHONPATH` set to the directory holding the module it imports, the
current environment otherwise kept.

## How a check runs

1. **Import** (`R-SURF-001`): `import <module>` in a subprocess; a
   non-zero exit gives one `import_error` finding, message the last
   non-empty stderr line, and ends the check.
2. **Dependency names** (`R-SURF-002`): a static scan of the source text,
   never an import of the candidate. An alias is the dependency's module
   name, or the left side of an assignment line whose right side calls
   `importlib.import_module(`, `module_from_spec(`, `exec_module(` or a
   function named `_load...(` and holds the dependency's slug or module
   name as a whole quoted string, single or double quotes. Names are
   checked against the dependency's real module, in one subprocess:
   `<module>.py` or `<module>/__init__.py` inside `<repo_root>/gen/<dep-slug>/`,
   or inside `<repo_root>/<source_path>` for a sealed dependency, with
   `PYTHONPATH` that directory. A use is `<alias>.<name>` not preceded
   by a word character or `.`, wherever it sits, including after an
   `import` guarded by `try`/`except ImportError`; names starting `__`
   are ignored. A name passes when the module has it (`hasattr`) or
   `<module>.<name>` imports. Each distinct missing name gives one
   finding, message `<dep-slug> has no <name>, which the candidate uses`;
   a dependency whose module does not import is skipped.
3. **Command line** (`R-SURF-003`): only when the component's own
   `interface/library.md` has a line starting `Implements:` that names
   `specs/architecture/cli-conventions.md`. A subprocess, `PYTHONPATH`
   `code_dir`, runs `sys.exit(<module>.main(["--hotdocs-smoke-unknown"]))`,
   so a `main` returning `0` exits `0`; anything but exit `2`, a first stderr
   line starting `usage error: `, and no `Traceback` gives one
   `cli_usage` finding whose message joins, with `, `, each of
   `exit <code>`, `no usage error line` and `traceback` that applies, in
   that order: a `main` that prints nothing and returns `0` gives
   `exit 0, no usage error line`. A timeout gives message `timeout`.

A component with no `depends_on` entries, and one whose library has no
such `Implements:` line, gets no finding from checks 2 and 3.

## Test fixtures

A `repo_root` holds, per component, `specs/components/<slug>/component.md`
with YAML frontmatter between `---` lines (`id`; `depends_on: []` or a
list, a missing key meaning none; for a sealed one `sealed: true` and
`source_path: <dir>/`), an
`interface/library.md` that may hold just `# Library`, and module files
under `gen/<slug>/` or the sealed `source_path`. A candidate's uses of a
dependency sit inside function bodies, so importing the candidate never
runs them. No lint is run.
