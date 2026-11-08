from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", ".hotdocs", "node_modules"}
LOW_RISK_TYPES = {"Base64 High Entropy String", "Hex High Entropy String"}
EXCLUDED_PLUGINS = {"KeywordDetector", "IPPublicDetector"}

_FILE_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_HASH_RE = re.compile(r"^sha1:[0-9a-f]{40}$")
_DECISION_RE = re.compile(r"^D(\d+)\.md$")


class AllowlistInvalidError(Exception):
    pass


def _dual_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@dataclass
class SecretScanResult:
    scope: str
    gate_version: "str | None"
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: "dict | None"
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


@dataclass
class AllowlistProposal:
    allowlist: dict
    ineligible: list

    def to_dict(self) -> dict:
        return {"allowlist": self.allowlist, "ineligible": self.ineligible}


# ---------------------------------------------------------------------------
# Dependency loading (cache-manager)
# ---------------------------------------------------------------------------

def _tool_root() -> "Path | None":
    p = Path(__file__).resolve()
    for parent in p.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_module_from_dir(dep_dir: Path, module_name: str):
    flat = dep_dir / f"{module_name}.py"
    pkg_dir = dep_dir / module_name
    pkg_init = pkg_dir / "__init__.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, str(flat))
    elif pkg_init.is_file():
        spec = importlib.util.spec_from_file_location(
            module_name, str(pkg_init), submodule_search_locations=[str(pkg_dir)]
        )
    else:
        return None
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_cache_manager(repo_root: Path):
    module_name = "cache_manager"
    dep_slug = "cache-manager"
    try:
        repo_dep_dir = Path(repo_root) / "gen" / dep_slug
        if repo_dep_dir.is_dir():
            return _load_module_from_dir(repo_dep_dir, module_name)
        tool_root = _tool_root()
        if tool_root is not None:
            tool_dep_dir = tool_root / "gen" / dep_slug
            if tool_dep_dir.is_dir():
                return _load_module_from_dir(tool_dep_dir, module_name)
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# File enumeration / hashing
# ---------------------------------------------------------------------------

