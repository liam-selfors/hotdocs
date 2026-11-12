"""secret-scanner: whole-repository committed-secret detection.

Detection is delegated entirely to the ``detect-secrets`` library; this
module only selects files, applies the sealed allowlist, builds the
``SecretScanResult``, consults ``cache-manager`` for full scans, and fires
the compliance webhook.
"""

import dataclasses
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCANNER_VERSION = "3.1.0"
GATE_TYPE = "secret_scanner"
ALLOWLIST_NAME = ".secret-allowlist.json"
SKIP_DIRS = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".venv", ".hotdocs", "node_modules"}
)
EXCLUDED_PLUGINS = frozenset({"KeywordDetector", "IPPublicDetector"})
HEX_TYPE = "Hex High Entropy String"
LOW_RISK_TYPES = frozenset({"Base64 High Entropy String", HEX_TYPE})
WEBHOOK_ENV = "VAR_COMPLIANCE_WEBHOOK_URL"
WEBHOOK_TIMEOUT = 10

_FILE_RE = re.compile(r"[A-Za-z0-9_./-]+")
_HASH_RE = re.compile(r"sha1:[0-9a-f]{40}")
_DECISION_RE = re.compile(r"D(\d+)\.md")
_DOC_KEYS = frozenset({"version", "entries"})
_ENTRY_KEYS = frozenset({"file", "type", "hashed_secret", "reason"})
_FIXTURE_ROOTS = ("verification/", "specs/")


class AllowlistInvalidError(Exception):
    """Raised by ``propose`` when the allowlist is invalid or unsealed."""


@dataclasses.dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: Optional[dict]
    cache_hit: bool

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class AllowlistProposal(dict):
    """``{"allowlist": {...}, "ineligible": [...]}``, also readable by attribute."""

    @property
    def allowlist(self) -> dict:
        return self["allowlist"]

    @property
    def ineligible(self) -> list:
        return self["ineligible"]

    def to_dict(self) -> dict:
        return dict(self)


# ---------------------------------------------------------------- versioning


def gate_version(repo_root: Path) -> str:
    """The gate version ``scan(repo_root)`` reports; scans and writes nothing."""
    library_version = importlib.metadata.version("detect-secrets")
    return f"{GATE_TYPE}@{SCANNER_VERSION}+detect-secrets.{library_version}"


# ---------------------------------------------------------------- file selection


def _read_text(path: Path):
    """Return the file's bytes if it is a UTF-8 text file, else ``None``."""
    if not path.is_file():
        return None
    data = path.read_bytes()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return data


