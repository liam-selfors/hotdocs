"""Secret Scanner (comp-secret-scanner)."""

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "AllowlistInvalidError",
    "SecretScanResult",
    "scan",
    "scan_files",
    "gate_version",
    "propose",
    "main",
]

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", ".hotdocs", "node_modules"}
GATE_BASE_VERSION = "3.0.0"
LOW_RISK_TYPES = {"Base64 High Entropy String", "Hex High Entropy String"}
EXCLUDED_PLUGINS = {"KeywordDetector", "IPPublicDetector"}
ALLOWLIST_FILENAME = ".secret-allowlist.json"

_PATH_CHARS_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_HASHED_SECRET_RE = re.compile(r"^sha1:[0-9a-f]{40}$")


class AllowlistInvalidError(Exception):
    pass


@dataclass
class SecretScanResult:
    scope: str
    gate_version: str | None
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: dict | None
    cache_hit: bool

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "gate_version": self.gate_version,
            "flagged": self.flagged,
            "matches": self.matches,
            "allowed": self.allowed,
            "unused_allowlist_entries": self.unused_allowlist_entries,
            "notified": self.notified,
            "notification_delivery_error": self.notification_delivery_error,
            "cache_hit": self.cache_hit,
        }


# --------------------------------------------------------------------------
# File enumeration / hashing
# --------------------------------------------------------------------------

def _iter_candidate_files(repo_root: Path):
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            yield Path(dirpath) / fn


