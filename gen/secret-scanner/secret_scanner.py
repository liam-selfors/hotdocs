"""Secret Scanner: whole-repository secret detection via detect-secrets."""

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

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", ".hotdocs", "node_modules"}

EXCLUDED_PLUGINS = {"KeywordDetector", "IPPublicDetector"}

LOW_RISK_RULE_IDS = {"Base64 High Entropy String", "Hex High Entropy String"}

ALLOWLIST_FILENAME = ".secret-allowlist.json"

_FILE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")
_HASHED_SECRET_RE = re.compile(r"^sha1:[0-9a-f]{40}$")


class AllowlistInvalidError(Exception):
    pass


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
class _RawFinding:
    file: str
    line: int
    rule_id: str
    risk_tier: str
    secret_hash: str


def _dual_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _gate_version_string() -> str:
    version = importlib.metadata.version("detect-secrets")
    return f"secret_scanner@3.1.0+detect-secrets.{version}"


def gate_version(repo_root) -> str:
    return _gate_version_string()


def _risk_tier(rule_id: str) -> str:
    return "low" if rule_id in LOW_RISK_RULE_IDS else "high"


def _build_plugins_config() -> dict:
    from detect_secrets.core.plugins.util import get_mapping_from_secret_type_to_class

    mapping = get_mapping_from_secret_type_to_class()
    seen = set()
    plugins_used = []
    for cls in mapping.values():
        name = cls.__name__
        if name in EXCLUDED_PLUGINS or name in seen:
            continue
        seen.add(name)
        plugins_used.append({"name": name})
    return {"plugins_used": plugins_used, "filters_used": []}


def _raw_scan(file_list) -> "list[_RawFinding]":
    from detect_secrets import SecretsCollection
    from detect_secrets.settings import transient_settings

    config = _build_plugins_config()
    collection = SecretsCollection()
    with transient_settings(config):
        for _rel, full_path in file_list:
            collection.scan_file(str(full_path))

    path_map = {str(full_path): rel for rel, full_path in file_list}
    findings = []
    for filename, secret in collection:
        rel = path_map.get(filename, filename)
        rule_id = secret.type
        findings.append(
            _RawFinding(
                file=rel,
                line=secret.line_number,
                rule_id=rule_id,
                risk_tier=_risk_tier(rule_id),
                secret_hash=secret.secret_hash,
            )
        )
    return findings


def _collect_files(repo_root: Path):
    collected = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fname in sorted(filenames):
            full = Path(dirpath) / fname
            try:
                content = full.read_bytes()
                content.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = full.relative_to(repo_root).as_posix()
            collected.append((rel, full, content))
    return collected


def _full_raw_findings(repo_root: Path):
    collected = _collect_files(repo_root)
    file_list = [(rel, full) for rel, full, _content in collected]
    return _raw_scan(file_list), collected


