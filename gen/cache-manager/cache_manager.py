"""Content-addressed gate cache (comp-cache-manager).

Library: get / put / now_iso / stats, plus the CacheKey / CachedResult
dataclasses, the Miss sentinel class and SchemaValidationError.
CLI: ``python -m cache_manager inspect ...`` / ``python -m cache_manager stats``.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_STORE_URL_ENV = "VAR_CACHE_STORE_URL"

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


class SchemaValidationError(ValueError):
    """Raised by put when a result's shape doesn't match its gate type."""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _shared_store_configured() -> bool:
    return bool(os.environ.get(_STORE_URL_ENV))


def _cache_dir(repo_root) -> Path:
    root = Path.cwd() if repo_root is None else Path(repo_root)
    return root / ".hotdocs" / "cache"


def _key_digest(cache_key: CacheKey) -> str:
    material = json.dumps(
        [
            cache_key.spec_bundle_hash,
            cache_key.gate_inputs_hash,
            cache_key.gate_version,
            cache_key.model_pin,
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _validate(cache_key: CacheKey, result: CachedResult) -> None:
    key_gate_type = cache_key.gate_version.partition("@")[0]
    if result.gate_type != key_gate_type:
        raise SchemaValidationError(
            f"result gate_type {result.gate_type!r} does not match "
            f"gate_version {cache_key.gate_version!r}"
        )
    required = _REQUIRED_PAYLOAD_KEYS.get(result.gate_type)
    if required is None:
        raise SchemaValidationError(f"unknown gate_type {result.gate_type!r}")
    payload = result.payload
    if not isinstance(payload, dict):
        raise SchemaValidationError(
            f"payload for {result.gate_type!r} must be a mapping"
        )
    missing = [k for k in required if k not in payload]
    if missing:
        raise SchemaValidationError(
            f"payload for {result.gate_type!r} missing required keys: {missing}"
        )


def get(cache_key: CacheKey, *, repo_root: Path = None):
    try:
        if _shared_store_configured():
            return Miss()
        path = _cache_dir(repo_root) / f"{_key_digest(cache_key)}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
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
    directory = _cache_dir(repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{_key_digest(cache_key)}.json"
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(asdict(result), handle)
    os.replace(tmp_path, target)
    return None


def stats(*, repo_root: Path = None) -> dict:
    if _shared_store_configured():
        return {"entry_count": 0}
    return {"entry_count": len(list(_cache_dir(repo_root).glob("*.json")))}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cache_manager", allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", allow_abbrev=False)
    inspect_parser.add_argument("--spec-bundle-hash", required=True)
    inspect_parser.add_argument("--gate-inputs-hash", required=True)
    inspect_parser.add_argument("--gate-version", required=True)
    inspect_parser.add_argument("--model-pin", required=True)
    inspect_parser.add_argument("--repo-root", default=".")

    stats_parser = subparsers.add_parser("stats", allow_abbrev=False)
    stats_parser.add_argument("--repo-root", default=".")

    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return 2

    repo_root = Path(args.repo_root)
    if args.command == "inspect":
        key = CacheKey(
            spec_bundle_hash=args.spec_bundle_hash,
            gate_inputs_hash=args.gate_inputs_hash,
            gate_version=args.gate_version,
            model_pin=args.model_pin,
        )
        found = get(key, repo_root=repo_root)
        if isinstance(found, Miss):
            output = {"result": "miss"}
        else:
            output = {
                "result": "hit",
                "gate_type": found.gate_type,
                "stored_at": found.stored_at,
            }
    else:
        output = stats(repo_root=repo_root)

    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
