"""Content-addressed gate cache (comp-cache-manager).

A dumb, trustworthy get/put store keyed by the 4-tuple
(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin).

When the environment variable VAR_CACHE_STORE_URL is unset or empty, entries
live in a local file-based store under <repo_root>/.hotdocs/cache/, one JSON
file per key, written atomically (temp file + os.replace) so concurrent
writers follow last-write-wins without corruption.  When it is set, no
shared-store client exists yet: get always misses and put validates and then
stores nothing.
"""

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STORE_URL_ENV = "VAR_CACHE_STORE_URL"

REQUIRED_PAYLOAD_KEYS = {
    "generator": ("component_id", "model", "prompt_version", "files"),
    "compiler": ("outputs", "gate_version", "summary"),
    "generated_test": ("component_id", "criterion_id", "model", "file"),
    "llm_judge": ("result", "rationale"),
    "license_scanner": (
        "component_id",
        "gate_version",
        "similarity_score",
        "blocked",
        "matches",
    ),
    "secret_scanner": ("scope", "gate_version", "flagged", "matches"),
}

KEY_FIELDS = ("spec_bundle_hash", "gate_inputs_hash", "gate_version", "model_pin")


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    """A definitive cache miss. Any two instances compare equal."""

    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash(Miss)

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    """Raised by put when a result's shape does not match its key's gate type."""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _store_url_set() -> bool:
    return bool(os.environ.get(STORE_URL_ENV))


def _cache_dir(repo_root) -> Path:
    root = Path.cwd() if repo_root is None else Path(repo_root)
    return root / ".hotdocs" / "cache"


def _key_fields(cache_key: CacheKey) -> list:
    return [getattr(cache_key, name) for name in KEY_FIELDS]


def _key_digest(cache_key: CacheKey) -> str:
    encoded = json.dumps(_key_fields(cache_key), separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _entry_path(cache_key: CacheKey, repo_root) -> Path:
    return _cache_dir(repo_root) / (_key_digest(cache_key) + ".json")


def _validate(cache_key: CacheKey, result: CachedResult) -> None:
    gate_type = cache_key.gate_version.split("@", 1)[0]
    required = REQUIRED_PAYLOAD_KEYS.get(gate_type)
    if required is None:
        raise SchemaValidationError(f"unknown gate type {gate_type!r}")
    if result.gate_type != gate_type:
        raise SchemaValidationError(
            f"result gate_type {result.gate_type!r} does not match key gate type {gate_type!r}"
        )
    payload = result.payload
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a mapping")
    missing = [k for k in required if k not in payload]
    if missing:
        raise SchemaValidationError(
            f"payload for gate type {gate_type!r} missing required keys: {missing}"
        )


def get(cache_key: CacheKey, *, repo_root: Path = None):
    if _store_url_set():
        return Miss()
    try:
        with open(_entry_path(cache_key, repo_root), "r", encoding="utf-8") as fh:
            stored = json.load(fh)["result"]
        return CachedResult(
            gate_type=stored["gate_type"],
            payload=stored["payload"],
            stored_at=stored["stored_at"],
        )
    except Exception:
        return Miss()


def put(cache_key: CacheKey, result: CachedResult, *, repo_root: Path = None) -> None:
    _validate(cache_key, result)
    if _store_url_set():
        return
    cache_dir = _cache_dir(repo_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "key": dict(zip(KEY_FIELDS, _key_fields(cache_key))),
        "result": {
            "gate_type": result.gate_type,
            "payload": result.payload,
            "stored_at": result.stored_at,
        },
    }
    fd, tmp_path = tempfile.mkstemp(dir=cache_dir, prefix=".", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(entry, fh)
    os.replace(tmp_path, _entry_path(cache_key, repo_root))


def stats(*, repo_root: Path = None) -> dict:
    if _store_url_set():
        return {"entry_count": 0}
    return {"entry_count": len(list(_cache_dir(repo_root).glob("*.json")))}


def _parse_flags(tokens, allowed):
    flags = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token.startswith("--"):
            return None
        name, eq, value = token[2:].partition("=")
        if name not in allowed:
            return None
        if not eq:
            i += 1
            if i >= len(tokens):
                return None
            value = tokens[i]
        flags[name] = value
        i += 1
    return flags


_INSPECT_KEY_FLAGS = ("spec-bundle-hash", "gate-inputs-hash", "gate-version", "model-pin")


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if not args:
        return 2
    command, rest = args[0], args[1:]
    if command == "inspect":
        flags = _parse_flags(rest, _INSPECT_KEY_FLAGS + ("repo-root",))
        if flags is None or any(f not in flags for f in _INSPECT_KEY_FLAGS):
            return 2
        key = CacheKey(**{f.replace("-", "_"): flags[f] for f in _INSPECT_KEY_FLAGS})
        found = get(key, repo_root=Path(flags.get("repo-root", ".")))
        if isinstance(found, Miss):
            out = {"result": "miss"}
        else:
            out = {"result": "hit", "gate_type": found.gate_type, "stored_at": found.stored_at}
        print(json.dumps(out))
        return 0
    if command == "stats":
        flags = _parse_flags(rest, ("repo-root",))
        if flags is None:
            return 2
        print(json.dumps(stats(repo_root=Path(flags.get("repo-root", ".")))))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())