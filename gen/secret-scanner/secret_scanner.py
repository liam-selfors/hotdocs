"""
Secret Scanner (comp-secret-scanner)

Implements the behavior described in the SpecBundle for this component:

  - R-SECRET-001: pattern-database + Shannon-entropy (>=4.0 bits/char)
    detection across specs/, gen/, verification/.
  - R-SECRET-002: any match blocks the merge (pure confidence call).
  - R-SECRET-003/009: every scan result -- clean or flagged -- is a real,
    recorded result; nothing is ever silently dropped or overwritten.
  - R-SECRET-004: notification fires when (flagged) OR (any match's
    risk_tier == "high"), independent of merge outcome; webhook call is
    attempted at most once, never retried, failures recorded as
    `notification_delivery_error`, never raised, never affecting `flagged`.
  - R-SECRET-005/006: cache-manager-aware full scan, keyed on
    (spec_bundle_hash, gate_inputs_hash, gate_version, model_pin), with the
    pattern-database version folded into `gate_version`.
  - R-SECRET-007: exactly one SecretScanResult per scan.
  - R-SECRET-008: a separate, lightweight `scan_files` / `precommit` mode,
    scoped to given files only, no cache-manager dependency.

This file is the complete, from-scratch implementation for this component;
no prior implementation or HINT_CODE was supplied for this generation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

ENTROPY_THRESHOLD = 4.0  # bits/char -- R-SECRET-001

# Candidate substrings considered for the entropy heuristic: contiguous
# runs of base64/hex-ish characters, long enough that ordinary prose /
# identifiers rarely qualify.
_ENTROPY_CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")

_ENTROPY_RULE_ID = "entropy-heuristic"
_ENTROPY_RISK_TIER = "low"

_GATE_NAME = "secret_scanner"
_DEFAULT_PATTERN_DB_VERSION = "0.0.0"

_SCAN_DIR_NAMES = ("specs", "gen", "verification")


# --------------------------------------------------------------------------
# Data shapes
# --------------------------------------------------------------------------

@dataclass
class SecretScanMatch:
    rule_id: str
    risk_tier: str
    file: str
    line: int
    excerpt: str  # redacted/truncated -- never the full matched string

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "risk_tier": self.risk_tier,
            "file": self.file,
            "line": self.line,
            "excerpt": self.excerpt,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SecretScanMatch":
        return SecretScanMatch(
            rule_id=d.get("rule_id", "unknown"),
            risk_tier=d.get("risk_tier", "low"),
            file=d.get("file", ""),
            line=int(d.get("line", 0) or 0),
            excerpt=d.get("excerpt", ""),
        )


@dataclass
class SecretScanResult:
    scope: str  # "full" | "precommit"
    flagged: bool
    matches: List[SecretScanMatch] = field(default_factory=list)
    notified: bool = False
    notification_delivery_error: Optional[Dict[str, str]] = None
    cache_hit: bool = False
    gate_version: Optional[str] = None  # only meaningful for scope == "full"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "scope": self.scope,
            "flagged": self.flagged,
            "matches": [m.to_dict() for m in self.matches],
            "notified": self.notified,
            "notification_delivery_error": self.notification_delivery_error,
            "cache_hit": self.cache_hit,
        }
        if self.gate_version is not None:
            d["gate_version"] = self.gate_version
        return d

    @staticmethod
    def from_payload(payload: Dict[str, Any], *, cache_hit: bool) -> "SecretScanResult":
        matches = [SecretScanMatch.from_dict(m) for m in payload.get("matches", [])]
        return SecretScanResult(
            scope=payload.get("scope", "full"),
            gate_version=payload.get("gate_version"),
            flagged=bool(payload.get("flagged", False)),
            matches=matches,
            notified=bool(payload.get("notified", False)),
            notification_delivery_error=payload.get("notification_delivery_error"),
            cache_hit=cache_hit,
        )


# --------------------------------------------------------------------------
# VAR lookup helper
# --------------------------------------------------------------------------

def _var(name: str) -> Optional[str]:
    """Look up a VAR-* declaration's value from the environment.

    VAR names are hyphenated (e.g. VAR-SECRET-PATTERNS-PATH); environment
    variable names can't contain hyphens, so the underscored form is the
    primary lookup, with the literal hyphenated name as a fallback.
    """
    underscored = name.replace("-", "_")
    val = os.environ.get(underscored)
    if val is not None:
        return val
    return os.environ.get(name)


# --------------------------------------------------------------------------
# Pattern database (R-SECRET-001)
# --------------------------------------------------------------------------

def _load_pattern_db(path_str: Optional[str]) -> "tuple[str, list]":
    """Load the externally-sourced pattern database.

    A missing/unreachable/malformed database MUST NOT raise -- the scanner
    still produces a real result, with entropy-only detection in effect
    (R-SECRET-001).
    """
    if not path_str:
        return _DEFAULT_PATTERN_DB_VERSION, []

    try:
        raw = Path(path_str).read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        return _DEFAULT_PATTERN_DB_VERSION, []

    if isinstance(data, dict):
        version = str(data.get("version", _DEFAULT_PATTERN_DB_VERSION))
        rules_raw = data.get("rules", [])
    elif isinstance(data, list):
        version = _DEFAULT_PATTERN_DB_VERSION
        rules_raw = data
    else:
        return _DEFAULT_PATTERN_DB_VERSION, []

    rules: List[Dict[str, Any]] = []
    if isinstance(rules_raw, list):
        for r in rules_raw:
            if not isinstance(r, dict):
                continue
            rule_id = r.get("rule_id")
            risk_tier = r.get("risk_tier")
            pattern_str = r.get("pattern", r.get("regex"))
            if not rule_id or not risk_tier or not pattern_str:
                continue
            try:
                compiled = re.compile(pattern_str)
            except re.error:
                continue
            rules.append({"rule_id": rule_id, "risk_tier": risk_tier, "pattern": compiled})

    return version, rules


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------

def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _redact(s: str) -> str:
    """Truncate/redact matched text -- never echo the full matched string."""
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:4]}...{s[-4:]}"


def _scan_text(text: str, rules: List[Dict[str, Any]]) -> "list[tuple[str, str, int, str]]":
    """Returns a list of (rule_id, risk_tier, line_number, redacted_excerpt)."""
    found: List["tuple[str, str, int, str]"] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        matched_spans: List["tuple[int, int]"] = []
        for rule in rules:
            for m in rule["pattern"].finditer(line):
                found.append((rule["rule_id"], rule["risk_tier"], lineno, _redact(m.group(0))))
                matched_spans.append((m.start(), m.end()))

        for cand in _ENTROPY_CANDIDATE_RE.finditer(line):
            start, end = cand.start(), cand.end()
            overlaps = any(start < e and s_ < end for s_, e in matched_spans)
            if overlaps:
                continue
            token = cand.group(0)
            entropy = _shannon_entropy(token)
            if entropy >= ENTROPY_THRESHOLD:
                found.append((_ENTROPY_RULE_ID, _ENTROPY_RISK_TIER, lineno, _redact(token)))

    return found


def _iter_files(root: Path):
    if root.is_file():
        yield root
        return
    if not root.exists():
        return
    for p in sorted(root.rglob("*")):
        if p.is_file():
            yield p


def _read_text(p: Path) -> Optional[str]:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


# --------------------------------------------------------------------------
# Hashing (for cache-key construction -- R-SECRET-005)
# --------------------------------------------------------------------------

def _hash_tree(root: Path) -> str:
    h = hashlib.sha256()
    for f in _iter_files(root):
        rel = f.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        try:
            h.update(f.read_bytes())
        except Exception:
            pass
    return h.hexdigest()


def _hash_trees(roots: List[Path]) -> str:
    h = hashlib.sha256()
    for root in roots:
        prefix = root.name
        for f in _iter_files(root):
            rel = f.relative_to(root).as_posix() if root.exists() and root.is_dir() else root.name
            h.update(prefix.encode("utf-8"))
            h.update(rel.encode("utf-8"))
            try:
                h.update(f.read_bytes())
            except Exception:
                pass
    return h.hexdigest()


# --------------------------------------------------------------------------
# cache-manager dependency loading
#
# comp-cache-manager is importable as `cache_manager`, living under
# gen/cache-manager/ (module path has an underscore, the containing
# directory has a hyphen). We first try a normal import (works if the
# caller's environment already has gen/cache-manager on sys.path); if that
# fails we locate the file ourselves and load it directly, registering it
# in sys.modules BEFORE exec_module so its dataclasses can resolve their
# own __module__ during class-body execution.
# --------------------------------------------------------------------------

def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # MUST happen before exec_module
    spec.loader.exec_module(module)
    return module


def _load_cache_manager():
    try:
        import cache_manager  # type: ignore
        return cache_manager
    except ImportError:
        pass

    here = Path(__file__).resolve()
    candidate_dirs: List[Path] = []

    # Walk upward looking for a sibling "gen/cache-manager" directory.
    for ancestor in here.parents:
        d = ancestor / "gen" / "cache-manager"
        if d.exists():
            candidate_dirs.append(d)

    # Also handle the case where this file itself lives under a "gen/"
    # directory (gen/secret-scanner/secret_scanner.py) -- check the sibling
    # "cache-manager" directory directly.
    for ancestor in here.parents:
        if ancestor.name == "gen":
            d = ancestor / "cache-manager"
            if d.exists() and d not in candidate_dirs:
                candidate_dirs.append(d)
            break

    for d in candidate_dirs:
        flat = d / "cache_manager.py"
        if flat.exists():
            module = _load_module_from_file("cache_manager", flat)
            if module is not None:
                return module
        pkg_init = d / "cache_manager" / "__init__.py"
        if pkg_init.exists():
            module = _load_module_from_file("cache_manager", pkg_init)
            if module is not None:
                return module

    raise ImportError("could not locate the cache_manager dependency module")


# --------------------------------------------------------------------------
# Webhook notification (R-SECRET-004)
# --------------------------------------------------------------------------

def _attempt_webhook(url: str, payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Attempt the webhook call exactly once. Never raises; never retries.

    Returns None on apparent success, or a {"category", "message"} dict on
    failure. This never affects `flagged`.
    """
    import socket
    import urllib.error
    import urllib.request

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = getattr(resp, "status", 200)
            if status in (401, 403):
                return {"category": "auth", "message": f"HTTP {status}"}
        return None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {"category": "auth", "message": str(e)}
        return {"category": "network", "message": str(e)}
    except (socket.timeout, TimeoutError):
        return {"category": "timeout", "message": "timed out"}
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return {"category": "timeout", "message": str(e)}
        return {"category": "network", "message": str(e)}
    except Exception as e:  # pragma: no cover - defensive catch-all
        return {"category": "network", "message": str(e)}


