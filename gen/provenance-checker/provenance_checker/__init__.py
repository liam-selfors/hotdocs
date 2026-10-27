"""Provenance Checker (comp-provenance-checker).

Decides whether a component's already-committed `.provenance.json`
proves it was already verified against the exact spec state a merge is
currently checking, per `specs/components/provenance-checker/`.

Public surface:
  - `ProvenanceCheckResult` — the data shape returned by a check.
  - `check_provenance` — the pure library entry point.
  - `main` — the `hotdocs provenance check` CLI entry point.
"""

from .core import ProvenanceCheckResult, check_provenance
from .cli import main

__all__ = ["ProvenanceCheckResult", "check_provenance", "main"]