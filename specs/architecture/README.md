# Architecture

The only place the component decomposition itself is declared and changed.
Splitting or merging components is a distinct, heavier, explicitly-reviewed
operation that goes through here — never an ordinary component spec edit.

See `SPEC_GUIDELINES.md` §3.2.

- **`pipeline-decomposition.md`** — the hotdocs pipeline tool's own 15-component
  decomposition and dependency graph. Includes a flagged, unresolved tension
  (an orchestrator component's fan-out exceeds D2's cap) — see the file for
  why it wasn't silently patched.