def _maybe_notify(flagged: bool, matches: List[SecretScanMatch]) -> "tuple[bool, Optional[Dict[str, str]]]":
    webhook_url = _var("VAR-COMPLIANCE-WEBHOOK-URL")
    due = flagged or any(m.risk_tier == "high" for m in matches)
    notified = bool(due and webhook_url)
    delivery_error = None
    if notified:
        delivery_error = _attempt_webhook(
            webhook_url,
            {
                "component": "secret-scanner",
                "flagged": flagged,
                "matches": [m.to_dict() for m in matches],
            },
        )
    return notified, delivery_error


# --------------------------------------------------------------------------
# Public library API
# --------------------------------------------------------------------------

def scan(repo_root: Path) -> SecretScanResult:
    """Full, cache-aware scan of specs/, gen/, and verification/.

    R-SECRET-001/002/003/004/005/006/007.
    """
    repo_root = Path(repo_root)

    db_path = _var("VAR-SECRET-PATTERNS-PATH")
    db_version, rules = _load_pattern_db(db_path)
    gate_version = f"{_GATE_NAME}@{db_version}"
    model_pin = "none"  # this gate makes no model calls

    scan_roots = [repo_root / name for name in _SCAN_DIR_NAMES]

    spec_bundle_hash = "sha256:" + _hash_tree(repo_root / "specs")
    gen_output_hash = "sha256:" + _hash_trees(
        [repo_root / "gen", repo_root / "verification"]
    )

    cache_module = None
    cache_key = None
    try:
        cache_module = _load_cache_manager()
        cache_key = cache_module.CacheKey(
            spec_bundle_hash=spec_bundle_hash,
            gate_inputs_hash=gen_output_hash,
            gate_version=gate_version,
            model_pin=model_pin,
        )
    except Exception:
        cache_module = None
        cache_key = None

    if cache_module is not None and cache_key is not None:
        try:
            cached = cache_module.get(cache_key, repo_root=repo_root)
        except Exception:
            cached = None
        if cached is not None and not isinstance(cached, cache_module.Miss):
            return SecretScanResult.from_payload(cached.payload, cache_hit=True)

    matches: List[SecretScanMatch] = []
    for root in scan_roots:
        if not root.exists():
            continue
        for f in _iter_files(root):
            text = _read_text(f)
            if text is None:
                continue
            try:
                rel = f.relative_to(repo_root).as_posix()
            except ValueError:
                rel = str(f)
            for rule_id, risk_tier, lineno, excerpt in _scan_text(text, rules):
                matches.append(
                    SecretScanMatch(
                        rule_id=rule_id,
                        risk_tier=risk_tier,
                        file=rel,
                        line=lineno,
                        excerpt=excerpt,
                    )
                )

    flagged = len(matches) > 0  # R-SECRET-002: pure confidence determination
    notified, delivery_error = _maybe_notify(flagged, matches)

    result = SecretScanResult(
        scope="full",
        gate_version=gate_version,
        flagged=flagged,
        matches=matches,
        notified=notified,
        notification_delivery_error=delivery_error,
        cache_hit=False,
    )

    if cache_module is not None and cache_key is not None:
        try:
            cache_module.put(
                cache_key,
                cache_module.CachedResult(
                    gate_type=_GATE_NAME,
                    payload=result.to_dict(),
                    stored_at=cache_module.now_iso(),
                ),
                repo_root=repo_root,
            )
        except Exception:
            # Caching is best-effort; a failure to cache MUST NOT turn a
            # real, computed result into a failure to produce one.
            pass

    return result


