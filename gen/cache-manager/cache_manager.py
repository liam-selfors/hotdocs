"""Cache Manager: a content-addressed get/put store for gate results.

Keyed by (spec_bundle_hash, gate_inputs_hash, gate_version, model_pin).
Backed by a local file store under ``<repo_root>/.hotdocs/cache/`` when
``VAR_CACHE_STORE_URL`` is absent; when it is set, no shared-store client
exists yet, so every ``get`` is a miss and ``put`` stores nothing.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
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

_STORE_URL_ENV = "VAR_CACHE_STORE_URL"
_CACHE_SUBDIR = Path(".hotdocs") / "cache"
_ENTRY_SUFFIX = ".json"

_REQUIRED_PAYLOAD_KEYS = {
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
    """A definitive cache miss. Any two instances compare equal."""

    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash(Miss)

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    """Raised by ``put`` when a result does not match its gate's schema."""


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _shared_store_configured() -> bool:
    return bool(os.environ.get(_STORE_URL_ENV))


def _cache_dir(repo_root) -> Path:
    root = Path.cwd() if repo_root is None else Path(repo_root)
    return root / _CACHE_SUBDIR


def _key_digest(cache_key: CacheKey) -> str:
    canonical = json.dumps(
        [
            cache_key.spec_bundle_hash,
            cache_key.gate_inputs_hash,
            cache_key.gate_version,
            cache_key.model_pin,
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _entry_path(cache_key: CacheKey, repo_root) -> Path:
    return _cache_dir(repo_root) / (_key_digest(cache_key) + _ENTRY_SUFFIX)


def _validate(cache_key: CacheKey, result: CachedResult) -> None:
    key_gate_type = cache_key.gate_version.split("@", 1)[0]
    if result.gate_type != key_gate_type:
        raise SchemaValidationError(
            f"result gate_type {result.gate_type!r} does not match key "
            f"gate type {key_gate_type!r}"
        )
    required = _REQUIRED_PAYLOAD_KEYS.get(result.gate_type)
    if required is None:
        raise SchemaValidationError(f"unknown gate_type {result.gate_type!r}")
    payload = result.payload
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a JSON object")
    missing = [k for k in required if k not in payload]
    if missing:
        raise SchemaValidationError(
            f"payload for {result.gate_type!r} missing required keys: "
            + ", ".join(missing)
        )


def get(cache_key: CacheKey, *, repo_root: Path = None):
    try:
        if _shared_store_configured():
            return Miss()
        path = _entry_path(cache_key, repo_root)
        if not path.is_file():
            return Miss()
        data = json.loads(path.read_text(encoding="utf-8"))
        return CachedResult(**data)
    except Exception:
        return Miss()


def put(cache_key: CacheKey, result: CachedResult, *, repo_root: Path = None) -> None:
    _validate(cache_key, result)
    if _shared_store_configured():
        return
    path = _entry_path(cache_key, repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        {
            "gate_type": result.gate_type,
            "payload": result.payload,
            "stored_at": result.stored_at,
        },
        sort_keys=True,
    )
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def stats(*, repo_root: Path = None) -> dict:
    if _shared_store_configured():
        return {"entry_count": 0}
    directory = _cache_dir(repo_root)
    if not directory.is_dir():
        return {"entry_count": 0}
    count = sum(
        1 for p in directory.iterdir() if p.is_file() and p.suffix == _ENTRY_SUFFIX
    )
    return {"entry_count": count}


# ---------------------------------------------------------------- CLI

_GENERAL_USAGE = "usage: python -m cache_manager {inspect,stats} [options]"
_USAGE = {
    "inspect": (
        "usage: python -m cache_manager inspect --spec-bundle-hash=<h> "
        "--gate-inputs-hash=<h> --gate-version=<v> --model-pin=<p> "
        "[--repo-root=<dir>]"
    ),
    "stats": "usage: python -m cache_manager stats [--repo-root=<dir>]",
}
_FLAGS = {
    "inspect": (
        "spec-bundle-hash",
        "gate-inputs-hash",
        "gate-version",
        "model-pin",
        "repo-root",
    ),
    "stats": ("repo-root",),
}
_REQUIRED = {
    "inspect": ("spec-bundle-hash", "gate-inputs-hash", "gate-version", "model-pin"),
    "stats": (),
}


class _UsageError(Exception):
    pass


def _usage_error(cause: str, usage: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _parse_flags(command: str, tokens: list) -> dict:
    allowed = _FLAGS[command]
    values = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token.startswith("--"):
            raise _UsageError(f"unknown argument {token!r}")
        body = token[2:]
        if "=" in body:
            name, value = body.split("=", 1)
            if name not in allowed:
                raise _UsageError(f"unknown argument '--{name}'")
        else:
            name = body
            if name not in allowed:
                raise _UsageError(f"unknown argument {token!r}")
            if i + 1 >= len(tokens):
                raise _UsageError(f"flag {token!r} requires a value")
            i += 1
            value = tokens[i]
        values[name] = value
        i += 1
    for name in _REQUIRED[command]:
        if name not in values:
            raise _UsageError(f"missing required flag '--{name}'")
    return values


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if not argv:
        return _usage_error("no subcommand given", _GENERAL_USAGE)
    command = argv[0]
    if command not in _FLAGS:
        return _usage_error(f"unknown subcommand {command!r}", _GENERAL_USAGE)
    try:
        values = _parse_flags(command, argv[1:])
    except _UsageError as exc:
        return _usage_error(str(exc), _USAGE[command])

    repo_root = Path(values.get("repo-root", "."))
    if command == "stats":
        print(json.dumps(stats(repo_root=repo_root)))
        return 0

    key = CacheKey(
        spec_bundle_hash=values["spec-bundle-hash"],
        gate_inputs_hash=values["gate-inputs-hash"],
        gate_version=values["gate-version"],
        model_pin=values["model-pin"],
    )
    found = get(key, repo_root=repo_root)
    if isinstance(found, Miss):
        print(json.dumps({"result": "miss"}))
    else:
        print(
            json.dumps(
                {
                    "result": "hit",
                    "gate_type": found.gate_type,
                    "stored_at": found.stored_at,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
