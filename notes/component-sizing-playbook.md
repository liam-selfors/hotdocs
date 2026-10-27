# Component Sizing Playbook — Tighten vs. Split

_Working notes. Non-normative. The actual caps and the "decomposition
signal, not just a cap" principle live in `SPEC_GUIDELINES.md` §4 — this
file is the worked decision procedure for acting on that signal, grounded
in this corpus's own real cases rather than abstract advice. Started:
2026-10-26._

Triggered by `spec-linter`'s `R-LINT-022` finding (two or more size-cap
dimensions over their warn threshold for the same component at once) —
or by a human/agent noticing a component is getting unwieldy before the
linter says so. Either way, work through this in order.

---

## Step 0: Is this actually the signal, or just fan-out?

If **only** `fan_out` is crowding and nothing else, stop here — that's
`D2`'s accepted "thin coordinator" shape (`merge-orchestrator` before
`D14`), not this signal at all. A coordinator with wide fan-out and
little owned logic of its own is a different risk shape than a
component doing too much, and `SPEC_GUIDELINES.md` §4 already says so
explicitly. Nothing to decide.

If **two or more** dimensions are crowding together, continue.

## Step 1: Classify the shape

- **Fan-out + component-doc words together** — a coordinator whose own
  owned-logic has grown alongside its call count (`merge-orchestrator`
  under `D14`, and again under `D29`). Go to Step 2.
- **Words/counts crowding with little or no fan-out** — a dense,
  self-contained component (`spec-linter` under `D17`). Go to Step 3.
- **Something else** — these two are the only shapes seen in this
  corpus so far. Don't force a non-matching case into one of them;
  reason from `SPEC_GUIDELINES.md` §4's underlying principle instead
  (does this really reflect one cohesive responsibility or two), and
  record whatever new shape you find here afterward.

## Step 2: Fan-out + words crowding — look for a split precedent first

Ask: is there a sub-responsibility inside this component that is
**structurally analogous to an already-specced component's pattern**,
one scope level up or down from something that already exists? `D14`
extracted `capability-scenario-verifier` because it was already the
cross-component analog of `verifier-orchestrator`'s own per-component
dispatch — the split mirrored a pattern already present, it wasn't
invented from scratch. `D29` extracted `provenance-checker` the same
way, once it was clear `cache-manager` was being asked a question
(“was this ever verified”) that belonged to a different kind of check
than the one it was actually built to answer (“was this already
produced”) — a real conceptual seam, not a cosmetic one.

**If a real precedent exists:** extract it. Expect `fan_out` to **stay
flat** — the coordinator still has to call the new component — the
dimension that's supposed to move is `component_doc_words`.

