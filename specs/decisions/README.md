# Decision Records — Guidelines

ADR-style, one file per decision, under `specs/decisions/D<N>.md`. This
document is the authoritative guide to writing and maintaining them;
`SPEC_GUIDELINES.md` §3.5 states the normative rules in brief and points
here for the full account.

## What belongs in a decision record

A decision record exists for a choice that could reasonably have gone
another way, where the reasoning matters to anyone revisiting it later —
not for every edit to a spec. If a change is purely mechanical (fixing a
typo, updating a stale cross-reference to match content that already
changed) it needs no record. If it changes what the methodology actually
does, or resolves a real ambiguity/gap discovered in the corpus, it
needs one.

## Atomicity

A decision record MUST cover exactly one topic — one problem, one
conclusion. The test: does removing any one paragraph leave the rest
meaning something different? If yes, it is one topic. If a paragraph
could be deleted intact with the rest unaffected, it belongs in its own
record instead. A follow-on finding discovered incidentally while
verifying or implementing an unrelated decision (a stray mis-citation,
an adjacent bug) gets its own record, never folded into the one that
happened to surface it.

This is a judgment call, the same way component-splitting
(`SPEC_GUIDELINES.md` §4) is — not mechanically enforced, but a real
question to ask before ratifying, every time.

## Shape

Every decision record carries the full frontmatter field set
(`SPEC_GUIDELINES.md` §2): `id`, `title`, `status`
(`draft`/`ratified`/`deprecated`), `owners`, `last_ratified_commit`
(the commit that landed it, once ratified — retained unchanged forever
after, even if the record is later deprecated: it is the historical
fact of when ratification happened, not a claim about whether the
record is still current), and two optional relationship fields:

- **`supersedes`** — the prior decision this one fully replaces. Scalar,
  singular. Setting it means the named decision's own conclusion is
  now entirely obsolete — never use it for a partial amendment; a
  decision that only reverses part of an earlier one's conclusion
  stays a plain prose cross-reference instead, no formal field.
- **`builds_on`** — the prior decisions this one's own reasoning
  depends on, without replacing any of them. List-valued, since a
  decision can depend on several. Carries no status obligation on
  either side.

Both resolve to a real decision id when checked (`R-LINT-029`/`030`),
except decisions still informally recorded in `notes/initial-ideas.md`
rather than as their own files, if any ever exist going forward the
same way the pre-formalization era once did.

## Landing a decision

`last_ratified_commit` names the commit that landed the record, which
cannot be known while that commit is being written. So a decision lands
in two commits: the first carries the ratified record, with
`last_ratified_commit: PENDING-COMMIT`, together with the spec change it
explains; the second replaces the placeholder with the first commit's
short hash and changes nothing else.

## The one sanctioned exception to immutability

Once ratified, a decision record's body is immutable — a change in
direction is a new, superseding record, never an edit to the old one.
The single exception: when a new decision's `supersedes` names a prior
one, that prior record's `status` field flips from `ratified` to
`deprecated` as part of the same change. This is a metadata-only edit,
never touching the body, and it is the one update the `supersedes`
mechanism itself requires to mean anything — without it, `deprecated`
could never be set and `supersedes` would be a field with no consumer.

## Citation discipline

A `D<N>` citation anywhere in the corpus must point to the *specific*
decision responsible for the *specific* fact being stated — never a
citation copied from a nearby one without checking it actually says
what is being attributed to it, and never a vague "see various
decisions." Checking a citation against the decision it names, before
relying on or extending it, is the expected discipline, not an
exceptional audit step: real citations have been found pointing at the
wrong decision simply because nobody checked.

Every citation uses the bare `D<N>` token, optionally backtick-wrapped,
always at a word boundary. Before deprecating or altering a decision,
the canonical check for what currently cites it is:

```
grep -rn '\bD<N>\b' specs/ --include="*.md" | grep -v '^specs/decisions/'
```

`specs/decisions/` is excluded deliberately — a citation inside another
decision record's own frozen historical narrative is never a drift
candidate; only one inside a *live* spec file is. `decision-drift-
detector` automates the commit-ancestry half of this same check
mechanically; this command is the zero-tooling version.

## Decisions are part of the corpus graph

A decision record is a real node in `graph-query-engine`'s shared
`nodes` view (`kind: decision`), and `supersedes`/`builds_on` are real
`edge_type`s in `edges` — the same shared-view pattern every other spec
kind (component, capability, var, requirement, acceptance) already
uses, not a side mechanism only decision-specific tooling can see. This
is what makes two further things possible without new machinery:

- **Staleness detection** (`decision-drift-detector`,
  `find_decision_drift`): for every live citation of a decision, is the
  citing file's own last-touched commit older than the ratification of
  whatever superseded that decision? If so, it is a candidate for
  review — never a verdict, since the citing content might still be
  correct in substance, just not re-verified.
- **Pre-ratification impact analysis** (`find_decision_impact`): given
  any decision id — including one not yet ratified, still being
  drafted — walk the graph backward to find every decision and every
  live file that would be affected by altering or superseding it. This
  is the check to run *before* ratifying a decision that changes an
  earlier one's conclusion, not after.

## The MVP baseline reset (one-time, not a precedent for routine use)

This corpus's decision history accumulated normally for a period, then
was deliberately collapsed once: every decision record was reviewed,
consolidated to its current, settled conclusion, freed of
superseded/deprecated chains, and renumbered sequentially from `D1`
with no gaps, specifically because the project was still establishing
its MVP baseline and a clean starting graph was worth more than
preserving the churn that produced it. Every citation across the whole
corpus was updated to match in the same pass.

**This is not a mechanism to reach for again.** Once a decision is
ratified under the renumbered baseline, immutability and the normal
`supersedes`/`deprecated` lifecycle apply exactly as described above,
with no further resets — a decision made after this point that changes
an earlier one's conclusion gets a new, superseding record, the same
way it always should have. The reset closes out the project's
pre-MVP history; it does not change what happens next.
