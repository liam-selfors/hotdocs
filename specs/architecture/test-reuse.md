---
id: arch-test-reuse
title: Test Specs and Test Reuse
status: draft
owners: [pipeline-team]
depends_on: []
---

# Test Specs and Test Reuse

## Purpose

A generated test is written from the spec alone, never from the code it
checks, so once it passes it stays valid until it is shown to be faulty
or what it was written from changes. These rules say what a test author
is shown, how a committed test is recognised as still current, and the
only conditions under which a test is authored again (`D341`).

## The test spec

A component may have `specs/components/<slug>/testing.md`: how its tests
build fixtures, plant stand-ins and find files. It holds test mechanics
only; a shape the component's own code reads (an input file's format, a
stand-in's call signature the code makes) belongs in the interface,
which both the generator and the test author see. It never restates a
requirement.

Its first line may be `Uses:` followed by backticked paths of files
under `specs/architecture/`, whose text the test author also sees. A
named path that does not exist is a `PreconditionFailure`, as for
`Implements:` (`R-ASSEMBLE-014`).

`spec-bundle-assembler` puts the test spec in `CriterionBundle.testing`,
exactly

    text + "".join(f"\n## Uses: {path}\n\n{doc}" for path, doc in uses)
         + "".join(f"\n## Asset kind: {kind}\n\n{guide}" for kind, guide in kinds)
         + "".join(f"\n## Test driver: {name}\n\n{guide}" for name, guide in drivers)

with `text` the file's full text as read, `""` when the component has no
`testing.md`; `uses` each `Uses:` path in order with that file's full
text; and `kinds` each asset kind the component declares, sorted, with
its definition's `## Test author guidance` section
(`specs/architecture/asset-kinds.md`); and `drivers` each declared test
driver, sorted, with its adapter's `guidance()["test_author"]`
(`specs/architecture/test-drivers.md`). `SpecBundle` never includes it, so the generator never
sees it.

## The criterion header

The first line of every generated test file is

    # hotdocs-criterion: sha256:<hex>

where `<hex>` is the lowercase hex SHA-256 of the UTF-8 encoding of

    json.dumps({"criterion_text": ..., "requirement_text": ...,
                "interface": ..., "glossary": ..., "testing": ...},
               sort_keys=True, ensure_ascii=False, separators=(",", ":"))

the five values taken from the criterion's `CriterionBundle`.
`dependency_interfaces` is deliberately left out: a dependency's
interface is reworded and re-versioned far more often than its call
shapes change, and a test whose fake no longer matches one is caught as
faulty by `test-probe`'s signature check (`R-PROBE-004`) before it runs.
The test author's own version is left out too: a test that breaks a
newer authoring rule fails its probe.

A cached test is current exactly when its first line is that header for
the criterion's bundle now. A test that is not current is stale and is
authored again; nothing else makes a current test stale.

## When a current test is authored again

Only when it is shown to be faulty, by one of:

1. **The probe.** `test-probe` reports it not `ok` (`R-SUPPLY-003`).
2. **The mutation sandbox.** It passed its criterion but fails when run
   alone in the mutation sandbox (Mutation runs, below): it depends on
   where it runs, not on the code.
3. **Repeated failure.** In a `generation-loop` run, its criterion
   failed with `failure_origin` `"implementation"` in two consecutive
   attempts with the test file unchanged, against two different
   candidates. The loop deletes the file before the next attempt, so it
   is authored again; at most once per criterion per run. The new test
   is written from the spec alone, so a correct test written again
   fails the wrong code again, and only a faulty one changes the
   outcome.

Each case authors the test once more within its limit and never more:
a test still faulty after that leaves its criterion `fail` with
`failure_origin` `"test"`.

## Mutation runs

A test that fails alone in the mutation sandbox is faulty; how it is
found is `specs/architecture/mutation-runs.md`'s "Faulty tests".
