"""Content-addressed cache store keyed by (spec_bundle_hash, gate_inputs_hash,
gate_version, model_pin). See interface/library.md and interface/cli.md."""

import contextlib
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union


KNOWN_GATE_TYPES = (
    "generator",
    "compiler",
    "generated_test",
    "llm_judge",
    "license_scanner",
    "secret_scanner",
)

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


class SchemaValidationError(ValueError):
    pass


class Miss:
    """Returned by get() on a definitive cache miss. Never None."""

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Miss)

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash("cache_manager.Miss")

    def __repr__(self) -> str:
        return "Miss()"


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


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _store_url() -> str:
    return os.environ.get("VAR_CACHE_STORE_URL", "") or ""


def _cache_dir(repo_root: Union[Path, str, None]) -> Path:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    return root / ".hotdocs" / "cache"


def _key_dict(cache_key: CacheKey) -> dict:
    return {
        "spec_bundle_hash": cache_key.spec_bundle_hash,
        "gate_inputs_hash": cache_key.gate_inputs_hash,
        "gate_version": cache_key.gate_version,
        "model_pin": cache_key.model_pin,
    }


def _key_id(cache_key: CacheKey) -> str:
    canonical = json.dumps(_key_dict(cache_key), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_result(cache_key: CacheKey, result: CachedResult) -> None:
    gate_version = cache_key.gate_version
    if "@" not in gate_version:
        raise SchemaValidationError(f"invalid gate_version: {gate_version!r}")
    key_gate_type = gate_version.split("@", 1)[0]
    if key_gate_type not in KNOWN_GATE_TYPES:
        raise SchemaValidationError(f"unknown gate type in gate_version: {key_gate_type!r}")
    if result.gate_type not in KNOWN_GATE_TYPES:
        raise SchemaValidationError(f"unknown result gate_type: {result.gate_type!r}")
    if result.gate_type != key_gate_type:
        raise SchemaValidationError(
            f"result gate_type {result.gate_type!r} does not match "
            f"key gate_type {key_gate_type!r}"
        )
    required = REQUIRED_PAYLOAD_KEYS[result.gate_type]
    payload = result.payload
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a dict")
    missing = [k for k in required if k not in payload]
    if missing:
        raise SchemaValidationError(
            f"payload for gate_type {result.gate_type!r} missing required keys: {missing}"
        )


def get(cache_key: CacheKey, *, repo_root: Union[Path, str, None] = None) -> Union[CachedResult, Miss]:
    if _store_url():
        return Miss()
    try:
        path = _cache_dir(repo_root) / f"{_key_id(cache_key)}.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data["cache_key"] != _key_dict(cache_key):
            return Miss()
        result_data = data["result"]
        return CachedResult(
            gate_type=result_data["gate_type"],
            payload=result_data["payload"],
            stored_at=result_data["stored_at"],
        )
    except Exception:
        return Miss()


def put(cache_key: CacheKey, result: CachedResult, *, repo_root: Union[Path, str, None] = None) -> None:
    _validate_result(cache_key, result)

    if _store_url():
        return None

    cache_dir = _cache_dir(repo_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_path = cache_dir / f"{_key_id(cache_key)}.json"

    data = {
        "cache_key": _key_dict(cache_key),
        "result": {
            "gate_type": result.gate_type,
            "payload": result.payload,
            "stored_at": result.stored_at,
        },
    }

    fd, tmp_path = tempfile.mkstemp(dir=str(cache_dir), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, target_path)
    except Exception:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        raise
    return None


def stats(*, repo_root: Union[Path, str, None] = None) -> dict:
    if _store_url():
        return {"entry_count": 0}
    cache_dir = _cache_dir(repo_root)
    try:
        count = sum(
            1
            for p in cache_dir.iterdir()
            if p.is_file() and p.suffix == ".json" and not p.name.startswith(".tmp-")
        )
    except OSError:
        count = 0
    return {"entry_count": count}


def _parse_flags(tokens: list, known: set):
    flags = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("--"):
            return None
        body = tok[2:]
        if not body:
            return None
        if "=" in body:
            name, value = body.split("=", 1)
            i += 1
        else:
            name = body
            i += 1
            if i >= len(tokens):
                return None
            value = tokens[i]
            i += 1
        if name not in known:
            return None
        flags[name] = value
    return flags


def main(argv: Union[list, None] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return 2

    command = argv[0]
    rest = argv[1:]

    if command == "inspect":
        known = {
            "spec-bundle-hash",
            "gate-inputs-hash",
            "gate-version",
            "model-pin",
            "repo-root",
        }
        required = {"spec-bundle-hash", "gate-inputs-hash", "gate-version", "model-pin"}
        flags = _parse_flags(rest, known)
        if flags is None:
            return 2
        if required - flags.keys():
            return 2

        repo_root = flags.get("repo-root")
        cache_key = CacheKey(
            spec_bundle_hash=flags["spec-bundle-hash"],
            gate_inputs_hash=flags["gate-inputs-hash"],
            gate_version=flags["gate-version"],
            model_pin=flags["model-pin"],
        )
        result = get(cache_key, repo_root=repo_root)
        if isinstance(result, Miss):
            print(json.dumps({"result": "miss"}))
        else:
            print(
                json.dumps(
                    {
                        "result": "hit",
                        "gate_type": result.gate_type,
                        "stored_at": result.stored_at,
                    }
                )
            )
        return 0

    elif command == "stats":
        known = {"repo-root"}
        flags = _parse_flags(rest, known)
        if flags is None:
            return 2
        repo_root = flags.get("repo-root")
        result = stats(repo_root=repo_root)
        print(json.dumps({"entry_count": result["entry_count"]}))
        return 0

    else:
        return 2