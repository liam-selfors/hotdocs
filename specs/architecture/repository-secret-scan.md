---
id: arch-repository-secret-scan
title: The Repository Secret Scan
status: draft
owners: [pipeline-team]
depends_on: []
---

# The Repository Secret Scan

## Purpose

`secret-scanner`'s `scan(repo_root)` reads every file under the
repository and its allowlist (`R-SECRET-001`, `R-SECRET-012`), so its
result describes the repository at the moment it runs, never one
component. The scan a component's provenance records is the one its
generation ran; once any file or the allowlist changes, that record is
history, not an answer. `hotdocs verify` therefore scans the repository
afresh, once, and reads no component's stored scan (`D371`).

## In `check_readiness`

When the resolved scope holds at least one component and no
`precondition_error`, `provenance-tracker`'s `check_readiness` calls
`secret-scanner`'s `scan(repo_root)` exactly once, after every component
and capability check, passing `repo_root` exactly as `check_readiness`
received it. `secret-scanner` is loaded at that point only, as
`R-TRACK-011` loads every dependency, from
`<repo_root>/gen/secret-scanner/secret_scanner.py`, else the tool root's
copy (`D199`). An empty scope, or one with a `precondition_error`, never
loads it.

`VerifyReport.secret_scan` is the result's `to_dict()` when it has one,
else the result itself, and `null` when `scan` was not called.

The result's `flagged` and `matches`, and each match's `file`, `line`
and `rule_id`, are read with dual dict-or-attribute access. When
`flagged` is true, `ready` is false and the last `not_ready_reasons`
entry is exactly `secret_scan flagged: ` followed by each match as
`<file>:<line> <rule_id>`, in `matches` order, joined by `, `.

When loading `secret-scanner` or calling `scan` raises, `secret_scan`
is `null`, `ready` is false and the last entry is exactly
`secret_scan unavailable: <exception class name>: <message>`; the
exception is never raised to the caller.

A component's own `secret_scan`, in its `ProvenanceCheckResult`, is
copied into `components` verbatim and never read: no component's
`not_ready_reasons` entry names `secret_scan`. A sealed component's
check is unchanged (`R-TRACK-009`).

The scan writes only what `secret-scanner` itself writes, its
`cache-manager` entry under `.hotdocs/`, and may notify
`VAR-COMPLIANCE-WEBHOOK-URL` as `R-SECRET-004` says: the one network
call the component half of `check_readiness` can make.

## Test fixtures

Every test whose real `check_readiness` call reaches the scan (a scope
holding a component, no `precondition_error`) writes a stand-in
`<repo_root>/gen/secret-scanner/secret_scanner.py` whose `scan(repo_root)`
appends `str(repo_root)` to a log file and returns the dict
`{"flagged": false, "matches": []}`, unless the test says otherwise; no
test runs the real scanner, which would read the test's own stand-ins. A flagged stand-in returns
`{"flagged": true, "matches": [{"file": "a/b.py", "line": 3, "rule_id":
"AWS Access Key", "risk_tier": "high"}]}`, whose entry is
`secret_scan flagged: a/b.py:3 AWS Access Key`.
