"""Secret scanner: whole-repository committed-secret detection via detect-secrets."""

import dataclasses
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SCANNER_VERSION = "3.1.0"
SKIP_DIRS = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".venv", ".hotdocs", "node_modules"}
)
EXCLUDED_PLUGINS = frozenset({"KeywordDetector", "IPPublicDetector"})
LOW_RISK_TYPES = frozenset({"Base64 High Entropy String", "Hex High Entropy String"})
HEX_TYPE = "Hex High Entropy String"
ALLOWLIST_NAME = ".secret-allowlist.json"
ALLOWLIST_KEYS = frozenset({"version", "entries"})
ENTRY_KEYS = frozenset({"file", "type", "hashed_secret", "reason"})
FIXTURE_PREFIXES = ("verification/", "specs/")
WEBHOOK_ENV = "VAR_COMPLIANCE_WEBHOOK_URL"

_FILE_RE = re.compile(r"[A-Za-z0-9_./-]+")
_HASH_RE = re.compile(r"sha1:[0-9a-f]{40}")
_DECISION_RE = re.compile(r"D(\d+)\.md")


class AllowlistInvalidError(Exception):
    """The allowlist file exists but is invalid or unsealed (R-SECRET-012)."""


@dataclasses.dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: object
    cache_hit: bool

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class AllowlistProposal:
    allowlist: dict
    ineligible: list

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def __getitem__(self, key):
        return getattr(self, key)


# --------------------------------------------------------------------------
# helpers


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _gate_version() -> str:
    return (
        f"secret_scanner@{SCANNER_VERSION}+detect-secrets."
        f"{importlib.metadata.version('detect-secrets')}"
    )


def _readable(path) -> bytes | None:
    if not os.path.isfile(path):
        return None
    data = Path(path).read_bytes()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return data


def _collect_full(repo_root: Path) -> list:
    """Return sorted (rel, abs, content) for every scannable file."""
    files = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in filenames:
            full = os.path.join(dirpath, name)
            data = _readable(full)
            if data is None:
                continue
            rel = os.path.relpath(full, repo_root).replace(os.sep, "/")
            files.append((rel, full, data))
    files.sort(key=lambda f: f[0])
    return files


def _detect(files: list) -> list:
    """Run detect-secrets over (rel, abs, content); return sorted findings."""
    from detect_secrets import SecretsCollection
    from detect_secrets.core.plugins.util import (
        get_mapping_from_secret_type_to_class,
    )
    from detect_secrets.settings import transient_settings

    names = sorted(
        {cls.__name__ for cls in get_mapping_from_secret_type_to_class().values()}
        - EXCLUDED_PLUGINS
    )
    config = {"plugins_used": [{"name": n} for n in names], "filters_used": []}
    findings = []
    with transient_settings(config):
        for rel, full, _data in files:
            collection = SecretsCollection()
            collection.scan_file(str(full))
            for _filename, secret in collection:
                findings.append(
                    (rel, secret.line_number, secret.type, secret.secret_hash)
                )
    findings.sort()
    return findings


def _files_hash(files: list) -> str:
    digest = hashlib.sha256()
    for rel, _full, data in files:
        rel_bytes = rel.encode("utf-8")
        digest.update(f"{len(rel_bytes)}:".encode() + rel_bytes)
        digest.update(f"{len(data)}:".encode() + data)
    return "sha256:" + digest.hexdigest()


def _frontmatter(text: str) -> dict:
    lines = text.splitlines()
    fields = {}
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip("'\"")
    return fields


def _sealed_hash(repo_root: Path):
    candidates = []
    for path in (Path(repo_root) / "specs" / "decisions").glob("D*.md"):
        m = _DECISION_RE.fullmatch(path.name)
        if m is None:
            continue
        fm = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if fm.get("status") == "ratified" and "allowlist_sha256" in fm:
            candidates.append((int(m.group(1)), fm["allowlist_sha256"]))
    return max(candidates)[1] if candidates else None


def _entry_ok(entry) -> bool:
    return (
        isinstance(entry, dict)
        and set(entry) == ENTRY_KEYS
        and isinstance(entry["file"], str)
        and _FILE_RE.fullmatch(entry["file"]) is not None
        and not entry["file"].startswith("/")
        and ".." not in entry["file"].split("/")
        and isinstance(entry["type"], str)
        and isinstance(entry["hashed_secret"], str)
        and _HASH_RE.fullmatch(entry["hashed_secret"]) is not None
        and (
            (
                entry["reason"] == "planted-fixture"
                and entry["file"].startswith(FIXTURE_PREFIXES)
            )
            or (entry["reason"] == "public-constant" and entry["type"] == HEX_TYPE)
        )
    )


