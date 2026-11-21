"""Cache Manager: a content-addressed get/put store for gate results."""

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "CacheKey",
    "CachedResult",
    "Miss",
    "SchemaValidationError",
    "get",
    "put",
    "now_iso",
    "stats",
    "main",
]

_ENV_VAR = "VAR_CACHE_STORE_URL"

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
    """A definitive cache miss."""

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


def _shared_store_configured() -> bool:
    return bool(os.environ.get(_ENV_VAR))


def _cache_dir(repo_root) -> Path:
    root = Path.cwd() if repo_root is None else Path(repo_root)
    return root / ".hotdocs" / "cache"


def _entry_path(cache_key: CacheKey, repo_root) -> Path:
    material = json.dumps(
        [
            cache_key.spec_bundle_hash,
            cache_key.gate_inputs_hash,
            cache_key.gate_version,
            cache_key.model_pin,
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return _cache_dir(repo_root) / (digest + ".json")


def _validate(cache_key: CacheKey, result: CachedResult) -> None:
    key_gate_type = cache_key.gate_version.split("@", 1)[0]
    if key_gate_type not in REQUIRED_PAYLOAD_KEYS:
        raise SchemaValidationError(f"unknown gate type: {key_gate_type!r}")
    if result.gate_type != key_gate_type:
        raise SchemaValidationError(
            f"result gate_type {result.gate_type!r} does not match key gate type "
            f"{key_gate_type!r}"
        )
    payload = result.payload
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a mapping")
    missing = [k for k in REQUIRED_PAYLOAD_KEYS[key_gate_type] if k not in payload]
    if missing:
        raise SchemaValidationError(
            f"payload for {key_gate_type!r} is missing required keys: {missing}"
        )


def get(cache_key: CacheKey, *, repo_root: Path = None):
    if _shared_store_configured():
        return Miss()
    try:
        path = _entry_path(cache_key, repo_root)
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return CachedResult(
            gate_type=data["gate_type"],
            payload=data["payload"],
            stored_at=data["stored_at"],
        )
    except Exception:
        return Miss()


def put(cache_key: CacheKey, result: CachedResult, *, repo_root: Path = None) -> None:
    _validate(cache_key, result)
    if _shared_store_configured():
        return None
    path = _entry_path(cache_key, repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(
        {
            "gate_type": result.gate_type,
            "payload": result.payload,
            "stored_at": result.stored_at,
        }
    )
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return None


def stats(*, repo_root: Path = None) -> dict:
    if _shared_store_configured():
        return {"entry_count": 0}
    return {"entry_count": len(list(_cache_dir(repo_root).glob("*.json")))}


_GENERAL_USAGE = "usage: python -m cache_manager {inspect,stats} ..."
_INSPECT_USAGE = (
    "usage: python -m cache_manager inspect --spec-bundle-hash=<h> "
    "--gate-inputs-hash=<h> --gate-version=<v> --model-pin=<p> [--repo-root=<dir>]"
)
_STATS_USAGE = "usage: python -m cache_manager stats [--repo-root=<dir>]"

_INSPECT_REQUIRED = (
    "--spec-bundle-hash",
    "--gate-inputs-hash",
    "--gate-version",
    "--model-pin",
)


class _UsageError(Exception):
    pass


def _usage_error(cause: str, usage: str) -> int:
    sys.stderr.write(f"usage error: {cause}\n")
    sys.stderr.write(usage + "\n")
    return 2


def _parse_flags(tokens, allowed):
    values = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, sep, value = token.partition("=")
        if name not in allowed:
            raise _UsageError(f"unknown argument: {token}")
        if not sep:
            if i + 1 >= len(tokens):
                raise _UsageError(f"flag {name} requires a value")
            i += 1
            value = tokens[i]
        values[name] = value
        i += 1
    return values


def main(argv: list = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv:
        return _usage_error("no subcommand given", _GENERAL_USAGE)
    command, rest = argv[0], argv[1:]

    if command == "inspect":
        try:
            flags = _parse_flags(rest, set(_INSPECT_REQUIRED) | {"--repo-root"})
        except _UsageError as exc:
            return _usage_error(str(exc), _INSPECT_USAGE)
        missing = [f for f in _INSPECT_REQUIRED if f not in flags]
        if missing:
            return _usage_error(
                f"missing required flag: {missing[0]}", _INSPECT_USAGE
            )
        key = CacheKey(
            spec_bundle_hash=flags["--spec-bundle-hash"],
            gate_inputs_hash=flags["--gate-inputs-hash"],
            gate_version=flags["--gate-version"],
            model_pin=flags["--model-pin"],
        )
        result = get(key, repo_root=Path(flags.get("--repo-root", ".")))
        if isinstance(result, Miss):
            out = {"result": "miss"}
        else:
            out = {
                "result": "hit",
                "gate_type": result.gate_type,
                "stored_at": result.stored_at,
            }
        sys.stdout.write(json.dumps(out) + "\n")
        return 0

    if command == "stats":
        try:
            flags = _parse_flags(rest, {"--repo-root"})
        except _UsageError as exc:
            return _usage_error(str(exc), _STATS_USAGE)
        sys.stdout.write(
            json.dumps(stats(repo_root=Path(flags.get("--repo-root", ".")))) + "\n"
        )
        return 0

    return _usage_error(f"unknown subcommand: {command}", _GENERAL_USAGE)


if __name__ == "__main__":
    sys.exit(main())
