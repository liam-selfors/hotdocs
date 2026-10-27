"""
comp-license-scanner — deterministic k-gram license fingerprint scanner.

Implements the behavior described by the SpecBundle for `comp-license-scanner`
(requirements R-LICENSE-001..007, interface/cli.md, interface/library.md,
interface/data/LicenseScanResult.md, constraints.md). This file is the
generated implementation; it is not itself spec text.

Public API:
    scan(component_id: str, repo_root: Path) -> LicenseScanResult
    main(argv=None) -> int                      # CLI entry point

No model calls are made anywhere in this module (constraints.md: "No model
calls" — same trust tier as spec-linter/impact-analyzer/cache-manager).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import socket
import sys
import types
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = ["scan", "LicenseScanResult", "main"]

# ---------------------------------------------------------------------------
# Constants (this component's own implementation choices, not spec-dictated
# literal values beyond what R-LICENSE-001/005 pin down: 9-token windows and
# "corpus version is part of gate_version").
# ---------------------------------------------------------------------------

SCANNER_NAME = "license_scanner"
CODE_VERSION = "3.1"  # this scanner's own code version component
DEFAULT_BLOCK_THRESHOLD = 0.70
REPORTING_FLOOR = 0.30
K_GRAM_SIZE = 9  # R-LICENSE-001: 9-token windows
NO_MODEL_PIN = "none"  # constraints.md: no model calls are ever made
WEBHOOK_TIMEOUT_SECONDS = 10

VAR_CORPUS_PATH = "VAR-LICENSE-CORPUS-PATH"
VAR_WEBHOOK_URL = "VAR-COMPLIANCE-WEBHOOK-URL"


# ---------------------------------------------------------------------------
# Result shape (interface/data/LicenseScanResult.md)
# ---------------------------------------------------------------------------


@dataclass
class LicenseScanResult:
    component_id: str
    gate_version: str
    similarity_score: float
    block_threshold: float
    blocked: bool
    matches: List[Dict[str, Any]] = field(default_factory=list)
    notified: bool = False
    notification_delivery_error: Optional[Dict[str, str]] = None
    cache_hit: bool = False


# ---------------------------------------------------------------------------
# Dependency loading: comp-cache-manager
#
# cache-manager lives under gen/cache-manager/ (either a flat module
# cache_manager.py or a package cache_manager/__init__.py). It is not a
# static import target from this file's own location in general (the
# dependency's repo_root may differ from this file's install location), so
# it is located and loaded dynamically from the filesystem. The loaded
# module is registered in sys.modules under its load-time name
# ("cache_manager") BEFORE exec_module runs it, so any dataclasses it
# defines can resolve sys.modules[cls.__module__] during class-body
# execution.
# ---------------------------------------------------------------------------


def _try_load_module_from_dir(component_dir: Path, module_name: str):
    if component_dir is None or not component_dir.exists():
        return None
    flat = component_dir / f"{module_name}.py"
    pkg_init = component_dir / module_name / "__init__.py"
    spec = None
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    elif pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            module_name,
            pkg_init,
            submodule_search_locations=[str(component_dir / module_name)],
        )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # MUST be registered before exec_module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        return None
    return module


def _load_cache_manager_module(repo_root: Optional[Path]):
    if "cache_manager" in sys.modules:
        return sys.modules["cache_manager"]

    candidates: List[Path] = []
    if repo_root is not None:
        candidates.append(Path(repo_root) / "gen" / "cache-manager")

    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            candidates.append(parent / "cache-manager")
            break

    for candidate in candidates:
        module = _try_load_module_from_dir(candidate, "cache_manager")
        if module is not None:
            return module
    return None


def _build_fallback_cache_manager():
    """
    Degenerate in-process stand-in used only if the real cache-manager
    component cannot be located on disk. Keeps scan() functional (so a
    missing dependency never turns into a crash or a skipped scan) while
    still faithfully reporting cache_hit based on its own (process-local)
    state.
    """
    ns = types.SimpleNamespace()

    @dataclass
    class CacheKey:
        spec_bundle_hash: str
        gate_inputs_hash: str
        gate_version: str
        model_pin: str

    @dataclass
    class CachedResult:
        gate_type: str
        payload: Dict[str, Any]
        stored_at: str

    class Miss:
        pass

    class SchemaValidationError(Exception):
        pass

    _store: Dict[Any, Any] = {}

    def _key_tuple(key: "CacheKey"):
        return (
            key.spec_bundle_hash,
            key.gate_inputs_hash,
            key.gate_version,
            key.model_pin,
        )

    def get(cache_key, *, repo_root=None):
        return _store.get(_key_tuple(cache_key), Miss())

    def put(cache_key, result, *, repo_root=None):
        _store[_key_tuple(cache_key)] = result

    def now_iso():
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def stats(*, repo_root=None):
        return {"hits": 0, "misses": 0}

    ns.CacheKey = CacheKey
    ns.CachedResult = CachedResult
    ns.Miss = Miss
    ns.SchemaValidationError = SchemaValidationError
    ns.get = get
    ns.put = put
    ns.now_iso = now_iso
    ns.stats = stats
    return ns


def _get_cache_manager(repo_root: Optional[Path]):
    module = _load_cache_manager_module(repo_root)
    if module is None:
        module = _build_fallback_cache_manager()
    return module


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _component_slug(component_id: str) -> str:
    """comp-<slug> -> <slug> (glossary: 'Component id / component slug')."""
    prefix = "comp-"
    if component_id.startswith(prefix):
        return component_id[len(prefix):]
    return component_id


def _env_var(var_name: str) -> Optional[str]:
    key = var_name.replace("-", "_")
    value = os.environ.get(key)
    return value if value else None


def _hash_dir(path: Optional[Path]) -> str:
    """
    Deterministic content hash of a directory tree (sorted relative paths +
    file bytes). A missing/unreadable directory still produces a stable,
    deterministic hash rather than erroring (consistent with this
    component's fail-to-empty posture for missing external/local inputs).
    """
    h = hashlib.sha256()
    try:
        p = Path(path) if path is not None else None
    except TypeError:
        p = None
    if p is not None and p.is_dir():
        for f in sorted(p.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(p).as_posix()
            h.update(rel.encode("utf-8"))
            try:
                h.update(f.read_bytes())
            except OSError:
                continue
    else:
        h.update(b"<absent>")
    return "sha256:" + h.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Reference corpus loading (R-LICENSE-001 / D67 / VAR-LICENSE-CORPUS-PATH)
# ---------------------------------------------------------------------------


def _load_corpus(repo_root: Path, corpus_path_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Loads the precomputed k-gram reference corpus from
    VAR-LICENSE-CORPUS-PATH. A missing var, missing file, or unparsable
    file all resolve to "no corpus" (None) — never an error, never a
    silently-skipped scan: the caller treats None as "no matches possible,
    similarity_score 0.0", which is still a real, recorded result.
    """
    if not corpus_path_str:
        return None
    p = Path(corpus_path_str)
    if not p.is_absolute():
        p = Path(repo_root) / p
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    entries = data.get("entries")
    if not isinstance(entries, list):
        return None
    return data


# ---------------------------------------------------------------------------
# Normalization / tokenization / k-gram hashing (R-LICENSE-001)
# ---------------------------------------------------------------------------

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_TRIPLE_DQUOTE_RE = re.compile(r'""".*?"""', re.S)
_TRIPLE_SQUOTE_RE = re.compile(r"'''.*?'''", re.S)
_LINE_SLASH_COMMENT_RE = re.compile(r"//.*$")
_LINE_HASH_COMMENT_RE = re.compile(r"#.*$")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def _strip_comments(text: str) -> str:
    text = _BLOCK_COMMENT_RE.sub(" ", text)
    text = _TRIPLE_DQUOTE_RE.sub(" ", text)
    text = _TRIPLE_SQUOTE_RE.sub(" ", text)
    out_lines = []
    for line in text.splitlines():
        line = _LINE_SLASH_COMMENT_RE.sub("", line)
        line = _LINE_HASH_COMMENT_RE.sub("", line)
        out_lines.append(line)
    return "\n".join(out_lines)


def _tokenize(text: str) -> List[str]:
    normalized = _strip_comments(text)
    return [t.lower() for t in _TOKEN_RE.findall(normalized)]


def _kgram_hashes(tokens: List[str], k: int) -> "set[str]":
    hashes: "set[str]" = set()
    n = len(tokens)
    if n < k:
        return hashes
    for i in range(n - k + 1):
        window = "\x1f".join(tokens[i:i + k])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return hashes


def _is_probably_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(2048)
        return b"\x00" in chunk
    except OSError:
        return True


def _document_kgram_hashes(gen_dir: Path) -> "set[str]":
    all_hashes: "set[str]" = set()
    if not gen_dir.is_dir():
        return all_hashes
    for f in sorted(gen_dir.rglob("*")):
        if not f.is_file():
            continue
        if _is_probably_binary(f):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        tokens = _tokenize(text)
        all_hashes |= _kgram_hashes(tokens, K_GRAM_SIZE)
    return all_hashes


def _score_against_corpus(doc_hashes: "set[str]", corpus: Optional[Dict[str, Any]]):
    """
    Returns (all_entry_matches, similarity_score) where similarity_score is
    the best (max) per-entry score — a pure confidence number, independent
    of which entry it came from or that entry's risk_tier (R-LICENSE-001 /
    R-LICENSE-003 separation of concerns).
    """
    matches: List[Dict[str, Any]] = []
    if not corpus or not doc_hashes:
        return matches, 0.0

    best = 0.0
    for entry in corpus.get("entries", []) or []:
        ref_hashes = set(entry.get("hashes", []) or [])
        if ref_hashes and doc_hashes:
            overlap = doc_hashes & ref_hashes
            score = len(overlap) / len(doc_hashes)
        else:
            score = 0.0
        matches.append(
            {
                "reference_id": entry.get("reference_id"),
                "license_family": entry.get("license_family"),
                "risk_tier": entry.get("risk_tier"),
                "score": round(score, 6),
            }
        )
        if score > best:
            best = score
    return matches, best


# ---------------------------------------------------------------------------
# Notification (R-LICENSE-003)
# ---------------------------------------------------------------------------


def _send_webhook(url: str, payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    At most one attempt, no retry-with-backoff. Any failure is caught and
    returned as a {category, message} dict; never raised, never retried.
    """
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SECONDS)
        return None
    except urllib.error.HTTPError as exc:
        category = "auth" if exc.code in (401, 403) else "network"
        return {"category": category, "message": str(exc)}
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            category = "timeout"
        else:
            category = "network"
        return {"category": category, "message": str(exc)}
    except (socket.timeout, TimeoutError) as exc:
        return {"category": "timeout", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - deliberately broad, never raised onward
        return {"category": "network", "message": str(exc)}


# ---------------------------------------------------------------------------
# Cache payload <-> result conversion
# ---------------------------------------------------------------------------


def _result_from_payload(payload: Dict[str, Any]) -> LicenseScanResult:
    return LicenseScanResult(
        component_id=payload.get("component_id"),
        gate_version=payload.get("gate_version"),
        similarity_score=payload.get("similarity_score", 0.0),
        block_threshold=payload.get("block_threshold", DEFAULT_BLOCK_THRESHOLD),
        blocked=payload.get("blocked", False),
        matches=list(payload.get("matches") or []),
        notified=payload.get("notified", False),
        notification_delivery_error=payload.get("notification_delivery_error"),
        cache_hit=payload.get("cache_hit", False),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan(component_id: str, repo_root: Path) -> LicenseScanResult:
    repo_root = Path(repo_root)
    slug = _component_slug(component_id)
    gen_dir = repo_root / "gen" / slug

    corpus_path_str = _env_var(VAR_CORPUS_PATH)
    corpus = _load_corpus(repo_root, corpus_path_str)
    corpus_version = corpus.get("corpus_version", 0) if corpus else 0
    block_threshold = (
        corpus.get("block_threshold", DEFAULT_BLOCK_THRESHOLD)
        if corpus
        else DEFAULT_BLOCK_THRESHOLD
    )
    gate_version = f"{SCANNER_NAME}@{CODE_VERSION}.{corpus_version}"

    gen_output_hash = _hash_dir(gen_dir)
    spec_bundle_hash = _hash_dir(repo_root / "specs" / "components" / slug)
    model_pin = NO_MODEL_PIN

    cm = _get_cache_manager(repo_root)
    cache_key = cm.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=gen_output_hash,
        gate_version=gate_version,
        model_pin=model_pin,
    )

    cached = cm.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cm.Miss):
        payload = dict(cached.payload)
        payload["cache_hit"] = True
        return _result_from_payload(payload)

    # --- R-LICENSE-004 cache miss: perform the real scan ---
    doc_hashes = _document_kgram_hashes(gen_dir)
    all_matches, similarity_score = _score_against_corpus(doc_hashes, corpus)
    blocked = similarity_score >= block_threshold

    reported_matches = [m for m in all_matches if m["score"] > REPORTING_FLOOR]
    reported_matches.sort(key=lambda m: m["score"], reverse=True)

    webhook_url = _env_var(VAR_WEBHOOK_URL)
    due = blocked or any(m.get("risk_tier") == "high" for m in reported_matches)
    notified = bool(due and webhook_url)

    notification_delivery_error: Optional[Dict[str, str]] = None
    if notified:
        notification_delivery_error = _send_webhook(
            webhook_url,
            {
                "component_id": component_id,
                "gate_version": gate_version,
                "similarity_score": round(similarity_score, 6),
                "block_threshold": block_threshold,
                "blocked": blocked,
                "matches": reported_matches,
            },
        )

    result = LicenseScanResult(
        component_id=component_id,
        gate_version=gate_version,
        similarity_score=round(similarity_score, 6),
        block_threshold=block_threshold,
        blocked=blocked,
        matches=reported_matches,
        notified=notified,
        notification_delivery_error=notification_delivery_error,
        cache_hit=False,
    )

    payload = dataclasses.asdict(result)
    try:
        cm.put(
            cache_key,
            cm.CachedResult(
                gate_type="license_scanner",
                payload=payload,
                stored_at=cm.now_iso() if hasattr(cm, "now_iso") else _now_iso(),
            ),
            repo_root=repo_root,
        )
    except Exception:
        # A caching failure must never affect the (already-computed,
        # already-correct) scan result; it only means this result won't be
        # reusable from cache next time.
        pass

    return result


# ---------------------------------------------------------------------------
# CLI (interface/cli.md)
# ---------------------------------------------------------------------------


def _format_text(result: LicenseScanResult) -> str:
    status = "FLAGGED" if result.blocked else "CLEAN"
    lines = [
        f"{status} {result.component_id} "
        f"score={result.similarity_score} threshold={result.block_threshold} "
        f"gate_version={result.gate_version} cache_hit={result.cache_hit}"
    ]
    for m in result.matches:
        lines.append(
            f"  match: reference_id={m.get('reference_id')} "
            f"license_family={m.get('license_family')} "
            f"risk_tier={m.get('risk_tier')} score={m.get('score')}"
        )
    lines.append(f"notified={result.notified}")
    if result.notification_delivery_error:
        lines.append(f"notification_delivery_error={result.notification_delivery_error}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs license-scan")
    parser.add_argument("component_id")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 2

    try:
        result = scan(args.component_id, Path(args.repo_root))
    except Exception as exc:  # usage-level failure, not a scan-result failure
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(dataclasses.asdict(result), indent=2, sort_keys=True))
    else:
        print(_format_text(result))

    return 1 if result.blocked else 0


if __name__ == "__main__":
    sys.exit(main())