def scan_files(paths: List[Path]) -> SecretScanResult:
    """Lightweight precommit/prepush scan -- R-SECRET-008.

    Scoped to the given files only; no cache-manager dependency, no
    gate_version dependency.
    """
    db_path = _var("VAR-SECRET-PATTERNS-PATH")
    _version, rules = _load_pattern_db(db_path)

    matches: List[SecretScanMatch] = []
    for p in paths:
        p = Path(p)
        if not p.exists() or not p.is_file():
            continue
        text = _read_text(p)
        if text is None:
            continue
        for rule_id, risk_tier, lineno, excerpt in _scan_text(text, rules):
            matches.append(
                SecretScanMatch(
                    rule_id=rule_id,
                    risk_tier=risk_tier,
                    file=str(p),
                    line=lineno,
                    excerpt=excerpt,
                )
            )

    flagged = len(matches) > 0
    notified, delivery_error = _maybe_notify(flagged, matches)

    return SecretScanResult(
        scope="precommit",
        gate_version=None,
        flagged=flagged,
        matches=matches,
        notified=notified,
        notification_delivery_error=delivery_error,
        cache_hit=False,
    )


# --------------------------------------------------------------------------
# git helpers for the precommit CLI form
# --------------------------------------------------------------------------

def _git_pending_files(repo_root: Path) -> List[str]:
    """Best-effort discovery of staged/pending files in the local git state.

    Used only when `--files` is omitted on `precommit`. Any failure (no
    git, no repo, git not on PATH) yields an empty file list rather than
    raising -- a precommit hook must never crash the commit it's guarding.
    """
    attempts = [
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    ]
    for cmd in attempts:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            continue
        if proc.returncode == 0:
            files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            if files:
                return files
    return []


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hotdocs secret-scan", add_help=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")

    sub = parser.add_subparsers(dest="mode")
    precommit = sub.add_parser("precommit")
    precommit.add_argument("--files", action="append", default=None)
    precommit.add_argument("--repo-root", default=".")
    precommit.add_argument("--format", choices=["json", "text"], default="text")

    return parser


