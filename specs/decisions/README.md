# Decision Records

ADR-style. Append-only. Once a decision record is ratified it is immutable —
a change in direction is a new record that supersedes the old one
(`supersedes` field), never an edit to it.

See `SPEC_GUIDELINES.md` §3.5.

**D15 through D30 are formalized here** (`D15.md` … `D30.md`), one file
per decision, each `ratified` with the commit that landed it. Every new
decision going forward gets a real record here at the time it's made —
not appended to a growing notes file.

**D1–D14 remain informal**, in `notes/initial-ideas.md` — the original
brainstorm that produced this project's own founding decisions. Several
were superseded or substantially redesigned by later, formal decisions
(`D15` alone replaced D1–D14's original component anatomy); backfilling
them here is still a real follow-up, not done in this pass, since most
of their *current* authoritative content already lives in a later
record or in `SPEC_GUIDELINES.md` directly.
