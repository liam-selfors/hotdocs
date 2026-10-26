# Audit Before You Build

_Working notes. Non-normative. The habit that turned a proposed new
cache field (then a proposed digital-signature scheme) into zero new
artifacts during the `D39` work — recorded so the next "we need a way
to prove X happened" conversation starts here instead of at "let's add
a store for it." Started: 2026-10-26._

The moment you notice you need a way to record or prove some fact
happened — a verification passed, a call was made, an attempt was
recorded — the instinct is to design a new mechanism for it. Resist
that instinct until you've checked whether the fact is **already
sitting somewhere**, committed, and merely not yet being read.

## The check, in order

1. **`provenance-writer`'s manifest** (`.provenance.json`, `D7`,
   `SPEC_GUIDELINES.md` §7). This already carries `spec_bundle_hash`,
   `gate_versions`, and the full `verification_report`/`license_scan`/
   `secret_scan` for every component, committed under the same
   discipline as the code it describes. If the fact you need is "was
   this exact spec state already verified," this file already answers
   it — `provenance-checker` (`D39`) exists entirely because this step
   was skipped the first time and a new mechanism was almost built
   instead.
2. **The git commit ledger itself.** It is already an append-only,
   content-addressed, hash-chained record — the exact properties a
   proposed "tamper-evident" or "blockchain-style" mechanism is usually
   reaching for. If the fact you need is "did this pass the real gate
   before landing here," the answer is: it couldn't be committed
   otherwise (`R-MERGE-011`), so the mere presence of a file *is* the
   proof, no new ledger required.
3. **`merge-tracker`'s `.hotdocs/` records** (`tracking/`, `attempts/`,
   `calls/`). These carry rich, already-written detail per attempt —
   but remember the one hard constraint before reaching for them:
   **`.hotdocs/` content MUST NEVER be a gate input** (`SPEC_GUIDELINES.md`
   §1, `R-TRACK-005`). They're the right source for a human-facing
   convenience (`hotdocs track feedback`) or a UI
   (`merge-tracker-ui`), and the *wrong* source for anything a pass/fail
   decision depends on — this was specifically ruled out as the home
   for `D39`'s provenance check for exactly this reason.

If none of these three already has the fact you need, *then* a new
mechanism may genuinely be warranted — but by that point you'll know
precisely what's missing, rather than building something that
duplicates a chunk of an existing manifest.

## The tell that you skipped this step

If the new mechanism you're designing would need to carry
`spec_bundle_hash`, `gate_versions`, or a verification verdict as one
of its own fields — stop. Those three already live together in exactly
one place. A second place that also carries them is either a
duplicate of `provenance-writer`'s manifest (delete the duplicate, read
the original instead) or evidence the manifest itself is missing a
field it should have (fix the manifest, per `R-PROV-001`'s "collects,
never invents" discipline — add the field there, once, rather than
starting a second schema).
