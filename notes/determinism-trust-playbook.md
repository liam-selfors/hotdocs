# Determinism & Trust Classification Playbook

_Working notes. Non-normative. The single idea that actually resolved
the `D29` cache/provenance investigation, generalized so the next
similar question doesn't need to re-derive it from scratch. Started:
2026-10-26._

Use this whenever you're designing (or auditing) anything that caches,
skips, or defers a piece of work based on a prior result — a new gate,
a new short-circuit, a new "don't redo this if nothing changed"
mechanism. The first question is never "should we trust the cache."
It's: **which band does the thing in question actually fall into?**

## The three bands

**Band 1 — Deterministic, always cheaply re-derivable.** `compiled`
criteria, and the *running* half of `generated-test` criteria (executing
already-authored test code against a candidate). Nothing about
re-checking this costs anything but CPU time — no model call, no
judgment, no non-reproducibility. A cache hit or miss here is **purely
a cost optimization.** There is no correctness question to design
around, because the real answer is always one cheap re-run away.
`cache-manager`'s narrowed role (`D29`) lives entirely in this band and
the next one.

**Band 2 — Non-deterministic authoring, but re-verifiable output.**
`generator` and `test-author`'s model calls. The call itself is
expensive and not required to be reproducible (their own
`constraints.md` say so explicitly) — but whatever they produce gets
checked by Band 1 machinery immediately afterward. A stale or
previously-failing cached candidate is **never silently dangerous**,
because nothing trusts it without re-running the cheap check. This is
why `R-GEN-006`/`R-AUTHOR-005` can cache unconditionally, right after
any successful call, with no correctness cost — the real gap `D29`
found wasn't in this caching, it was in `merge-orchestrator` treating a
Band-2 cache hit as license to skip the Band-1 re-check entirely.

**Band 3 — Non-deterministic verdict, no re-derivation available.**
`llm-judge`. Here the "check" and the "non-reproducible thing" are the
*same step* — there is no cheap fallback that independently confirms
the answer the way Band 1 does for Bands 1 and 2. This is the **only**
band where caching or trusting a prior result is a genuine correctness
and governance decision, not just a cost one. `VAR-TRUST-JUDGE-PROVENANCE`
exists because of this band specifically, and should be the *only*
place a trust variable like it is ever needed — if you find yourself
wanting one for a Band-1 or Band-2 mechanism, that's a sign something
is misdesigned, not a sign the variable is reusable.

## The questions to actually ask

1. **What band is this?** Walk the criterion/mechanism through the
   three definitions above before designing anything. Don't guess from
   vibes — check whether a cheap, independent re-check genuinely exists
   downstream (Bands 1/2) or doesn't (Band 3).
2. **If Band 1 or 2: is anything currently treating a hit as skipping
   the re-check, not just skipping the expensive step?** This is
   exactly the bug `D29` found — `cache-manager`'s hit was being used
   to skip `verifier-orchestrator` entirely, not just to skip a
   redundant model call. Any mechanism that conflates "this was
   produced before" with "this was verified before" has reintroduced
   this bug in a new place.
3. **If Band 3: does trusting a prior result need to be a deliberate,
   visible, possibly project-specific choice** (a var, like
   `VAR-TRUST-JUDGE-PROVENANCE`), **or should it just never be cached at
   all** (always re-run, full stop)? There is no universally correct
   answer here — it's a real governance trade-off, which is why it's a
   configurable var rather than a hardcoded rule.
4. **Sealed-component check, for anything keyed on `spec_bundle_hash`:**
   does this component have hand-maintained content whose correctness
   isn't actually captured by its spec hash? A sealed component's hash
   reflects only its *spec*, never its `source_path` — any new
   mechanism trusting a hash match must explicitly exclude sealed
   components, or it will silently stop catching a human's own edit
   breaking something (`R-MERGE-015`'s reasoning, almost reintroduced
   by `provenance-checker` before this check was made explicit).

## Quick reference

| Band | Example | Can a cache hit here ever be unsafe? |
| --- | --- | --- |
| 1: deterministic | `compiled`, running a `generated-test` | No — just re-run it, it's free |
| 2: authored, re-verified | `generator`, `test-author` | No, *provided* something downstream still re-verifies the output — check that it does |
| 3: non-reproducible verdict | `llm-judge` | Yes — this is the only band where trusting a prior result is a real decision |
