# Non-Python assets in the specbase (survey, 2026-11-18)

Every component is generated as Python, but several carry a second
language or format as string constants that no gate parses, executes or
mutates as what it is. Found by scanning `specs/components/` for format
signals and every `gen/` module for string constants over 120 characters
that parse as another language. Sizes are from the generated code on
`refine-authoring-agentic`.

| Component | Embedded asset | Size today | What it is | Gate gap today |
| --- | --- | --- | --- | --- |
| `docs-site-renderer` | JavaScript, CSS, HTML | 2.8k chars JS, 0.5k CSS | Clickable, searchable DAG page (R-DOCS-001) | JS only reached by `D335`'s string mutation; behaviour never executed |
| `provenance-tracker-ui` | JavaScript, CSS, HTML | 0.5k JS, 1.4k CSS | Static readiness page; JS may only show/hide/select (R-UI-001) | Same; CSS never checked |
| `graph-query-engine` | SQL (DuckDB) | 8 statements, 5.7k chars | The views behind every graph query (R-GQE-001/004/005/008 quote SQL) | Python mutation never touches SQL operators; a wrong `JOIN`/`WHERE` survives unless a criterion happens to hit it |
| `spec-linter` | SQL (DuckDB) | 5 statements, 1.3k chars | Lint rules expressed as queries | Same as above |
| `agentic-generator` | macOS sandbox profile (SBPL) and `bwrap` arguments | 0.25k chars | The OS isolation that keeps model-written code off the network and out of the repo | Security-critical and only checked by one end-to-end criterion; a dropped `(deny network*)` is invisible to mutation |
| `generator`, `test-author`, `spec-reviewer`, `spec-completeness-assistant`, `agentic-generator` | Prompt text (Markdown) | 0.2k-1.2k chars each | Model instructions, versioned by `PROMPT_VERSION` | Prompts are tested for presence of phrases, never for effect; no regression check when one is edited |
| `review-packet-builder` | Markdown document (output) | rendered | The review packet a human reads (R-PACKET-012 `--format=markdown`) | Checked by substring criteria only |
| `hotdocs-init` | Project template: `hotdocs.toml`, `.secret-allowlist.json`, `examples/slugify/` specs | files | What a new project starts from (R-INIT-001/004/006/008) | The template's own validity (lints clean, config parses) is not a gate |
| `component-gate-runner`, `hotdocs-cli`, `llm-endpoint` | `hotdocs.toml` schema (config) | prose | Configuration every command reads | Schema exists only as prose in three places |
| `corpus-graph-builder`, `provenance-writer`, `provenance-checker`, `secret-scanner` | JSON data files (graph, manifests, allowlist) | prose | Committed data other components read | Shapes stated as JSON examples, not as a checked schema |

## Reading the table

- **Behavioural code in another language** (JS, SQL, sandbox profiles)
  is where gates are weakest: the code runs in production but is
  verified only through Python wrappers. These are the first candidates
  for an asset kind with its own runner and mutation operators.
- **Text that drives a model** (prompts) is an asset whose "tests" are
  evaluations, not unit tests. It needs a different strength check
  (fixed eval cases with expected judgements), not mutation.
- **Documents and templates** (review packet, init template) need
  structural checks plus perturbation, not execution.
- **Data and config** (manifests, graph, allowlist, `hotdocs.toml`)
  need a schema as the spec, and validation as the gate; this is the
  cheapest kind to make strict.

## Suggested order

1. `javascript` (docs-site-renderer, provenance-tracker-ui): the user's
   pick; mutation operators already exist (`D335`).
2. `sql` (graph-query-engine, spec-linter): high value, DuckDB is
   already a dependency, so it needs no new toolchain.
3. `data-schema` (manifests, graph, allowlist, config): low cost,
   removes prose-only shapes.
4. `sandbox-profile` (agentic-generator): small, security-critical.
5. `prompt` and `document`: need the evaluation-style strength check
   designed first.

See `specs/architecture/asset-kinds.md` for the contract and `D340`.