def _print_result(result: SecretScanResult, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return

    status = "FLAGGED" if result.flagged else "CLEAN"
    print(f"{status} ({result.scope}) -- {len(result.matches)} match(es)")
    for m in result.matches:
        print(f"  [{m.risk_tier}] {m.rule_id} {m.file}:{m.line} {m.excerpt}")
    if result.notified:
        if result.notification_delivery_error:
            print(f"notification: due, delivery failed ({result.notification_delivery_error})")
        else:
            print("notification: due, delivered")


def main(argv: Optional[List[str]] = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else list(argv)

    # Tolerate being invoked either with or without the leading
    # "secret-scan" token (the `hotdocs` dispatcher strips it; direct
    # invocation of this module may not).
    if raw_argv and raw_argv[0] == "secret-scan":
        raw_argv = raw_argv[1:]

    parser = _build_parser()
    try:
        ns = parser.parse_args(raw_argv)
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else 2

    repo_root = Path(getattr(ns, "repo_root", "."))
    fmt = getattr(ns, "format", "text")

    try:
        if getattr(ns, "mode", None) == "precommit":
            file_args = getattr(ns, "files", None)
            if file_args:
                paths = [Path(p) for p in file_args]
            else:
                paths = [repo_root / f for f in _git_pending_files(repo_root)]
            result = scan_files(paths)
        else:
            result = scan(repo_root)
    except Exception as e:
        print(f"secret-scan: error: {e}", file=sys.stderr)
        return 2

    _print_result(result, fmt)
    return 1 if result.flagged else 0


if __name__ == "__main__":
    sys.exit(main())