def _iter_text_files(repo_root: Path):
    for root, dirs, fnames in os.walk(repo_root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for fname in sorted(fnames):
            fpath = Path(root) / fname
            try:
                content = fpath.read_bytes()
                content.decode("utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            relpath = fpath.relative_to(repo_root).as_posix()
            yield relpath, content, fpath


def _hash_file_set(entries) -> str:
    h = hashlib.sha256()
    for relpath, content in sorted(entries, key=lambda x: x[0]):
        h.update(relpath.encode("utf-8"))
        h.update(b"\x00")
        h.update(content)
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# detect-secrets integration
# ---------------------------------------------------------------------------

def _gate_version_string() -> str:
    v = importlib.metadata.version("detect-secrets")
    return f"secret_scanner@3.1.0+detect-secrets.{v}"


def _plugin_names() -> list:
    from detect_secrets.core.plugins.util import get_mapping_from_secret_type_to_class

    mapping = get_mapping_from_secret_type_to_class()
    names = set()
    for cls in mapping.values():
        name = cls.__name__
        if name in EXCLUDED_PLUGINS:
            continue
        names.add(name)
    return sorted(names)


def _risk_tier(rule_id: str) -> str:
    return "low" if rule_id in LOW_RISK_TYPES else "high"


def _detect_secrets_findings(file_specs) -> list:
    from detect_secrets import SecretsCollection
    from detect_secrets.settings import transient_settings

    config = {"plugins_used": [{"name": n} for n in _plugin_names()], "filters_used": []}
    collection = SecretsCollection()
    path_to_report = {}
    with transient_settings(config):
        for report_path, abspath in file_specs:
            path_str = str(abspath)
            path_to_report[path_str] = report_path
            collection.scan_file(path_str)

    findings = []
    for filename, secret in collection:
        report_path = path_to_report.get(filename, filename)
        rule_id = secret.type
        findings.append(
            {
                "file": report_path,
                "line": secret.line_number,
                "rule_id": rule_id,
                "risk_tier": _risk_tier(rule_id),
                "secret_hash": secret.secret_hash,
            }
        )
    return findings


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

def _is_valid_relpath(p: str) -> bool:
    if not _FILE_RE.match(p):
        return False
    if p.startswith("/"):
        return False
    if ".." in p.split("/"):
        return False
    return True


def _validate_entry(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    if set(entry.keys()) != {"file", "type", "hashed_secret", "reason"}:
        return False
    file_ = entry["file"]
    type_ = entry["type"]
    hashed = entry["hashed_secret"]
    reason = entry["reason"]
    if not isinstance(file_, str) or not _is_valid_relpath(file_):
        return False
    if not isinstance(type_, str):
        return False
    if not isinstance(hashed, str) or not _HASH_RE.match(hashed):
        return False
    if reason == "planted-fixture":
        if not (file_.startswith("verification/") or file_.startswith("specs/")):
            return False
    elif reason == "public-constant":
        if type_ != "Hex High Entropy String":
            return False
    else:
        return False
    return True


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    result = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def _find_seal_hash(repo_root: Path) -> "str | None":
    decisions_dir = repo_root / "specs" / "decisions"
    if not decisions_dir.is_dir():
        return None
    best_n = -1
    best_hash = None
    for entry in decisions_dir.iterdir():
        m = _DECISION_RE.match(entry.name)
        if not m:
            continue
        n = int(m.group(1))
        try:
            text = entry.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        fm = _parse_frontmatter(text)
        if fm.get("status") != "ratified":
            continue
        if "allowlist_sha256" not in fm:
            continue
        if n > best_n:
            best_n = n
            best_hash = fm["allowlist_sha256"]
    return best_hash


def _load_allowlist(repo_root: Path):
    path = repo_root / ".secret-allowlist.json"
    if not path.exists():
        return True, []
    try:
        raw = path.read_bytes()
    except OSError:
        return True, []
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return False, []
    if not isinstance(data, dict) or set(data.keys()) != {"version", "entries"}:
        return False, []
    version = data.get("version")
    if type(version) is not int or version != 1:
        return False, []
    entries = data.get("entries")
    if not isinstance(entries, list):
        return False, []
    for entry in entries:
        if not _validate_entry(entry):
            return False, []
    if entries:
        seal_hash = _find_seal_hash(repo_root)
        actual_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
        if seal_hash != actual_hash:
            return False, []
    return True, entries


def _apply_allowlist(findings, valid, entries):
    used = set()
    matches = []
    allowed = []
    for f in findings:
        key = (f["file"], f["rule_id"], "sha1:" + f["secret_hash"])
        matched_idx = None
        if valid:
            for idx, e in enumerate(entries):
                if (e["file"], e["type"], e["hashed_secret"]) == key:
                    matched_idx = idx
                    break
        if matched_idx is not None:
            used.add(matched_idx)
            allowed.append({"rule_id": f["rule_id"], "file": f["file"], "line": f["line"]})
        else:
            matches.append(
                {
                    "rule_id": f["rule_id"],
                    "risk_tier": f["risk_tier"],
                    "file": f["file"],
                    "line": f["line"],
                }
            )

    unused = []
    if valid:
        for idx, e in enumerate(entries):
            if idx not in used:
                unused.append({"file": e["file"], "type": e["type"]})
    else:
        matches.append(
            {
                "rule_id": "allowlist-invalid",
                "risk_tier": "high",
                "file": ".secret-allowlist.json",
                "line": 1,
            }
        )

    matches.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    allowed.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    unused.sort(key=lambda e: (e["file"], e["type"]))
    return matches, allowed, unused


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def _maybe_notify(matches):
    webhook_url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL")
    flagged = len(matches) > 0
    has_high = any(m["risk_tier"] == "high" for m in matches)
    due = flagged or has_high
    notified = bool(due and webhook_url)
    notification_delivery_error = None
    if notified:
        try:
            body = json.dumps({"matches": matches, "flagged": flagged}).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            category = "auth" if e.code in (401, 403) else "network"
            notification_delivery_error = {"category": category, "message": str(e)}
        except (socket.timeout, TimeoutError) as e:
            notification_delivery_error = {"category": "timeout", "message": str(e)}
        except Exception as e:
            notification_delivery_error = {"category": "network", "message": str(e)}
    return notified, notification_delivery_error


def _result_from_payload(payload, cache_hit: bool) -> SecretScanResult:
    return SecretScanResult(
        scope=_dual_get(payload, "scope", "full"),
        gate_version=_dual_get(payload, "gate_version"),
        flagged=_dual_get(payload, "flagged", False),
        matches=_dual_get(payload, "matches", []),
        allowed=_dual_get(payload, "allowed", []),
        unused_allowlist_entries=_dual_get(payload, "unused_allowlist_entries", []),
        notified=_dual_get(payload, "notified", False),
        notification_delivery_error=_dual_get(payload, "notification_delivery_error"),
        cache_hit=cache_hit,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def gate_version(repo_root) -> str:
    return _gate_version_string()


def scan(repo_root) -> SecretScanResult:
    repo_root = Path(repo_root).resolve()
    all_entries = list(_iter_text_files(repo_root))
    spec_entries = [(r, c) for r, c, _ in all_entries if r.startswith("specs/")]
    other_entries = [(r, c) for r, c, _ in all_entries if not r.startswith("specs/")]
    spec_bundle_hash = _hash_file_set(spec_entries)
    gate_inputs_hash = _hash_file_set(other_entries)
    gv = _gate_version_string()
    model_pin = "none"

    cache_manager = None
    try:
        cache_manager = _load_cache_manager(repo_root)
    except Exception:
        cache_manager = None

    cache_key = None
    if cache_manager is not None:
        try:
            cache_key = cache_manager.CacheKey(
                spec_bundle_hash=spec_bundle_hash,
                gate_inputs_hash=gate_inputs_hash,
                gate_version=gv,
                model_pin=model_pin,
            )
            cached = cache_manager.get(cache_key, repo_root=repo_root)
        except Exception:
            cached = None
        if cached is not None:
            payload = _dual_get(cached, "payload")
            if payload is not None:
                return _result_from_payload(payload, cache_hit=True)

    valid, alist_entries = _load_allowlist(repo_root)
    file_specs = [(r, abspath) for r, c, abspath in all_entries]
    findings = _detect_secrets_findings(file_specs)
    matches, allowed, unused = _apply_allowlist(findings, valid, alist_entries)
    flagged = len(matches) > 0
    notified, notif_error = _maybe_notify(matches)

    result = SecretScanResult(
        scope="full",
        gate_version=gv,
        flagged=flagged,
        matches=matches,
        allowed=allowed,
        unused_allowlist_entries=unused,
        notified=notified,
        notification_delivery_error=notif_error,
        cache_hit=False,
    )

    if cache_manager is not None and cache_key is not None:
        try:
            cached_result = cache_manager.CachedResult(
                gate_type="secret_scanner",
                payload=result.to_dict(),
                stored_at=_now_iso(),
            )
            cache_manager.put(cache_key, cached_result, repo_root=repo_root)
        except Exception:
            pass

    return result


def scan_files(paths, repo_root=None) -> SecretScanResult:
    gv = _gate_version_string()
    resolved_repo_root = Path(repo_root).resolve() if repo_root is not None else None

    resolved = []
    for p in paths:
        p = Path(p)
        if resolved_repo_root is not None and not p.is_absolute():
            abspath = resolved_repo_root / p
        else:
            abspath = p
        if resolved_repo_root is not None:
            try:
                report_path = abspath.resolve().relative_to(resolved_repo_root).as_posix()
            except ValueError:
                report_path = abspath.as_posix()
        else:
            report_path = str(p)
        resolved.append((report_path, abspath))

    filtered = []
    for report_path, abspath in resolved:
        parts = Path(report_path).parts if resolved_repo_root is not None else abspath.parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        try:
            content = abspath.read_bytes()
            content.decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        filtered.append((report_path, abspath))

    valid, alist_entries = True, []
    if resolved_repo_root is not None:
        valid, alist_entries = _load_allowlist(resolved_repo_root)

    findings = _detect_secrets_findings(filtered)
    matches, allowed, unused = _apply_allowlist(findings, valid, alist_entries)
    flagged = len(matches) > 0
    notified, notif_error = _maybe_notify(matches)

    return SecretScanResult(
        scope="precommit",
        gate_version=gv,
        flagged=flagged,
        matches=matches,
        allowed=allowed,
        unused_allowlist_entries=unused,
        notified=notified,
        notification_delivery_error=notif_error,
        cache_hit=False,
    )


def propose(repo_root) -> AllowlistProposal:
    repo_root = Path(repo_root).resolve()
    valid, entries = _load_allowlist(repo_root)
    if not valid:
        raise AllowlistInvalidError("the current .secret-allowlist.json is invalid")

    file_specs = [(r, abspath) for r, c, abspath in _iter_text_files(repo_root)]
    findings = _detect_secrets_findings(file_specs)

    covered = {(e["file"], e["type"], e["hashed_secret"]) for e in entries}

    new_entries = []
    ineligible = []
    seen_new = set()
    for f in findings:
        hashed = "sha1:" + f["secret_hash"]
        key = (f["file"], f["rule_id"], hashed)
        if key in covered:
            continue
        file_ = f["file"]
        rule_id = f["rule_id"]
        if file_.startswith("verification/") or file_.startswith("specs/"):
            reason = "planted-fixture"
        elif rule_id == "Hex High Entropy String":
            reason = "public-constant"
        else:
            ineligible.append({"file": file_, "line": f["line"], "rule_id": rule_id})
            continue
        if key in seen_new:
            continue
        seen_new.add(key)
        new_entries.append(
            {"file": file_, "type": rule_id, "hashed_secret": hashed, "reason": reason}
        )

    all_entries = list(entries) + new_entries
    all_entries.sort(key=lambda e: (e["file"], e["type"], e["hashed_secret"]))
    ineligible.sort(key=lambda e: (e["file"], e["line"], e["rule_id"]))

    return AllowlistProposal(
        allowlist={"version": 1, "entries": all_entries},
        ineligible=ineligible,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _git_diff_files(repo_root: Path) -> list:
    try:
        out1 = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        out2 = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    files = set(out1.stdout.splitlines()) | set(out2.stdout.splitlines())
    return sorted(f for f in files if f)


def _print_result(result, fmt: str) -> None:
    if fmt == "json":
        d = result.to_dict() if hasattr(result, "to_dict") else result
        print(json.dumps(d, indent=2))
    else:
        flagged = _dual_get(result, "flagged", False)
        print("FLAGGED" if flagged else "CLEAN")
        for m in _dual_get(result, "matches", []):
            file_ = _dual_get(m, "file")
            line = _dual_get(m, "line")
            rule_id = _dual_get(m, "rule_id")
            risk_tier = _dual_get(m, "risk_tier")
            print(f"{file_}:{line} {rule_id} [{risk_tier}]")


def _take_flag_value(args, i, flag_name):
    arg = args[i]
    if "=" in arg:
        value = arg.split("=", 1)[1]
        if value == "":
            return None, i, True
        return value, i + 1, False
    if i + 1 >= len(args):
        return None, i, True
    return args[i + 1], i + 2, False


def main(argv) -> int:
    args = list(argv)

    if args and args[0] == "secret-scan":
        args = args[1:]

    subcommand = "scan"
    if args and args[0] in ("precommit", "propose"):
        subcommand = args[0]
        args = args[1:]
    elif args and not args[0].startswith("--"):
        print(f"usage error: unknown subcommand {args[0]!r}", file=sys.stderr)
        return 2

    repo_root_val = None
    fmt = None
    files = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--repo-root" or arg.startswith("--repo-root="):
            value, i, err = _take_flag_value(args, i, "--repo-root")
            if err:
                print("usage error: --repo-root requires a value", file=sys.stderr)
                return 2
            repo_root_val = value
        elif arg == "--format" or arg.startswith("--format="):
            if subcommand == "propose":
                print("usage error: propose accepts no --format", file=sys.stderr)
                return 2
            value, i, err = _take_flag_value(args, i, "--format")
            if err:
                print("usage error: --format requires a value", file=sys.stderr)
                return 2
            if value not in ("json", "text"):
                print(f"usage error: invalid --format {value!r}", file=sys.stderr)
                return 2
            fmt = value
        elif arg == "--files" or arg.startswith("--files="):
            if subcommand != "precommit":
                print("usage error: --files is only valid for precommit", file=sys.stderr)
                return 2
            value, i, err = _take_flag_value(args, i, "--files")
            if err:
                print("usage error: --files requires a value", file=sys.stderr)
                return 2
            files.append(value)
        else:
            print(f"usage error: unknown argument {arg!r}", file=sys.stderr)
            return 2

    repo_root_path = Path(repo_root_val) if repo_root_val is not None else Path.cwd()
    if fmt is None:
        fmt = "text"

    if subcommand == "propose":
        try:
            proposal = propose(repo_root_path)
        except AllowlistInvalidError as e:
            print(f"usage error: {e}", file=sys.stderr)
            return 2
        print(json.dumps(proposal.to_dict(), indent=2))
        return 1 if proposal.ineligible else 0

    if subcommand == "precommit":
        if not files:
            files = _git_diff_files(repo_root_path)
        resolved_paths = []
        for f in files:
            fp = Path(f)
            if not fp.is_absolute():
                fp = repo_root_path / fp
            resolved_paths.append(fp)
        result = scan_files(resolved_paths, repo_root=repo_root_path)
    else:
        result = scan(repo_root_path)

    _print_result(result, fmt)
    flagged = _dual_get(result, "flagged", False)
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))