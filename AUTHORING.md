# Writing specs that generate well

`QUICKSTART.md` gets a component generated. This guide is about writing the
spec so it generates *correctly the first time*, from a model that has never
seen your codebase and cannot ask you anything. `SPEC_GUIDELINES.md` is the
normative reference; this is the practical companion. In an installed
package, `SPEC_GUIDELINES.md` and the `specs/architecture/` documents this
guide names for the tool's own rules sit beside it, not in your project.

## 1. Each model sees only part of your spec

Three models read your spec, and none sees all of it.

| Who | Sees | Never sees |
| --- | --- | --- |
| The generator, writing `gen/<component>/` | `component.md`, `requirements/`, `interface/` (with any `Implements:` documents), `constraints.md`, its dependencies' `interface/`, the glossary | `acceptance/`, any test |
| A test author, writing one criterion's test | that one criterion, the requirement it `Covers:`, the component's `interface/` (with `Implements:` documents), its dependencies' `interface/`, the glossary | other criteria, other requirements, `constraints.md`, the code |
| The judge, for an `llm-judge` criterion | the criterion, its requirement, the interface, the code | other criteria |

Two rules follow, and most failed generations break one of them.

- **Every behavior a criterion expects must be stated in a requirement or
  the interface.** The generator never sees criteria, so a value, error or
  edge case that only a criterion mentions is one the code will not have.
  Since D252 the generator is told to implement exactly what the spec says
  and nothing more, so an unstated behavior is a guaranteed failure, not a
  lucky guess.
- **Every rule a test needs must be stated where that test's author can see
  it:** in the criterion itself, its covered requirement, or the interface.
  A rule written in another requirement, in `constraints.md` or in a
  decision record is invisible to the test author.

`hotdocs spec check` looks for both problems before you generate.

## 2. Where shared rules go

A rule that many criteria need, such as a reply format, a fixture layout,
or the CLI's exit-code conventions, belongs in a document under
`specs/architecture/`. Name it on the component's `interface/library.md`:

```
Implements: `specs/architecture/cli-conventions.md`
```

The document is then part of the interface every generator and test author
sees, and it does not count toward the component's word cap.

Watch for criteria that combine requirements. A criterion that checks the
order of several checks' findings, or that "only one finding" appears,
depends on every rule that could add one, yet its test author sees only
the one requirement it covers. Summarize how the pieces fit together (the
checks in order, what triggers each, exact messages) in a section of the
interface. When the tool's own `test-probe` and `surface-checker` were
first reviewed with `hotdocs spec check`, most of the gaps it found were
of this kind.

## 3. Choosing a criterion's kind

| Kind | Use when | The test is |
| --- | --- | --- |
| `compiled` | The behavior fits the step grammar (`specs/architecture/step-phrase-grammar.md`): call a function with literal inputs, compare a result field or the whole result with a literal | compiled deterministically; no model involved |
| `generated-test` | Setup or assertions the grammar can't express: files on disk, several calls, exceptions, CLI exit codes | written by a test author from the criterion |
| `llm-judge` | A quality, not a runtime behavior: documentation tone, a design rule | a model's verdict with rationale |

Prefer `compiled`, then `generated-test`. Use `llm-judge` sparingly: it is
the least reproducible.

## 4. Writing a criterion a test author can implement

A good criterion names concrete inputs and exact outputs, and its covered
requirement names every behavior it checks.

**Vague:**

```gherkin
Given a bad title
When slugify runs
Then it fails gracefully
```

**Testable:**

```gherkin
Given the title "" (an empty string)
When slugify(title) is called
Then it raises ValueError, its message containing "empty"
```

and the requirement says: *"`slugify` MUST raise `ValueError` with a
message containing `empty` when `title` is empty."*

Checklist:

- **Concrete values.** Literal inputs and exact expected outputs, not
  "a valid input" or "the correct result".
- **Exact shapes.** If a result is a dict, a JSON document or a file,
  state its keys and types in `interface/data/<Type>.md`, and have the
  criterion assert specific fields.