def _load_allowlist(repo_root: Path) -> list:
    """The one shared allowlist loader: entries, or AllowlistInvalidError."""
    path = Path(repo_root) / ALLOWLIST_NAME
    if not path.is_file():
        return []
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise AllowlistInvalidError(f"not valid JSON: {exc}") from exc
    if not (
        isinstance(doc, dict)
        and set(doc) == ALLOWLIST_KEYS
        and type(doc["version"]) is int
        and doc["version"] == 1
        and isinstance(doc["entries"], list)
        and all(_entry_ok(e) for e in doc["entries"])
    ):
        raise AllowlistInvalidError("allowlist does not follow R-SECRET-012")
    entries = doc["entries"]
    if entries and _sealed_hash(repo_root) != (
        "sha256:" + hashlib.sha256(raw).hexdigest()
    ):
        raise AllowlistInvalidError("allowlist is not sealed by a ratified decision")
    return entries


def _match(rel, line, rule_id) -> dict:
    return {
        "rule_id": rule_id,
        "risk_tier": "low" if rule_id in LOW_RISK_TYPES else "high",
        "file": rel,
        "line": line,
    }


def _sort_key(item):
    return (item["file"], item["line"], item["rule_id"])


def _assemble(scope, gv, findings, entries, invalid) -> SecretScanResult:
    matches, allowed, used = [], [], set()
    for rel, line, rule_id, secret_hash in findings:
        hits = [
            i
            for i, e in enumerate(entries)
            if e["file"] == rel
            and e["type"] == rule_id
            and e["hashed_secret"] == "sha1:" + secret_hash
        ]
        if hits:
            used.update(hits)
            allowed.append({"rule_id": rule_id, "file": rel, "line": line})
        else:
            matches.append(_match(rel, line, rule_id))
    if invalid:
        matches.append(
            {
                "rule_id": "allowlist-invalid",
                "risk_tier": "high",
                "file": ALLOWLIST_NAME,
                "line": 1,
            }
        )
    unused = sorted(
        (
            {"file": e["file"], "type": e["type"]}
            for i, e in enumerate(entries)
            if i not in used
        ),
        key=lambda u: (u["file"], u["type"]),
    )
    matches.sort(key=_sort_key)
    allowed.sort(key=_sort_key)
    result = SecretScanResult(
        scope=scope,
        gate_version=gv,
        flagged=bool(matches),
        matches=matches,
        allowed=allowed,
        unused_allowlist_entries=unused,
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )
    _notify(result)
    return result


def _allowlist_state(repo_root):
    try:
        return _load_allowlist(repo_root), False
    except AllowlistInvalidError:
        return [], True


def _category(exc) -> str:
    if getattr(exc, "code", None) in (401, 403):
        return "auth"
    if isinstance(exc, TimeoutError) or isinstance(
        getattr(exc, "reason", None), TimeoutError
    ):
        return "timeout"
    return "network"