def _hash_fileset(files) -> str:
    h = hashlib.sha256()
    for rel, content in sorted(files, key=lambda x: x[0]):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(content)
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _parse_frontmatter(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    result = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return None


def _find_sealed_hash(repo_root: Path):
    decisions_dir = Path(repo_root) / "specs" / "decisions"
    if not decisions_dir.is_dir():
        return None
    pattern = re.compile(r"^D(\d+)\.md$")
    best_n = -1
    best_hash = None
    for entry in decisions_dir.iterdir():
        m = pattern.match(entry.name)
        if not m:
            continue
        n = int(m.group(1))
        try:
            text = entry.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        frontmatter = _parse_frontmatter(text)
        if frontmatter is None:
            continue
        if frontmatter.get("status") != "ratified":
            continue
        if "allowlist_sha256" not in frontmatter:
            continue
        if n > best_n:
            best_n = n
            best_hash = frontmatter["allowlist_sha256"]
    return best_hash


def _validate_entry(entry) -> bool:
    if not isinstance(entry, dict) or set(entry.keys()) != {"file", "type", "hashed_secret", "reason"}:
        return False
    file_ = entry["file"]
    type_ = entry["type"]
    hashed_secret = entry["hashed_secret"]
    reason = entry["reason"]

    if not isinstance(file_, str) or not file_ or file_.startswith("/"):
        return False
    if not _FILE_PATH_RE.match(file_):
        return False
    if ".." in file_.split("/"):
        return False
    if not isinstance(type_, str) or not type_:
        return False
    if not isinstance(hashed_secret, str) or not _HASHED_SECRET_RE.match(hashed_secret):
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


def _load_and_validate_allowlist(repo_root: Path):
    path = Path(repo_root) / ALLOWLIST_FILENAME
    if not path.exists():
        return [], True

    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return [], False

    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return [], False

    if not isinstance(data, dict) or set(data.keys()) != {"version", "entries"}:
        return [], False
    if data.get("version") != 1:
        return [], False
    entries = data.get("entries")
    if not isinstance(entries, list):
        return [], False
    for entry in entries:
        if not _validate_entry(entry):
            return [], False

    if entries:
        sealed_hash = _find_sealed_hash(repo_root)
        actual_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
        if sealed_hash is None or sealed_hash != actual_hash:
            return [], False

    return entries, True


def _categorize_webhook_error(exc) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return "auth" if exc.code in (401, 403) else "network"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return "timeout"
        return "network"
    return "network"


def _attempt_webhook(url: str, scope: str, flagged: bool, matches: list):
    payload = json.dumps(
        {"source": "secret_scanner", "scope": scope, "flagged": flagged, "matches": matches}
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return None
    except Exception as exc:
        category = _categorize_webhook_error(exc)
        return {"category": category, "message": str(exc)}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_result(scope, gate_version_str, raw_findings, repo_root, apply_allowlist) -> SecretScanResult:
    matches = []
    allowed = []
    unused_entries = []

    if apply_allowlist:
        entries, valid = _load_and_validate_allowlist(repo_root)
    else:
        entries, valid = [], True

    if not valid:
        for f in raw_findings:
            matches.append({"rule_id": f.rule_id, "risk_tier": f.risk_tier, "file": f.file, "line": f.line})
        matches.append(
            {"rule_id": "allowlist-invalid", "risk_tier": "high", "file": ALLOWLIST_FILENAME, "line": 1}
        )
    else:
        matched_idx = set()
        for f in raw_findings:
            hashed_secret = "sha1:" + f.secret_hash
            match_idx = None
            for idx, entry in enumerate(entries):
                if (
                    entry["file"] == f.file
                    and entry["type"] == f.rule_id
                    and entry["hashed_secret"] == hashed_secret
                ):
                    match_idx = idx
                    break
            if match_idx is not None:
                matched_idx.add(match_idx)
                allowed.append({"rule_id": f.rule_id, "file": f.file, "line": f.line})
            else:
                matches.append(
                    {"rule_id": f.rule_id, "risk_tier": f.risk_tier, "file": f.file, "line": f.line}
                )
        for idx, entry in enumerate(entries):
            if idx not in matched_idx:
                unused_entries.append({"file": entry["file"], "type": entry["type"]})

    matches.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    allowed.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    unused_entries.sort(key=lambda e: (e["file"], e["type"]))

    flagged = len(matches) > 0
    has_high = any(m["risk_tier"] == "high" for m in matches)

    webhook_url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL") or None
    due = (flagged or has_high) and bool(webhook_url)
    notified = bool(due)
    notification_delivery_error = None
    if due:
        notification_delivery_error = _attempt_webhook(webhook_url, scope, flagged, matches)

    return SecretScanResult(
        scope=scope,
        gate_version=gate_version_str,
        flagged=flagged,
        matches=matches,
        allowed=allowed,
        unused_allowlist_entries=unused_entries,
        notified=notified,
        notification_delivery_error=notification_delivery_error,
        cache_hit=False,
    )


def _result_from_payload(payload, cache_hit: bool) -> SecretScanResult:
    return SecretScanResult(
        scope=_dual_get(payload, "scope"),
        gate_version=_dual_get(payload, "gate_version"),
        flagged=_dual_get(payload, "flagged"),
        matches=_dual_get(payload, "matches") or [],
        allowed=_dual_get(payload, "allowed") or [],
        unused_allowlist_entries=_dual_get(payload, "unused_allowlist_entries") or [],
        notified=_dual_get(payload, "notified"),
        notification_delivery_error=_dual_get(payload, "notification_delivery_error"),
        cache_hit=cache_hit,
    )


def _load_cache_manager(repo_root: Path):
    try:
        dep_dir = Path(repo_root) / "gen" / "cache-manager"
        flat_path = dep_dir / "cache_manager.py"
        pkg_path = dep_dir / "cache_manager" / "__init__.py"
        if flat_path.is_file():
            module_path = flat_path
        elif pkg_path.is_file():
            module_path = pkg_path
        else:
            return None
        spec = importlib.util.spec_from_file_location("cache_manager", module_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules["cache_manager"] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def scan(repo_root) -> SecretScanResult:
    repo_root = Path(repo_root)
    raw_findings, collected = _full_raw_findings(repo_root)
    gv = _gate_version_string()

    cm = _load_cache_manager(repo_root)
    cache_key = None
    if cm is not None:
        try:
            specs_files = [(rel, content) for rel, _full, content in collected if rel.startswith("specs/")]
            other_files = [
                (rel, content) for rel, _full, content in collected if not rel.startswith("specs/")
            ]
            spec_bundle_hash = _hash_fileset(specs_files)
            gate_inputs_hash = _hash_fileset(other_files)
            cache_key = cm.CacheKey(
                spec_bundle_hash=spec_bundle_hash,
                gate_inputs_hash=gate_inputs_hash,
                gate_version=gv,
                model_pin="none",
            )
        except Exception:
            cache_key = None

        if cache_key is not None:
            payload = None
            try:
                cached = cm.get(cache_key, repo_root=repo_root)
                payload = _dual_get(cached, "payload")
            except Exception:
                payload = None
            if payload is not None:
                try:
                    return _result_from_payload(payload, cache_hit=True)
                except Exception:
                    pass

    result = _build_result(
        scope="full", gate_version_str=gv, raw_findings=raw_findings, repo_root=repo_root, apply_allowlist=True
    )

    if cm is not None and cache_key is not None:
        try:
            payload = result.to_dict()
            cached_result = cm.CachedResult(
                gate_type="secret_scanner", payload=payload, stored_at=_now_iso()
            )
            cm.put(cache_key, cached_result, repo_root=repo_root)
        except Exception:
            pass

    return result


def scan_files(paths, repo_root=None) -> SecretScanResult:
    gv = _gate_version_string()
    repo_root_path = Path(repo_root) if repo_root is not None else None
    file_list = []

    for original in paths:
        original_str = str(original)
        p = Path(original)
        if repo_root_path is not None:
            full = p if p.is_absolute() else repo_root_path / p
        else:
            full = p

        try:
            content = full.read_bytes()
            content.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if any(part in SKIP_DIRS for part in full.parts):
            continue

        if repo_root_path is not None:
            try:
                rel = full.resolve().relative_to(repo_root_path.resolve()).as_posix()
            except ValueError:
                rel = full.as_posix()
        else:
            rel = original_str

        file_list.append((rel, full))

    raw_findings = _raw_scan(file_list)

    return _build_result(
        scope="precommit",
        gate_version_str=gv,
        raw_findings=raw_findings,
        repo_root=repo_root_path,
        apply_allowlist=(repo_root_path is not None),
    )


def propose(repo_root) -> dict:
    repo_root = Path(repo_root)
    entries, valid = _load_and_validate_allowlist(repo_root)
    if not valid:
        raise AllowlistInvalidError(f"invalid allowlist at {repo_root / ALLOWLIST_FILENAME}")

    raw_findings, _collected = _full_raw_findings(repo_root)

    covered = {(e["file"], e["type"], e["hashed_secret"]) for e in entries}
    seen_new = set()
    new_entries = []
    ineligible = []

    for f in raw_findings:
        hashed_secret = "sha1:" + f.secret_hash
        key = (f.file, f.rule_id, hashed_secret)
        if key in covered:
            continue
        if f.file.startswith("verification/") or f.file.startswith("specs/"):
            reason = "planted-fixture"
        elif f.rule_id == "Hex High Entropy String":
            reason = "public-constant"
        else:
            ineligible.append({"file": f.file, "line": f.line, "rule_id": f.rule_id})
            continue
        if key in seen_new:
            continue
        seen_new.add(key)
        new_entries.append(
            {"file": f.file, "type": f.rule_id, "hashed_secret": hashed_secret, "reason": reason}
        )

    all_entries = list(entries) + new_entries
    all_entries.sort(key=lambda e: (e["file"], e["type"], e["hashed_secret"]))
    ineligible.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))

    return {
        "allowlist": {"version": 1, "entries": all_entries},
        "ineligible": ineligible,
    }


def _default_precommit_files(repo_root: Path):
    names = set()
    for cmd in (
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    ):
        try:
            out = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
        except Exception:
            continue
        for line in out.stdout.splitlines():
            line = line.strip()
            if line:
                names.add(line)
    return sorted(names)


def _print_result(result: SecretScanResult, fmt: str):
    if fmt == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        flagged = _dual_get(result, "flagged")
        print("FLAGGED" if flagged else "CLEAN")
        for m in _dual_get(result, "matches") or []:
            file_ = _dual_get(m, "file")
            line_ = _dual_get(m, "line")
            rule_ = _dual_get(m, "rule_id")
            tier_ = _dual_get(m, "risk_tier")
            print(f"{file_}:{line_}: {rule_} ({tier_})")


def main(argv) -> int:
    args = list(argv)
    if args and args[0] == "secret-scan":
        args = args[1:]

    subcommand = None
    if args and args[0] in ("precommit", "propose"):
        subcommand = args[0]
        args = args[1:]

    repo_root = None
    fmt = "text"
    files = []

    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("--"):
            print(f"usage error: unknown argument {arg}", file=sys.stderr)
            return 2

        if "=" in arg:
            flag, value = arg.split("=", 1)
        else:
            flag = arg
            if i + 1 >= len(args):
                print(f"usage error: missing value for {flag}", file=sys.stderr)
                return 2
            value = args[i + 1]
            i += 1

        if flag == "--repo-root":
            repo_root = value
        elif flag == "--format":
            if subcommand == "propose":
                print("usage error: propose accepts no --format", file=sys.stderr)
                return 2
            if value not in ("json", "text"):
                print(f"usage error: invalid --format {value}", file=sys.stderr)
                return 2
            fmt = value
        elif flag == "--files":
            if subcommand != "precommit":
                print("usage error: --files is only valid for precommit", file=sys.stderr)
                return 2
            files.append(value)
        else:
            print(f"usage error: unknown flag {flag}", file=sys.stderr)
            return 2

        i += 1

    repo_root_path = Path(repo_root) if repo_root is not None else Path(".")

    if subcommand == "propose":
        try:
            proposal = propose(repo_root_path)
        except AllowlistInvalidError as exc:
            print(f"usage error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(proposal, indent=2))
        return 1 if len(proposal["ineligible"]) > 0 else 0

    if subcommand == "precommit":
        scoped_files = files if files else _default_precommit_files(repo_root_path)
        resolved_files = []
        for f in scoped_files:
            fp = Path(f)
            resolved_files.append(fp if fp.is_absolute() else repo_root_path / fp)
        result = scan_files(resolved_files, repo_root=repo_root_path)
    else:
        result = scan(repo_root_path)

    _print_result(result, fmt)
    return 1 if _dual_get(result, "flagged") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))