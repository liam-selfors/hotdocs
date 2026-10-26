"""cache-manager — bootstrap implementation.

HAND-AUTHORED BOOTSTRAP (fifth instance of the same honest exception;
see verification/cache-manager/BOOTSTRAP.md) -- unlike llm-endpoint,
this one is a temporary exception, not a permanent one: nothing stops
a real generator from cold-regenerating this component later, now that
a real generator exists (D47 built llm-endpoint; the generator itself
is still hand-bootstrapped as of this file).

Implements R-CACHE-001..009: a content-addressed get/put store keyed by
(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin), with a
local-file fallback under .hotdocs/cache/ when VAR-CACHE-STORE-URL is
absent (R-CACHE-009) -- the only backing this v1 implements (D18/D20:
no real shared store exists in this project to target yet).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CACHE_DIR_RELATIVE = Path(".hotdocs") / "cache"

# R-CACHE-007: a minimal, deliberately shallow shape fingerprint per known
# gate_type -- just enough to reject an obviously-wrong payload (e.g. a
# LintReport under a license_scanner gate_version), not a full JSON-schema
# validator nothing in this corpus needs yet (D18/D20).
_REQUIRED_PAYLOAD_KEYS: dict[str, frozenset[str]] = {
    "generator": frozenset({"component_id", "model", "prompt_version", "files"}),
    "compiler": frozenset({"outputs", "gate_version", "summary"}),
    "generated_test": frozenset({"component_id", "criterion_id", "model", "file"}),
    "llm_judge": frozenset({"result", "rationale"}),
    "license_scanner": frozenset({"component_id", "gate_version", "similarity_score", "blocked", "matches"}),
    "secret_scanner": frozenset({"scope", "gate_version", "flagged", "matches"}),
}


class Miss:
    """R-CACHE-001 -- a definitive miss, never an approximation. A
    distinct type (not None, not an exception) so a caller's `isinstance`
    check can never be confused with a legitimate falsy stored payload."""

    def __repr__(self) -> str:
        return "Miss()"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Miss)


MISS = Miss()


class SchemaValidationError(Exception):
    """R-CACHE-007 -- put() raises, never silently no-ops, on a payload
    shape mismatch for the cache_key's declared gate_version."""


@dataclass(frozen=True)
class CacheKey:
    """Matches `interface/data/CacheKey.md` exactly."""

    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str

    def gate_type(self) -> str:
        """`gate_version` is `"<gate_type>@<semver>"` (every example in
        CacheKey.md/CachedResult.md follows this shape) -- the type
        R-CACHE-007 validates against is the part before `@`."""
        return self.gate_version.split("@", 1)[0]

    def serialized(self) -> str:
        """R-CACHE-002 -- byte-identical regardless of caller: a fixed
        field order and separators, not whatever a generic dict-ordering
        default would happen to produce."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.serialized().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CachedResult:
    """Matches `interface/data/CachedResult.md` exactly."""

    gate_type: str
    payload: dict[str, Any]
    stored_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"gate_type": self.gate_type, "payload": self.payload, "stored_at": self.stored_at}


def _cache_dir(repo_root: Path | None) -> Path:
    root = repo_root if repo_root is not None else Path.cwd()
    return root / _CACHE_DIR_RELATIVE


def _entry_path(cache_key: CacheKey, repo_root: Path | None) -> Path:
    return _cache_dir(repo_root) / f"{cache_key.digest()}.json"


def get(cache_key: CacheKey, *, repo_root: Path | None = None) -> CachedResult | Miss:
    """R-CACHE-001/004/005/009. `repo_root` is an added parameter (D48,
    the same pre-existing-gap pattern llm-endpoint's `backend` and
    provenance-writer's `ProvenanceInputs` already found) -- the CLI's
    own `--repo-root` flag implied this all along; the original
    `interface/library.md` signature just never wrote it down."""

    # R-CACHE-009: an unset VAR-CACHE-STORE-URL means the local fallback;
    # a set one names a backing this v1 has no client for at all (D18/
    # D20 -- no real shared store exists to target yet), which this
    # component treats the same way any other unreachable store is
    # treated: R-CACHE-004's fail-to-miss, never a crash.
    if os.environ.get("VAR_CACHE_STORE_URL"):
        return MISS

    path = _entry_path(cache_key, repo_root)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return MISS
    return CachedResult(
        gate_type=data["result"]["gate_type"],
        payload=data["result"]["payload"],
        stored_at=data["result"]["stored_at"],
    )


def put(cache_key: CacheKey, result: CachedResult, *, repo_root: Path | None = None) -> None:
    """R-CACHE-003/007/009. Validates shape before writing (R-CACHE-007);
    writes via a temp-file-then-atomic-rename (G-CACHE-001/R-CACHE-003) --
    concurrent writers each complete a full, uncorrupted write, and
    whichever `os.replace` lands last is the one a later `get` returns."""

    _validate_payload_shape(cache_key, result)

    if os.environ.get("VAR_CACHE_STORE_URL"):
        return  # same unsupported-backing posture as get() above

    cache_dir = _cache_dir(repo_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    entry = {"key": asdict(cache_key), "result": result.to_dict()}

    final_path = _entry_path(cache_key, repo_root)
    # A per-call-unique temp name, not just pid -- concurrent *threads* in
    # one process share a pid, and a shared temp name was a real bug this
    # test suite caught: two threads could race on the same tmp_path and
    # FileNotFoundError on os.replace once the other thread's replace had
    # already consumed it.
    tmp_path = cache_dir / f".{final_path.stem}.{uuid.uuid4().hex}.tmp"
    tmp_path.write_text(json.dumps(entry), encoding="utf-8")
    os.replace(tmp_path, final_path)  # atomic on POSIX -- never a partial file


def _validate_payload_shape(cache_key: CacheKey, result: CachedResult) -> None:
    expected_type = cache_key.gate_type()
    if result.gate_type != expected_type:
        raise SchemaValidationError(
            f"result.gate_type {result.gate_type!r} does not match "
            f"cache_key.gate_version's gate type {expected_type!r}"
        )
    required = _REQUIRED_PAYLOAD_KEYS.get(expected_type)
    if required is None:
        raise SchemaValidationError(f"unknown gate type {expected_type!r}")
    missing = required - result.payload.keys()
    if missing:
        raise SchemaValidationError(
            f"payload for gate type {expected_type!r} is missing required "
            f"key(s): {sorted(missing)}"
        )


def stats(*, repo_root: Path | None = None) -> dict[str, int]:
    """R-CACHE-006's `stats` subcommand. This implementation reports the
    local store's current entry count only -- no persistent cumulative
    hit/miss counter exists anywhere in this corpus's own spec (no
    interface/data/ schema defines one), so this is a minimal, honest
    reading of what R-CACHE-006 asks for, not the richer "hit rate over
    time" metric notes/metrics.md eventually wants; see BOOTSTRAP.md."""

    cache_dir = _cache_dir(repo_root)
    if not cache_dir.is_dir():
        return {"entry_count": 0}
    return {"entry_count": sum(1 for _ in cache_dir.glob("*.json"))}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