def _notify(result: SecretScanResult) -> None:
    url = os.environ.get(WEBHOOK_ENV, "")
    result.notified = result.flagged and bool(url)
    if result.notified:
        body = json.dumps({"gate_type": "secret_scanner", **result.to_dict()})
        try:
            request = urllib.request.Request(
                url,
                data=body.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(request, timeout=10)
        except Exception as exc:  # noqa: BLE001 - never raised (R-SECRET-004)
            result.notification_delivery_error = {
                "category": _category(exc),
                "message": str(exc),
            }


def _tool_root() -> Path:
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _load_cache_manager(repo_root: Path):
    try:
        directory = Path(repo_root) / "gen" / "cache-manager"
        if not directory.is_dir():
            directory = _tool_root() / "gen" / "cache-manager"
        flat = directory / "cache_manager.py"
        if flat.is_file():
            spec = importlib.util.spec_from_file_location("cache_manager", flat)
        else:
            spec = importlib.util.spec_from_file_location(
                "cache_manager",
                directory / "cache_manager" / "__init__.py",
                submodule_search_locations=[str(directory / "cache_manager")],
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules["cache_manager"] = module
        spec.loader.exec_module(module)
        return module
    except Exception:  # noqa: BLE001 - unloadable means no lookup
        return None


def _from_payload(payload) -> SecretScanResult:
    fields = {f.name: _get(payload, f.name) for f in dataclasses.fields(SecretScanResult)}
    fields["cache_hit"] = True
    return SecretScanResult(**fields)


# --------------------------------------------------------------------------
# library API


def gate_version(repo_root: Path) -> str:
    return _gate_version()


def scan(repo_root: Path) -> SecretScanResult:
    repo_root = Path(repo_root)
    files = _collect_full(repo_root)
    gv = _gate_version()
    cm = _load_cache_manager(repo_root)
    key = None
    if cm is not None:
        try:
            key = cm.CacheKey(
                spec_bundle_hash=_files_hash(
                    [f for f in files if f[0].startswith("specs/")]
                ),
                gate_inputs_hash=_files_hash(
                    [f for f in files if not f[0].startswith("specs/")]
                ),
                gate_version=gv,
                model_pin="none",
            )
            payload = _get(cm.get(key, repo_root=repo_root), "payload")
            if payload is not None:
                return _from_payload(payload)
        except Exception:  # noqa: BLE001 - a cache failure never fails a scan
            pass
    entries, invalid = _allowlist_state(repo_root)
    result = _assemble("full", gv, _detect(files), entries, invalid)
    try:
        cm.put(
            key,
            cm.CachedResult(
                gate_type="secret_scanner",
                payload=result.to_dict(),
                stored_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
            repo_root=repo_root,
        )
    except Exception:  # noqa: BLE001 - a cache failure never fails a scan
        pass
    return result


def scan_files(paths: list, repo_root: Path | None = None) -> SecretScanResult:
    chosen = {}
    for given in paths:
        given = Path(given)
        if repo_root is None:
            display, full = given.as_posix(), given
        else:
            full = given if given.is_absolute() else Path(repo_root) / given
            display = os.path.relpath(
                full.resolve(), Path(repo_root).resolve()
            ).replace(os.sep, "/")
        chosen.setdefault(display, full)
    files = []
    for display, full in sorted(chosen.items()):
        if any(part in SKIP_DIRS for part in PurePosixPath(display).parts[:-1]):
            continue
        data = _readable(full)
        if data is None:
            continue
        files.append((display, full, data))
    entries, invalid = ([], False) if repo_root is None else _allowlist_state(repo_root)
    return _assemble("precommit", _gate_version(), _detect(files), entries, invalid)


def propose(repo_root: Path) -> AllowlistProposal:
    repo_root = Path(repo_root)
    entries = _load_allowlist(repo_root)
    covered = {(e["file"], e["type"], e["hashed_secret"]) for e in entries}
    proposed = [
        {
            "file": e["file"],
            "type": e["type"],
            "hashed_secret": e["hashed_secret"],
            "reason": e["reason"],
        }
        for e in entries
    ]
    ineligible = []
    for rel, line, rule_id, secret_hash in _detect(_collect_full(repo_root)):
        hashed = "sha1:" + secret_hash
        if (rel, rule_id, hashed) in covered:
            continue
        candidate = {
            "file": rel,
            "type": rule_id,
            "hashed_secret": hashed,
            "reason": "planted-fixture"
            if rel.startswith(FIXTURE_PREFIXES)
            else "public-constant",
        }
        if _entry_ok(candidate):
            proposed.append(candidate)
        else:
            ineligible.append({"file": rel, "line": line, "rule_id": rule_id})
    proposed.sort(key=lambda e: (e["file"], e["type"], e["hashed_secret"]))
    ineligible.sort(key=_sort_key)
    return AllowlistProposal(
        allowlist={"version": 1, "entries": proposed}, ineligible=ineligible
    )


# --------------------------------------------------------------------------
# CLI

_FORMS = {
    "full": (
        {"--repo-root", "--format"},
        "usage: hotdocs secret-scan [--repo-root=<dir>] [--format=json|text]",
    ),
    "precommit": (
        {"--files", "--repo-root", "--format"},
        "usage: hotdocs secret-scan precommit [--files=<path>]... "
        "[--repo-root=<dir>] [--format=json|text]",
    ),
    "propose": (
        {"--repo-root"},
        "usage: hotdocs secret-scan propose [--repo-root=<dir>]",
    ),
}


def _usage_error(cause: str, usage: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(usage, file=sys.stderr)
    return 2


def _git_changed(repo_root: Path) -> list:
    names = set()
    try:
        for cmd in (
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        ):
            out = subprocess.run(
                cmd, cwd=repo_root, capture_output=True, text=True, check=True
            ).stdout
            names.update(line for line in out.splitlines() if line)
    except (OSError, subprocess.CalledProcessError):
        return []
    return sorted(names)


def _emit(result: SecretScanResult, fmt: str) -> int:
    if fmt == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("FLAGGED" if result.flagged else "CLEAN")
        for m in result.matches:
            print(f"{m['file']}:{m['line']}: {m['rule_id']} ({m['risk_tier']})")
    return 1 if result.flagged else 0


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["secret-scan"]:
        args = args[1:]
    form = args[0] if args[:1] in (["precommit"], ["propose"]) else "full"
    if form != "full":
        args = args[1:]
    allowed, usage = _FORMS[form]
    opts = {"--files": [], "--repo-root": os.getcwd(), "--format": "text"}
    i = 0
    while i < len(args):
        name, sep, value = args[i].partition("=")
        if name not in allowed:
            return _usage_error(f"unknown argument: {args[i]}", usage)
        if not sep:
            if i + 1 >= len(args):
                return _usage_error(f"{name} requires a value", usage)
            i += 1
            value = args[i]
        if name == "--files":
            opts[name].append(value)
        else:
            opts[name] = value
        i += 1
    if opts["--format"] not in ("json", "text"):
        return _usage_error(f"invalid --format: {opts['--format']}", usage)
    repo_root = Path(opts["--repo-root"])

    if form == "propose":
        try:
            proposal = propose(repo_root)
        except AllowlistInvalidError as exc:
            print(f"error: invalid allowlist: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(proposal.to_dict(), indent=2))
        return 1 if proposal.ineligible else 0

    if form == "precommit":
        names = opts["--files"] or _git_changed(repo_root)
        result = scan_files([repo_root / n for n in names], repo_root=repo_root)
    else:
        result = scan(repo_root)
    return _emit(result, opts["--format"])