def _is_utf8_decodable(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            data = f.read()
        data.decode("utf-8")
        return True
    except (OSError, UnicodeDecodeError):
        return False


def _relative_posix(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
        return str(rel).replace(os.sep, "/")
    except ValueError:
        return str(path)


def _is_under(path: Path, base_dir: Path) -> bool:
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def _hash_file_set(files: list, repo_root: Path) -> str:
    pairs = sorted(
        ((_relative_posix(f, repo_root), f) for f in files), key=lambda x: x[0]
    )
    h = hashlib.sha256()
    for rel, f in pairs:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(f.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# detect-secrets engine
# --------------------------------------------------------------------------

def _detect_secrets_version() -> str:
    return importlib.metadata.version("detect-secrets")


def _gate_version_string(detect_secrets_version: str) -> str:
    return f"secret_scanner@{GATE_BASE_VERSION}+detect-secrets.{detect_secrets_version}"


def _risk_tier(rule_id: str) -> str:
    return "low" if rule_id in LOW_RISK_TYPES else "high"


def _run_detect_secrets(file_paths: list):
    from detect_secrets import SecretsCollection
    from detect_secrets.core.plugins.util import get_mapping_from_secret_type_to_class
    from detect_secrets.settings import transient_settings

    names = []
    for cls in get_mapping_from_secret_type_to_class().values():
        name = cls.__name__
        if name in EXCLUDED_PLUGINS:
            continue
        if name not in names:
            names.append(name)

    config = {"plugins_used": [{"name": n} for n in names], "filters_used": []}

    collection = SecretsCollection()
    with transient_settings(config):
        for path in file_paths:
            collection.scan_file(str(path))

    return list(collection)


def _collect_matches_internal(files: list, repo_root) -> list:
    raw = _run_detect_secrets(files)
    result = []
    for filename, secret in raw:
        rule_id = secret.type
        if repo_root is not None:
            file_str = _relative_posix(Path(filename), repo_root)
        else:
            file_str = filename
        result.append(
            {
                "rule_id": rule_id,
                "risk_tier": _risk_tier(rule_id),
                "file": file_str,
                "line": secret.line_number,
                "secret_hash": secret.secret_hash,
            }
        )
    return result


def _strip_hash(m: dict) -> dict:
    return {"rule_id": m["rule_id"], "risk_tier": m["risk_tier"], "file": m["file"], "line": m["line"]}


# --------------------------------------------------------------------------
# Allowlist
# --------------------------------------------------------------------------

def _has_dotdot_segment(p: str) -> bool:
    return ".." in p.split("/")


def _load_allowlist(repo_root: Path):
    path = repo_root / ALLOWLIST_FILENAME
    if not path.exists():
        return [], True

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [], False

    if not isinstance(data, dict) or set(data.keys()) != {"version", "entries"}:
        return [], False

    version = data.get("version")
    if isinstance(version, bool) or version != 1:
        return [], False

    entries = data.get("entries")
    if not isinstance(entries, list):
        return [], False

    validated = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry.keys()) != {"file", "type", "hashed_secret", "reason"}:
            return [], False

        file_ = entry.get("file")
        type_ = entry.get("type")
        hashed = entry.get("hashed_secret")
        reason = entry.get("reason")

        if not all(isinstance(v, str) for v in (file_, type_, hashed, reason)):
            return [], False
        if file_.startswith("/") or _has_dotdot_segment(file_):
            return [], False
        if not _PATH_CHARS_RE.match(file_):
            return [], False
        if not _HASHED_SECRET_RE.match(hashed):
            return [], False

        if reason == "planted-fixture":
            if not (file_.startswith("verification/") or file_.startswith("specs/")):
                return [], False
        elif reason == "public-constant":
            if type_ != "Hex High Entropy String":
                return [], False
        else:
            return [], False

        validated.append({"file": file_, "type": type_, "hashed_secret": hashed, "reason": reason})

    return validated, True


def _apply_allowlist(internal_matches: list, allowlist_entries: list, allowlist_valid: bool):
    if not allowlist_valid:
        final_matches = [_strip_hash(m) for m in internal_matches]
        final_matches.append(
            {
                "rule_id": "allowlist-invalid",
                "risk_tier": "high",
                "file": ALLOWLIST_FILENAME,
                "line": 1,
            }
        )
        return final_matches, [], []

    entry_lookup = {(e["file"], e["type"], e["hashed_secret"]): e for e in allowlist_entries}
    matched_keys = set()
    final_matches = []
    allowed = []

    for m in internal_matches:
        hashed = "sha1:" + m["secret_hash"]
        key = (m["file"], m["rule_id"], hashed)
        if key in entry_lookup:
            matched_keys.add(key)
            allowed.append({"rule_id": m["rule_id"], "file": m["file"], "line": m["line"]})
        else:
            final_matches.append(_strip_hash(m))

    unused = []
    for e in allowlist_entries:
        key = (e["file"], e["type"], e["hashed_secret"])
        if key not in matched_keys:
            unused.append({"file": e["file"], "type": e["type"]})

    return final_matches, allowed, unused


# --------------------------------------------------------------------------
# Notification
# --------------------------------------------------------------------------

def _webhook_url():
    val = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL")
    return val if val else None


def _post_webhook(url: str, flagged: bool, matches: list):
    body = json.dumps({"gate": "secret_scanner", "flagged": flagged, "matches": matches}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=10)
        return None
    except urllib.error.HTTPError as e:
        category = "auth" if e.code in (401, 403) else "network"
        return {"category": category, "message": str(e)}
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
            category = "timeout"
        else:
            category = "network"
        return {"category": category, "message": str(e)}
    except TimeoutError as e:
        return {"category": "timeout", "message": str(e)}
    except Exception as e:
        return {"category": "network", "message": str(e)}


def _maybe_notify(final_matches: list, flagged: bool):
    high_risk_present = any(m["risk_tier"] == "high" for m in final_matches)
    due = flagged or high_risk_present
    url = _webhook_url()
    notified = bool(due and url)
    error = _post_webhook(url, flagged, final_matches) if notified else None
    return notified, error


# --------------------------------------------------------------------------
# cache-manager loading
# --------------------------------------------------------------------------

def _load_module_from_path(module_name: str, base_dir: Path):
    pkg_init = base_dir / module_name / "__init__.py"
    flat = base_dir / f"{module_name}.py"

    if pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            module_name, pkg_init, submodule_search_locations=[str(pkg_init.parent)]
        )
    elif flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        raise ImportError(f"cannot find module {module_name!r} under {base_dir}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_cache_manager(repo_root: Path):
    try:
        base_dir = Path(repo_root) / "gen" / "cache-manager"
        return _load_module_from_path("cache_manager", base_dir)
    except Exception:
        return None


def _result_from_payload(payload, cache_hit: bool) -> SecretScanResult:
    def g(key, default=None):
        if isinstance(payload, dict):
            return payload.get(key, default)
        return getattr(payload, key, default)

    return SecretScanResult(
        scope=g("scope"),
        gate_version=g("gate_version"),
        flagged=g("flagged"),
        matches=g("matches", []),
        allowed=g("allowed", []),
        unused_allowlist_entries=g("unused_allowlist_entries", []),
        notified=g("notified", False),
        notification_delivery_error=g("notification_delivery_error"),
        cache_hit=cache_hit,
    )


# --------------------------------------------------------------------------
# Core scan paths
# --------------------------------------------------------------------------

def _run_full_scan(repo_root: Path, decodable_files: list, gate_version_str: str) -> SecretScanResult:
    allowlist_entries, allowlist_valid = _load_allowlist(repo_root)
    internal_matches = _collect_matches_internal(decodable_files, repo_root)
    final_matches, allowed, unused = _apply_allowlist(internal_matches, allowlist_entries, allowlist_valid)

    final_matches.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    allowed.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    unused.sort(key=lambda e: (e["file"], e["type"]))

    flagged = len(final_matches) > 0
    notified, notification_delivery_error = _maybe_notify(final_matches, flagged)

    return SecretScanResult(
        scope="full",
        gate_version=gate_version_str,
        flagged=flagged,
        matches=final_matches,
        allowed=allowed,
        unused_allowlist_entries=unused,
        notified=notified,
        notification_delivery_error=notification_delivery_error,
        cache_hit=False,
    )


def scan(repo_root) -> SecretScanResult:
    repo_root_path = Path(repo_root)
    all_files = list(_iter_candidate_files(repo_root_path))
    decodable_files = [f for f in all_files if _is_utf8_decodable(f)]

    gate_version_str = _gate_version_string(_detect_secrets_version())

    cache_mod = _load_cache_manager(repo_root_path)
    cache_key = None
    if cache_mod is not None:
        try:
            specs_dir = repo_root_path / "specs"
            spec_files = [f for f in decodable_files if _is_under(f, specs_dir)]
            other_files = [f for f in decodable_files if not _is_under(f, specs_dir)]
            spec_hash = "sha256:" + _hash_file_set(spec_files, repo_root_path)
            inputs_hash = "sha256:" + _hash_file_set(other_files, repo_root_path)

            cache_key = cache_mod.CacheKey(
                spec_bundle_hash=spec_hash,
                gate_inputs_hash=inputs_hash,
                gate_version=gate_version_str,
                model_pin="none",
            )
            cached = cache_mod.get(cache_key, repo_root=repo_root_path)
            payload = (
                cached.get("payload") if isinstance(cached, dict) else getattr(cached, "payload", None)
            )
            if payload is not None:
                return _result_from_payload(payload, cache_hit=True)
        except Exception:
            cache_mod = None
            cache_key = None

    result = _run_full_scan(repo_root_path, decodable_files, gate_version_str)

    if cache_mod is not None and cache_key is not None:
        try:
            cached_result = cache_mod.CachedResult(
                gate_type="secret_scanner",
                payload={
                    "scope": result.scope,
                    "gate_version": result.gate_version,
                    "flagged": result.flagged,
                    "matches": result.matches,
                    "allowed": result.allowed,
                    "unused_allowlist_entries": result.unused_allowlist_entries,
                    "notified": result.notified,
                    "notification_delivery_error": result.notification_delivery_error,
                },
                stored_at=_now_iso(),
            )
            cache_mod.put(cache_key, cached_result, repo_root=repo_root_path)
        except Exception:
            pass

    return result


def scan_files(paths: list, repo_root=None) -> SecretScanResult:
    repo_root_path = Path(repo_root) if repo_root is not None else None
    resolved_paths = [Path(p) for p in paths]

    decodable = []
    for p in resolved_paths:
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not _is_utf8_decodable(p):
            continue
        decodable.append(p)

    internal_matches = _collect_matches_internal(decodable, repo_root_path)

    if repo_root_path is not None:
        allowlist_entries, allowlist_valid = _load_allowlist(repo_root_path)
        final_matches, allowed, unused = _apply_allowlist(internal_matches, allowlist_entries, allowlist_valid)
    else:
        final_matches = [_strip_hash(m) for m in internal_matches]
        allowed = []
        unused = []

    final_matches.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    allowed.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    unused.sort(key=lambda e: (e["file"], e["type"]))

    flagged = len(final_matches) > 0
    notified, notification_delivery_error = _maybe_notify(final_matches, flagged)

    gate_version_str = _gate_version_string(_detect_secrets_version())

    return SecretScanResult(
        scope="precommit",
        gate_version=gate_version_str,
        flagged=flagged,
        matches=final_matches,
        allowed=allowed,
        unused_allowlist_entries=unused,
        notified=notified,
        notification_delivery_error=notification_delivery_error,
        cache_hit=False,
    )


def gate_version(repo_root) -> str:
    return _gate_version_string(_detect_secrets_version())


def propose(repo_root) -> dict:
    repo_root_path = Path(repo_root)
    allowlist_entries, allowlist_valid = _load_allowlist(repo_root_path)
    if not allowlist_valid:
        raise AllowlistInvalidError(f"{ALLOWLIST_FILENAME} is invalid")

    all_files = list(_iter_candidate_files(repo_root_path))
    decodable_files = [f for f in all_files if _is_utf8_decodable(f)]
    internal_matches = _collect_matches_internal(decodable_files, repo_root_path)

    covered = {(e["file"], e["type"], e["hashed_secret"]) for e in allowlist_entries}

    new_entries = []
    seen_new = set()
    ineligible = []

    for m in internal_matches:
        hashed = "sha1:" + m["secret_hash"]
        key = (m["file"], m["rule_id"], hashed)
        if key in covered:
            continue

        if m["file"].startswith("verification/") or m["file"].startswith("specs/"):
            reason = "planted-fixture"
        elif m["rule_id"] == "Hex High Entropy String":
            reason = "public-constant"
        else:
            ineligible.append({"file": m["file"], "line": m["line"], "rule_id": m["rule_id"]})
            continue

        if key not in seen_new:
            seen_new.add(key)
            new_entries.append({"file": m["file"], "type": m["rule_id"], "hashed_secret": hashed, "reason": reason})

    full_entries = list(allowlist_entries) + new_entries
    full_entries.sort(key=lambda e: (e["file"], e["type"], e["hashed_secret"]))
    ineligible.sort(key=lambda e: (e["file"], e["line"], e["rule_id"]))

    return {
        "allowlist": {"version": 1, "entries": full_entries},
        "ineligible": ineligible,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _flag_value(args: list, i: int, name: str):
    arg = args[i]
    prefix = name + "="
    if arg.startswith(prefix):
        return arg[len(prefix):], i + 1, False
    if i + 1 >= len(args):
        return None, i + 1, True
    return args[i + 1], i + 2, False


def _git_pending_files(repo_root: Path) -> list:
    names = set()
    commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    ]
    for cmd in commands:
        try:
            proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
        except Exception:
            return []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                names.add(line)
    return [repo_root / n for n in sorted(names)]


def _resolve_precommit_files(files: list, repo_root: Path) -> list:
    if files:
        resolved = []
        for f in files:
            p = Path(f)
            if not p.is_absolute():
                p = repo_root / p
            resolved.append(p)
        return resolved
    return _git_pending_files(repo_root)


def _print_result(result: SecretScanResult, fmt: str) -> None:
    if fmt == "json":
        sys.stdout.write(json.dumps(result.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write("FLAGGED\n" if result.flagged else "CLEAN\n")
        for m in result.matches:
            sys.stdout.write(f"{m['file']}:{m['line']} {m['rule_id']} ({m['risk_tier']})\n")


def main(argv: list) -> int:
    args = list(argv)
    if args and args[0] == "secret-scan":
        args = args[1:]

    subcommand = "full"
    if args and args[0] in ("precommit", "propose"):
        subcommand = args[0]
        args = args[1:]
    elif args and not args[0].startswith("--"):
        sys.stderr.write(f"unknown subcommand: {args[0]}\n")
        return 2

    allowed_flags = {
        "full": {"--repo-root", "--format"},
        "precommit": {"--repo-root", "--format", "--files"},
        "propose": {"--repo-root"},
    }

    repo_root_arg = None
    fmt_arg = None
    files_args = []

    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("--"):
            sys.stderr.write(f"unknown argument: {arg}\n")
            return 2
        name = arg.split("=", 1)[0]
        if name not in allowed_flags[subcommand]:
            sys.stderr.write(f"unknown argument: {arg}\n")
            return 2

        value, i, err = _flag_value(args, i, name)
        if err:
            sys.stderr.write(f"missing value for {name}\n")
            return 2

        if name == "--repo-root":
            repo_root_arg = value
        elif name == "--format":
            fmt_arg = value
        elif name == "--files":
            files_args.append(value)

    fmt = fmt_arg if fmt_arg is not None else "text"
    if fmt not in ("json", "text"):
        sys.stderr.write(f"invalid format: {fmt}\n")
        return 2

    repo_root_path = Path(repo_root_arg) if repo_root_arg is not None else Path.cwd()

    if subcommand == "propose":
        try:
            proposal = propose(repo_root_path)
        except AllowlistInvalidError as e:
            sys.stderr.write(f"{e}\n")
            return 2
        sys.stdout.write(json.dumps(proposal, indent=2) + "\n")
        ineligible = (
            proposal.get("ineligible", [])
            if isinstance(proposal, dict)
            else getattr(proposal, "ineligible", [])
        )
        return 1 if ineligible else 0

    if subcommand == "precommit":
        file_paths = _resolve_precommit_files(files_args, repo_root_path)
        result = scan_files(file_paths, repo_root=repo_root_path)
    else:
        result = scan(repo_root_path)

    _print_result(result, fmt)
    return 1 if result.flagged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))