def _collect_tree(root: Path) -> list:
    """Every scannable file under ``root`` as ``(relative_posix, path, bytes)``."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            path = Path(dirpath) / name
            data = _read_text(path)
            if data is not None:
                files.append((Path(os.path.relpath(path, root)).as_posix(), path, data))
    return files


def _file_set_hash(files) -> str:
    digest = hashlib.sha256()
    for rel, _path, data in sorted(files, key=lambda item: item[0]):
        rel_bytes = rel.encode("utf-8")
        digest.update(len(rel_bytes).to_bytes(8, "big"))
        digest.update(rel_bytes)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


# ---------------------------------------------------------------- detection


def _detect(files) -> list:
    """Run detect-secrets over ``(reported_path, path)`` pairs."""
    import detect_secrets
    from detect_secrets.core.plugins.util import get_mapping_from_secret_type_to_class
    from detect_secrets.settings import transient_settings

    names = sorted(
        {cls.__name__ for cls in get_mapping_from_secret_type_to_class().values()}
        - EXCLUDED_PLUGINS
    )
    config = {"plugins_used": [{"name": name} for name in names], "filters_used": []}
    findings = []
    with transient_settings(config):
        for reported, path in files:
            collection = detect_secrets.SecretsCollection()
            collection.scan_file(str(path))
            for _filename, secret in collection:
                findings.append(
                    {
                        "file": reported,
                        "line": secret.line_number,
                        "rule_id": secret.type,
                        "secret_hash": secret.secret_hash,
                    }
                )
    return findings


# ---------------------------------------------------------------- allowlist


def _valid_entry(entry) -> bool:
    if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
        return False
    file = entry["file"]
    kind = entry["type"]
    hashed = entry["hashed_secret"]
    reason = entry["reason"]
    if not (
        isinstance(file, str)
        and _FILE_RE.fullmatch(file)
        and not file.startswith("/")
        and ".." not in file.split("/")
    ):
        return False
    if not (isinstance(kind, str) and isinstance(hashed, str) and _HASH_RE.fullmatch(hashed)):
        return False
    if reason == "planted-fixture":
        return file.startswith(_FIXTURE_ROOTS)
    return reason == "public-constant" and kind == HEX_TYPE


def _valid_document(doc) -> bool:
    return (
        isinstance(doc, dict)
        and set(doc) == _DOC_KEYS
        and type(doc["version"]) is int
        and doc["version"] == 1
        and isinstance(doc["entries"], list)
        and all(_valid_entry(entry) for entry in doc["entries"])
    )


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
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def _seal(repo_root: Path):
    """``allowlist_sha256`` of the highest-numbered ratified decision carrying it."""
    decisions = repo_root / "specs" / "decisions"
    numbered = []
    if decisions.is_dir():
        for path in decisions.iterdir():
            match = _DECISION_RE.fullmatch(path.name)
            if match:
                numbered.append((int(match.group(1)), path))
    for _number, path in sorted(numbered, reverse=True):
        fields = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if fields.get("status") == "ratified" and "allowlist_sha256" in fields:
            return fields["allowlist_sha256"]
    return None


def _load_allowlist(repo_root: Path):
    """The one shared loader: ``(valid, entries)``."""
    path = repo_root / ALLOWLIST_NAME
    if not path.is_file():
        return True, []
    raw = path.read_bytes()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except ValueError:
        return False, []
    if not _valid_document(doc):
        return False, []
    if doc["entries"] and "sha256:" + hashlib.sha256(raw).hexdigest() != _seal(repo_root):
        return False, []
    return True, doc["entries"]


# ---------------------------------------------------------------- notification


def _delivery_category(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403):
        return "auth"
    timeouts = (socket.timeout, TimeoutError)
    if isinstance(exc, timeouts) or isinstance(getattr(exc, "reason", None), timeouts):
        return "timeout"
    return "network"


def _notify(url: str, body: dict):
    """POST once; return ``None`` or a ``{category, message}`` delivery error."""
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = urllib.request.urlopen(request, timeout=WEBHOOK_TIMEOUT)
        getattr(response, "close", lambda: None)()
    except Exception as exc:
        return {"category": _delivery_category(exc), "message": str(exc)}
    return None


# ---------------------------------------------------------------- evaluation


def _sort_key(item: dict):
    return (item["file"], item["line"], item["rule_id"])


def _evaluate(scope: str, files, allowlist, version: str) -> SecretScanResult:
    valid, entries = allowlist
    used = [False] * len(entries)
    matches = []
    allowed = []
    for finding in _detect([(rel, path) for rel, path, _data in files]):
        hashed = "sha1:" + finding["secret_hash"]
        hits = [
            index
            for index, entry in enumerate(entries)
            if entry["file"] == finding["file"]
            and entry["type"] == finding["rule_id"]
            and entry["hashed_secret"] == hashed
        ]
        for index in hits:
            used[index] = True
        if hits:
            allowed.append(
                {"rule_id": finding["rule_id"], "file": finding["file"], "line": finding["line"]}
            )
        else:
            matches.append(
                {
                    "rule_id": finding["rule_id"],
                    "risk_tier": "low" if finding["rule_id"] in LOW_RISK_TYPES else "high",
                    "file": finding["file"],
                    "line": finding["line"],
                }
            )
    if not valid:
        matches.append(
            {"rule_id": "allowlist-invalid", "risk_tier": "high", "file": ALLOWLIST_NAME, "line": 1}
        )
    matches.sort(key=_sort_key)
    allowed.sort(key=_sort_key)
    unused = [
        {"file": entry["file"], "type": entry["type"]}
        for entry, was_used in zip(entries, used)
        if not was_used
    ]
    flagged = bool(matches)
    url = os.environ.get(WEBHOOK_ENV) or ""
    # Every high-risk match is a match, so "flagged or any high match" is "flagged".
    notified = flagged and bool(url)
    result = SecretScanResult(
        scope=scope,
        gate_version=version,
        flagged=flagged,
        matches=matches,
        allowed=allowed,
        unused_allowlist_entries=unused,
        notified=notified,
        notification_delivery_error=None,
        cache_hit=False,
    )
    if notified:
        result.notification_delivery_error = _notify(url, result.to_dict())
    return result


# ---------------------------------------------------------------- cache-manager


def _field(obj, name: str):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _dependency_dir(repo_root: Path, slug: str) -> Path:
    local = repo_root / "gen" / slug
    if local.is_dir():
        return local
    for parent in Path(os.path.abspath(__file__)).parents:
        if parent.name == "gen":
            return parent.parent / "gen" / slug
    return local


def _load_cache_manager(repo_root: Path):
    directory = _dependency_dir(repo_root, "cache-manager")
    flat = directory / "cache_manager.py"
    package = directory / "cache_manager" / "__init__.py"
    try:
        if flat.is_file():
            target, search = flat, None
        elif package.is_file():
            target, search = package, [str(package.parent)]
        else:
            return None
        digest = hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:16]
        name = f"_secret_scanner_dep_cache_manager_{digest}"
        spec = importlib.util.spec_from_file_location(
            name, target, submodule_search_locations=search
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _from_payload(payload) -> SecretScanResult:
    return SecretScanResult(
        scope=_field(payload, "scope"),
        gate_version=_field(payload, "gate_version"),
        flagged=_field(payload, "flagged"),
        matches=list(_field(payload, "matches") or []),
        allowed=list(_field(payload, "allowed") or []),
        unused_allowlist_entries=list(_field(payload, "unused_allowlist_entries") or []),
        notified=_field(payload, "notified"),
        notification_delivery_error=_field(payload, "notification_delivery_error"),
        cache_hit=True,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- public API


def scan(repo_root: Path) -> SecretScanResult:
    """Full, cache-aware scan of every text file under ``repo_root``."""
    root = Path(repo_root)
    version = gate_version(root)
    files = _collect_tree(root)
    cache = _load_cache_manager(root)
    key = None
    if cache is not None:
        try:
            key = cache.CacheKey(
                spec_bundle_hash=_file_set_hash([f for f in files if f[0].startswith("specs/")]),
                gate_inputs_hash=_file_set_hash(
                    [f for f in files if not f[0].startswith("specs/")]
                ),
                gate_version=version,
                model_pin="none",
            )
            payload = _field(cache.get(key, repo_root=root), "payload")
            if payload is not None:
                return _from_payload(payload)
        except Exception:
            pass
    result = _evaluate("full", files, _load_allowlist(root), version)
    if key is not None:
        try:
            cache.put(
                key,
                cache.CachedResult(
                    gate_type=GATE_TYPE, payload=result.to_dict(), stored_at=_utc_now()
                ),
                repo_root=root,
            )
        except Exception:
            pass
    return result


def scan_files(paths: list, repo_root: Optional[Path] = None) -> SecretScanResult:
    """Pre-commit form: only the given files, no cache-manager."""
    root = None if repo_root is None else Path(repo_root)
    selected = {}
    for given in paths:
        if root is None:
            path = Path(given)
            reported = os.fspath(given)
        else:
            path = root / given
            reported = Path(os.path.relpath(path, root)).as_posix()
        if SKIP_DIRS.intersection(Path(reported).parts[:-1]):
            continue
        data = _read_text(path)
        if data is not None:
            selected[reported] = (reported, path, data)
    allowlist = (True, []) if root is None else _load_allowlist(root)
    return _evaluate("precommit", list(selected.values()), allowlist, gate_version(root))


def propose(repo_root: Path) -> AllowlistProposal:
    """A complete allowlist covering every eligible finding; writes nothing."""
    root = Path(repo_root)
    valid, entries = _load_allowlist(root)
    if not valid:
        raise AllowlistInvalidError(f"{ALLOWLIST_NAME} is invalid or unsealed")
    covered = {(entry["file"], entry["type"], entry["hashed_secret"]) for entry in entries}
    proposed = [dict(entry) for entry in entries]
    ineligible = []
    for finding in _detect([(rel, path) for rel, path, _data in _collect_tree(root)]):
        hashed = "sha1:" + finding["secret_hash"]
        if (finding["file"], finding["rule_id"], hashed) in covered:
            continue
        for reason in ("planted-fixture", "public-constant"):
            entry = {
                "file": finding["file"],
                "type": finding["rule_id"],
                "hashed_secret": hashed,
                "reason": reason,
            }
            if _valid_entry(entry):
                proposed.append(entry)
                break
        else:
            ineligible.append(
                {"file": finding["file"], "line": finding["line"], "rule_id": finding["rule_id"]}
            )
    proposed.sort(key=lambda entry: (entry["file"], entry["type"], entry["hashed_secret"]))
    ineligible.sort(key=_sort_key)
    return AllowlistProposal(
        allowlist={"version": 1, "entries": proposed}, ineligible=ineligible
    )


# ---------------------------------------------------------------- CLI

_MODE_FLAGS = {
    "full": ("--repo-root", "--format"),
    "precommit": ("--files", "--repo-root", "--format"),
    "propose": ("--repo-root",),
}


def _usage(message: str) -> int:
    print(f"secret-scan: usage error: {message}", file=sys.stderr)
    return 2


def _git_changed_files(root: Path) -> list:
    commands = (
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    )
    names = set()
    for command in commands:
        try:
            proc = subprocess.run(command, cwd=root, capture_output=True, text=True)
        except OSError:
            continue
        if proc.returncode == 0:
            names.update(line for line in proc.stdout.splitlines() if line)
    return sorted(names)


def _emit(result: SecretScanResult, fmt: str) -> int:
    if fmt == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("FLAGGED" if result.flagged else "CLEAN")
        for match in result.matches:
            print(f"{match['file']}:{match['line']}: {match['rule_id']} ({match['risk_tier']})")
    return 1 if result.flagged else 0


def main(argv: list) -> int:
    args = list(argv)
    if args[:1] == ["secret-scan"]:
        args = args[1:]
    mode = "full"
    if args[:1] in (["precommit"], ["propose"]):
        mode = args.pop(0)
    options = {"--repo-root": ".", "--format": "text"}
    files = []
    index = 0
    while index < len(args):
        name, sep, value = args[index].partition("=")
        if name not in _MODE_FLAGS[mode]:
            return _usage(f"unknown argument {args[index]!r}")
        if not sep:
            if index + 1 == len(args):
                return _usage(f"{name} requires a value")
            index += 1
            value = args[index]
        index += 1
        if name == "--files":
            files.append(value)
        else:
            options[name] = value
    if options["--format"] not in ("json", "text"):
        return _usage(f"invalid --format {options['--format']!r}")
    root = Path(options["--repo-root"])
    if mode == "propose":
        try:
            proposal = propose(root)
        except AllowlistInvalidError as exc:
            print(f"secret-scan: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(proposal.to_dict(), indent=2))
        return 1 if proposal.ineligible else 0
    if mode == "precommit":
        result = scan_files(files or _git_changed_files(root), repo_root=root)
    else:
        result = scan(root)
    return _emit(result, options["--format"])