- **Errors by name.** Name the exception class, error category or exit
  code in a requirement, not only in a criterion.
- **Fixtures stated.** If tests must build files on disk, describe the
  layout in a "Test fixtures" section of `interface/library.md`: what a
  minimal valid input tree looks like, which files are required.
- **One behavior per criterion,** with Given, When and Then each present.
  `hotdocs lint` fails a criterion missing any of them.
- **Cover edges.** Empty input, maximum size, unicode, an absent optional
  argument, each failure mode. A generated-test criterion can carry several
  scenarios; one per edge is clearer.

### Examples from the tool's own rebuild

Each of these failed a real generation and was fixed in the spec:

| What went wrong | Fix |
| --- | --- |
| A test needed the compiled step grammar but its author never saw it, so it guessed six phrasings | `Implements: specs/architecture/step-phrase-grammar.md` on the interface |
| A criterion expected a reply format stated only in one requirement; other criteria's authors faked replies wrongly | The format moved to `interface/library.md` |
| A criterion expected a command to print its usage error; no requirement said so, and the generated code exited silently | The requirement now says every usage error prints one line to stderr |
| A decision's `supersedes` was written as a list in one spec and a single id in another; the test followed the wrong one | Both state the scalar form |
| A criterion said "within a minute"; a test author built a fixture too slow for the verifier's limit | The criterion states the exact bound and fixture size |

## 5. Files in other languages

When a component produces something other than Python, such as the
JavaScript a page runs, declare it as an asset (`assets:
[javascript:static/app.js]` in `component.md`) instead of keeping it in
Python strings. Then:

- list its interface the way the kind's definition asks: for
  `javascript`, one `export function` signature per line in a fenced
  block of the interface file;
- write criteria that call it through the `asset_runner` fixture with
  concrete JSON arguments and an exact expected result, so its tests can
  be mutation-tested on the asset itself;
- keep the asset's logic in pure functions over JSON values, and leave
  wiring (event handlers, the DOM) thin, since only functions a criterion
  can call are checked.

The kind's definition (`specs/architecture/asset-kind-<kind>.md`) gives
its test author and its generator their own guidance, so a criterion only
needs the facts specific to this component. `QUICKSTART.md` §5 covers
declaring assets, `hotdocs kind new` and the project Python environment.

## 6. Size limits

The linter fails a component whose generator bundle (what its generator
reads: its own docs except `acceptance/`, the documents its `Implements:` line
appends, and its dependencies' interfaces) is above 14,000 words, or whose
largest criterion bundle (what one criterion's test author reads) is above
12,000 words. It also fails any single requirement or criterion file above 500
words, and a `Purpose` section above 150 words. It warns well before
(`specs/architecture/size-caps.md`). When a component nears a cap:

- move rationale and history into decision records,
- move shared rules into `specs/architecture/` documents,
- or split it: a second component with its own interface, which the first
  lists in `depends_on`.

`hotdocs lint` also warns when several size dimensions are high at once:
that is a decomposition signal, not just a length problem.

## 7. Recording decisions

A decision record (`specs/decisions/D<N>.md`) explains why the spec says
what it says. Records are immutable once ratified: a change is a new
record, which may name the old one in `supersedes`.

```
hotdocs decision new "Slugs are lowercase ASCII"   # writes a draft with the next id
hotdocs decision ratify D7                          # status: ratified
git commit ...                                      # commit the record with the spec change
hotdocs decision record-commit D7                   # fills last_ratified_commit, then commit again
```

`last_ratified_commit` names the commit that landed the record, so it is
filled in by a follow-up commit. Cite a decision from a spec by its id in
backticks, such as `` `D7` ``.

## 8. Checking before you generate

```
hotdocs lint                         # structure, coverage, sizes, citations
hotdocs spec check comp-slugify      # can each criterion's test author write it?
hotdocs assist --changed=comp-slugify  # completeness, redundancy, blast radius
hotdocs impact --changed=comp-slugify  # what else the change touches
```

`spec check` and `assist` use your configured model when one is set in
`hotdocs.toml`; pass `--no-model` to run only their deterministic checks.
