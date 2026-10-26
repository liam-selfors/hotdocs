"""
R-ENDPOINT-006's call log: one record per `complete()` dispatch, written
to `.hotdocs/calls/` -- gitignored, local-only, non-gating
(SPEC_GUIDELINES.md §1, constraints.md), never read by any gate's
pass/fail decision.

Deliberately lower-level than anything a caller separately persists
about its own attempt (D32): this answers "how many calls, to which
backend, with what error rate" across the whole pipeline, independent of
which component's semantics any individual call served. It never carries
prompt/response content or a credential -- only whether `text` was
present, and the full `model_call_error` object on failure.
"""

import datetime
import json
import os
import uuid

_CALL_LOG_DIR = os.path.join(".hotdocs", "calls")


def write_call_record(*, model, backend, text_present, model_call_error):
    """
    Write one call record before `complete()` returns to its caller.
    Best-effort directory creation only -- this is a local write side
    effect, not a gate input, so it must never be what makes a `complete()`
    call itself fail.
    """
    os.makedirs(_CALL_LOG_DIR, exist_ok=True)

    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": model,
        "backend": backend,
        "text_present": bool(text_present),
        "model_call_error": model_call_error,
    }

    path = os.path.join(_CALL_LOG_DIR, f"{uuid.uuid4().hex}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
        handle.write("\n")