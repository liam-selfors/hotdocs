"""Secret scanner: pattern + entropy based secret detection (comp-secret-scanner)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_ENTROPY_RUN_RE = re.compile(r"[A-Za-z0-9+/=_-]+")
_MIN_RUN_LENGTH = 20
_WINDOW_SIZE = 20
_ENTROPY_THRESHOLD = 4.0

_SCAN_SUBDIRS = ("specs", "gen", "verification")


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access helper
# ---------------------------------------------------------------------------

def _dget(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _payload_to_dict(payload):
    if isinstance(payload, dict):
        return dict(payload)
    result = {}
    for key in (
        "scope",
        "gate_version",
        "flagged",
        "matches",
        "notified",
        "notification_delivery_error",
        "cache_hit",
    ):
        if hasattr(payload, key):
            result[key] = getattr(payload, key)
    return result


# ---------------------------------------------------------------------------
# Pattern database
# ---------------------------------------------------------------------------

def _load_pattern_db(base_dir):
    raw_path = os.environ.get("VAR_SECRET_PATTERNS_PATH", "")
    if not raw_path:
        return "0.0.0", []

    p = Path(raw_path)
    if not p.is_absolute():
        p = Path(base_dir) / p

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return "0.0.0", []

    if not isinstance(data, dict):
        return "0.0.0", []

    version = data.get("version")
    if not isinstance(version, str) or not version:
        version = "0.0.0"

    rules = []
    rules_raw = data.get("rules")
    if isinstance(rules_raw, list):
        for entry in rules_raw:
            if not isinstance(entry, dict):
                continue
            rule_id = entry.get("rule_id")
            risk_tier = entry.get("risk_tier")
            pattern = entry.get("pattern")
            if not isinstance(rule_id, str) or not isinstance(risk_tier, str) or not isinstance(pattern, str):
                continue
            try:
                compiled = re.compile(pattern)
            except re.error:
                continue
            rules.append({"rule_id": rule_id, "risk_tier": risk_tier, "compiled": compiled})

    return version, rules


def gate_version(repo_root) -> str:
    version, _rules = _load_pattern_db(Path(repo_root))
    return f"secret_scanner@{version}"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _shannon_entropy(s):
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(s)
    entropy = 0.0
    for count in counts.values():
        prob = count / length
        entropy -= prob * math.log2(prob)
    return entropy


def _pattern_matches(line, rules):
    matches = []
    for rule in rules:
        for m in rule["compiled"].finditer(line):
            matches.append((m.start(), m.end(), rule["rule_id"], rule["risk_tier"]))
    return matches


def _entropy_matches(line, excluded_spans):
    matches = []
    for run_match in _ENTROPY_RUN_RE.finditer(line):
        start, end = run_match.span()
        run = run_match.group(0)
        if len(run) < _MIN_RUN_LENGTH:
            continue
        overlaps = any(start < es_end and end > es_start for es_start, es_end in excluded_spans)
        if overlaps:
            continue
        found = False
        for i in range(0, len(run) - _WINDOW_SIZE + 1):
            window = run[i:i + _WINDOW_SIZE]
            if _shannon_entropy(window) >= _ENTROPY_THRESHOLD:
                found = True
                break
        if found:
            matches.append((start, end, "entropy-heuristic", "low"))
    return matches


def _scan_line(line, rules):
    pattern_matches = _pattern_matches(line, rules)
    excluded_spans = [(s, e) for s, e, _rid, _tier in pattern_matches]
    entropy_matches = _entropy_matches(line, excluded_spans)
    return pattern_matches + entropy_matches


def _scan_file_content(text, rules):
    results = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for _start, _end, rule_id, risk_tier in _scan_line(line, rules):
            results.append({"rule_id": rule_id, "risk_tier": risk_tier, "line": lineno})
    return results


def _read_text(path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _walk_files(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fname in filenames:
            yield Path(dirpath) / fname


def _iter_scan_dirs(repo_root):
    for sub in _SCAN_SUBDIRS:
        base = Path(repo_root) / sub
        if not base.exists():
            continue
        for path in sorted(_walk_files(base), key=str):
            yield path


def _scan_tree(repo_root, rules):
    matches = []
    for path in _iter_scan_dirs(repo_root):
        text = _read_text(path)
        if text is None:
            continue
        rel_str = str(path.relative_to(repo_root)).replace(os.sep, "/")
        for match in _scan_file_content(text, rules):
            match["file"] = rel_str
            matches.append(match)
    return matches


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def _send_webhook(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return None
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {"category": "auth", "message": str(exc)}
        return {"category": "network", "message": str(exc)}
    except socket.timeout:
        return {"category": "timeout", "message": "request timed out"}
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.timeout):
            return {"category": "timeout", "message": str(exc)}
        return {"category": "network", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - must never raise out of scan()
        return {"category": "network", "message": str(exc)}


# ---------------------------------------------------------------------------
# cache-manager dynamic loading
# ---------------------------------------------------------------------------

def _try_load_cache_manager(repo_root):
    base = Path(repo_root) / "gen" / "cache-manager"
    flat = base / "cache_manager.py"
    pkg = base / "cache_manager" / "__init__.py"
    if flat.is_file():
        module_path = flat
    elif pkg.is_file():
        module_path = pkg
    else:
        return None

    try:
        spec = importlib.util.spec_from_file_location("cache_manager", module_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules["cache_manager"] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        sys.modules.pop("cache_manager", None)
        return None


def _hash_dir(base):
    h = hashlib.sha256()
    if base.exists():
        for path in sorted(_walk_files(base), key=lambda p: str(p)):
            try:
                data = path.read_bytes()
            except OSError:
                continue
            rel = str(path.relative_to(base)).replace(os.sep, "/")
            h.update(rel.encode("utf-8"))
            h.update(b"\x00")
            h.update(data)
            h.update(b"\x00")
    return "sha256:" + h.hexdigest()


def _hash_combined(bases):
    h = hashlib.sha256()
    for base in bases:
        h.update(_hash_dir(base).encode("utf-8"))
    return "sha256:" + h.hexdigest()


# ---------------------------------------------------------------------------
# Public library API
# ---------------------------------------------------------------------------

def scan(repo_root) -> dict:
    repo_root = Path(repo_root)
    version, rules = _load_pattern_db(repo_root)
    full_gate_version = f"secret_scanner@{version}"

    cache_module = None
    cache_key = None
    try:
        cache_module = _try_load_cache_manager(repo_root)
    except Exception:
        cache_module = None

    if cache_module is not None:
        try:
            spec_bundle_hash = _hash_dir(repo_root / "specs")
            gate_inputs_hash = _hash_combined([repo_root / "gen", repo_root / "verification"])
            cache_key = cache_module.CacheKey(
                spec_bundle_hash=spec_bundle_hash,
                gate_inputs_hash=gate_inputs_hash,
                gate_version=full_gate_version,
                model_pin="none",
            )
            cached = cache_module.get(cache_key, repo_root=repo_root)
            payload = _dget(cached, "payload")
            if payload is not None:
                result = _payload_to_dict(payload)
                result["cache_hit"] = True
                return result
        except Exception:
            cache_key = None

    matches = _scan_tree(repo_root, rules)
    flagged = len(matches) > 0
    has_high = any(m["risk_tier"] == "high" for m in matches)
    webhook_url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL", "")
    notified = (flagged or has_high) and bool(webhook_url)

    notification_delivery_error = None
    if notified:
        notification_delivery_error = _send_webhook(
            webhook_url,
            {
                "scope": "full",
                "gate_version": full_gate_version,
                "flagged": flagged,
                "matches": matches,
            },
        )

    result = {
        "scope": "full",
        "gate_version": full_gate_version,
        "flagged": flagged,
        "matches": matches,
        "notified": notified,
        "notification_delivery_error": notification_delivery_error,
        "cache_hit": False,
    }

    if cache_module is not None and cache_key is not None:
        try:
            stored_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            cached_result = cache_module.CachedResult(
                gate_type="secret_scanner",
                payload={
                    "scope": result["scope"],
                    "gate_version": result["gate_version"],
                    "flagged": result["flagged"],
                    "matches": result["matches"],
                    "notified": result["notified"],
                    "notification_delivery_error": result["notification_delivery_error"],
                    "cache_hit": False,
                },
                stored_at=stored_at,
            )
            cache_module.put(cache_key, cached_result, repo_root=repo_root)
        except Exception:
            pass

    return result


def scan_files(paths) -> dict:
    version, rules = _load_pattern_db(Path.cwd())
    full_gate_version = f"secret_scanner@{version}"

    matches = []
    for raw in paths:
        path = Path(raw)
        text = _read_text(path)
        if text is None:
            continue
        file_str = str(path).replace(os.sep, "/")
        for match in _scan_file_content(text, rules):
            match["file"] = file_str
            matches.append(match)

    flagged = len(matches) > 0
    has_high = any(m["risk_tier"] == "high" for m in matches)
    webhook_url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL", "")
    notified = (flagged or has_high) and bool(webhook_url)

    notification_delivery_error = None
    if notified:
        notification_delivery_error = _send_webhook(
            webhook_url,
            {
                "scope": "precommit",
                "flagged": flagged,
                "matches": matches,
            },
        )

    return {
        "scope": "precommit",
        "gate_version": full_gate_version,
        "flagged": flagged,
        "matches": matches,
        "notified": notified,
        "notification_delivery_error": notification_delivery_error,
        "cache_hit": False,
    }


# ---------------------------------------------------------------------------
# precommit default file discovery
# ---------------------------------------------------------------------------

def _default_precommit_files(repo_root):
    files = set()
    commands = (
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    )
    for command in commands:
        try:
            proc = subprocess.run(
                command, cwd=str(repo_root), capture_output=True, text=True, check=False
            )
        except OSError:
            return []
        if proc.returncode != 0:
            return []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                files.add(line)
    return sorted(files)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _usage_error(message):
    print(f"usage error: {message}", file=sys.stderr)


def _flag_value(args, i, name):
    arg = args[i]
    prefix = name + "="
    if arg.startswith(prefix):
        return arg[len(prefix):], i + 1, True
    if i + 1 >= len(args):
        return None, i + 1, False
    return args[i + 1], i + 2, True


def main(argv) -> int:
    args = list(argv)
    if args and args[0] == "secret-scan":
        args = args[1:]

    subcommand = "full"
    if args and args[0] == "precommit":
        subcommand = "precommit"
        args = args[1:]
    elif args and not args[0].startswith("-"):
        _usage_error(f"unknown subcommand: {args[0]}")
        return 2

    repo_root_raw = None
    fmt = "text"
    files = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--repo-root" or arg.startswith("--repo-root="):
            value, i, ok = _flag_value(args, i, "--repo-root")
            if not ok:
                _usage_error("--repo-root requires a value")
                return 2
            repo_root_raw = value
        elif arg == "--format" or arg.startswith("--format="):
            value, i, ok = _flag_value(args, i, "--format")
            if not ok:
                _usage_error("--format requires a value")
                return 2
            if value not in ("json", "text"):
                _usage_error(f"invalid --format: {value}")
                return 2
            fmt = value
        elif subcommand == "precommit" and (arg == "--files" or arg.startswith("--files=")):
            value, i, ok = _flag_value(args, i, "--files")
            if not ok:
                _usage_error("--files requires a value")
                return 2
            files.append(value)
        else:
            _usage_error(f"unknown argument: {arg}")
            return 2

    repo_root = Path(repo_root_raw) if repo_root_raw else Path.cwd()

    if subcommand == "full":
        result = scan(repo_root)
    else:
        if not files:
            files = _default_precommit_files(repo_root)
        abs_paths = []
        for raw in files:
            p = Path(raw)
            if not p.is_absolute():
                p = repo_root / p
            abs_paths.append(p)
        result = scan_files(abs_paths)
        for match in result["matches"]:
            try:
                rel = os.path.relpath(match["file"], str(repo_root))
                match["file"] = rel.replace(os.sep, "/")
            except ValueError:
                pass

    if fmt == "json":
        print(json.dumps(result))
    else:
        print("FLAGGED" if result["flagged"] else "CLEAN")
        for match in result["matches"]:
            print(f"{match['file']}:{match['line']} {match['rule_id']} ({match['risk_tier']})")

    return 1 if result["flagged"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))