**But don't assume words will actually drop.** `D14`'s extraction did
drop `component_doc_words` "well clear" of both thresholds — the
capability-scenario dispatch logic moved out completely, taking its
words with it. `D29`'s extraction did **not**: `provenance-checker`
took the *mechanics* of the hit/miss check, but `merge-orchestrator`
still had to document, in its own requirements (now `component-gate-
runner`'s `R-GATE-001`/`007` after `D76` moved them), *when* and *why*
it calls the new component versus routing around it entirely for a
sealed component — reasoning that belongs to the coordinator's own
routing decision, not the extracted component's. An extraction relieves
word pressure only for the words that actually left; words describing
the coordinator's own remaining decision don't leave just because a
mechanism moved. Check the actual number after extracting — don't
assume the shape of `D14`'s outcome repeats.

**Nor should you assume `fan_out` stays flat, either.** `D76` extracted
`component-gate-runner` out of `merge-orchestrator` the same way `D14`
did — but unlike `D14`, fan-out actually dropped, from 15 to 9. The
difference: every one of the seven dependencies `component-gate-runner`
now calls (`provenance-checker`, `spec-bundle-assembler`, `generator`,
`verifier-orchestrator`, `license-scanner`, `secret-scanner`,
`provenance-writer`) had been a direct `merge-orchestrator` dependency
used for nothing but that one gauntlet — there was no other reason for
`merge-orchestrator` to keep calling any of them directly. `D14`'s
extraction didn't get this benefit because `merge-orchestrator` had
(and still has) its own independent reasons to call several of
`capability-scenario-verifier`'s own dependencies directly. Whether
fan-out drops depends on whether the parent coordinator ever had a
*second* reason to call the extracted component's dependencies, not on
the extraction pattern itself — check both numbers after extracting,
don't assume either one from precedent alone.

**If no real precedent exists:** do not invent a split just to relieve
the finding. A split with no structural precedent is premature
abstraction wearing a size-cap excuse (`D4`/`D6`). Go to Step 4
(tightening) instead, and write down explicitly, in the component's own
`Rationale` or the architecture doc, that a split was considered and
rejected, and why — so a future reader doesn't have to re-litigate it
from the finding alone.

## Step 3: Words/counts crowding, little fan-out — the cohesion question

Ask: can this component's behavior honestly be split into two
different one-sentence "why does this exist" statements, each serving
a materially different consumer or capability? If yes, that's
`D2`'s actual non-negotiable trigger (`SPEC_GUIDELINES.md` §4)
wearing a size-cap costume — split along that seam.

If no — if the crowding reflects **one cohesive responsibility with
many genuinely independent, correlated rules** (`spec-linter`'s own
case, `D77`: a structural linter whose rule count, generated code, and
spec bundle all grow together because each new rule is a real, separate
check, not a second responsibility) — don't split. Splitting a
single-pass component into sub-checkers for no architectural reason is
the wrong response to this signal, not the right one. Accept the
near-misses, document why (same as Step 2's rejected-split case), and
move on.

## Step 4: Tightening toolbox, cheapest first

Everything here was actually used, in this order, trimming
`merge-orchestrator` from 4170 back to 3991 words during `D29` without
splitting anything further:

1. **Cut restated reasoning, don't duplicate it.** If the same "why"
   needs to be referenced from two places (a requirement and an open
   question, a requirement and a changelog bullet), write it in full
   **once**, in its most natural home — usually the requirement that
   actually governs the behavior — and make every other mention a
   short pointer, not a second explanation.
2. **Trim Gherkin to the minimum that tests the behavior.** Acceptance
   criteria should assert outcomes, not re-argue the requirement's own
   justification — parenthetical "because..." clauses belong in the
   requirement, never repeated in the `Given`/`When`/`Then`.
3. **Shorten "resolved" open-question notes once the real reasoning has
   a permanent home.** An open question's resolution note only needs
   to say *where* the answer now lives, not restate the answer itself.
4. **Shorten changelog bullets to fact + pointer.** "What changed,
   where" — not a second summary of why.
5. **Put deep narrative where there's room for it.** This corpus's
   architecture-level docs (`pipeline-decomposition.md`,
   `graph-query-engine.md`) carry a much larger word budget than any
   one component's own directory. The *normative* rule stays terse in
   the component's own `requirements/`; the *historical* "how we got
   here" narrative belongs in the architecture doc, with the component
   pointing at it rather than repeating it.
6. **Measure, don't estimate.** Re-run the real linter after every
   meaningful edit (`/tmp/hotdocs-venv2/bin/python
   gen/spec-linter/spec_linter.py` or your own build's equivalent) and
   trim against the actual reported number — word counts are easy to
   misjudge by eye, especially near a hard-fail boundary.

If tightening genuinely can't bring a *necessary* addition under the
cap — not "it would take more effort," but there's no more restatement
left to cut — that's the real signal to revisit Step 2/3, or, failing
that, to flag the cap itself as miscalibrated for this case (rare; the
last three size-cap rows are already documented as "a first pass...
expect them to be revisited," `D17`). Don't split merely because
trimming is tedious.

## Step 5: Never split to relieve a number alone

Every real split in this corpus (`D14`, `D29`) was grounded in an
existing structural pattern the new component mirrored — never in the
crowding finding by itself. Every accepted non-split (`D17`'s
`spec-linter`, and any crowding case resolved by tightening instead) was
grounded in an explicit cohesion argument, written down, not just a
quiet decision to ignore the warning. Treat the finding as a prompt to
reason explicitly, in either direction — not as a mandate to act, and
not as something to silently dismiss either.

---

## Quick reference

| Signal | First move |
| --- | --- |
| Fan-out alone | Nothing — accepted thin-coordinator shape (Step 0) |
| Fan-out + words, real split precedent exists | Extract it; check — don't assume — whether words actually drop (Step 2) |
| Fan-out + words, no precedent | Tighten (Step 4); document the rejected split |
| Words/counts, no fan-out, one cohesive responsibility | Tighten or accept; document why no split |
| Words/counts, no fan-out, two real responsibilities | Split along that seam (Step 3) |
| Tightening exhausted, addition still necessary | Revisit split, or flag the cap itself — don't force it |
