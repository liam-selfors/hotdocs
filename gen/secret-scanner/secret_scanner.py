"""Secret Scanner: whole-repository committed-secret detection via detect-secrets."""

from __future__ import annotations

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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

GATE_BASE_VERSION = "3.1.0"
GATE_TYPE = "secret_scanner"

_SKIP_DIRS = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".venv", ".hotdocs", "node_modules"}
)
_EXCLUDED_PLUGINS = frozenset({"KeywordDetector", "IPPublicDetector"})
_LOW_RISK_TYPES = frozenset({"Base64 High Entropy String", "Hex High Entropy String"})
_HEX_TYPE = "Hex High Entropy String"

_ALLOWLIST_NAME = ".secret-allowlist.json"
_ALLOWLIST_KEYS = frozenset({"version", "entries"})
_ENTRY_KEYS = ("file", "type", "hashed_secret", "reason")
_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+")
_HASH_RE = re.compile(r"sha1:[0-9a-f]{40}")
_DECISION_RE = re.compile(r"D(\d+)\.md")

_WEBHOOK_ENV = "VAR_COMPLIANCE_WEBHOOK_URL"


class AllowlistInvalidError(Exception):
    """Raised by `propose` when the allowlist is invalid (R-SECRET-012/013)."""


@dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list = field(default_factory=list)
    allowed: list = field(default_factory=list)
    unused_allowlist_entries: list = field(default_factory=list)
    notified: bool = False
    notification_delivery_error: dict | None = None
    cache_hit: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AllowlistProposal:
    allowlist: dict
    ineligible: list

    def to_dict(self) -> dict:
        return asdict(self)

    def __getitem__(self, key):
        return getattr(self, key)


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


# ---------------------------------------------------------------- files


def _read_text(path) -> bytes | None:
    """Return the file's bytes if it is a file decoding as UTF-8, else None."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        data = fh.read()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return data


def _collect_full(root: Path) -> list:
    """Every scanned text file under root: sorted (rel, full, bytes) triples."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in filenames:
            full = os.path.join(dirpath, name)
            data = _read_text(full)
            if data is None:
                continue
            rel = Path(os.path.relpath(full, root)).as_posix()
            out.append((rel, full, data))
    out.sort(key=lambda t: t[0])
    return out


def _hash_files(items) -> str:
    h = hashlib.sha256()
    for rel, data in sorted(items, key=lambda t: t[0]):
        rb = rel.encode("utf-8")
        h.update(b"%d:" % len(rb) + rb + b"%d:" % len(data))
        h.update(data)
    return "sha256:" + h.hexdigest()


# ---------------------------------------------------------------- engine


def _engine(files) -> list:
    """Run detect-secrets over (rel, full) pairs; return raw findings."""
    from detect_secrets import SecretsCollection
    from detect_secrets.core.plugins.util import get_mapping_from_secret_type_to_class
    from detect_secrets.settings import transient_settings

    names = sorted(
        {cls.__name__ for cls in get_mapping_from_secret_type_to_class().values()}
        - _EXCLUDED_PLUGINS
    )
    config = {"plugins_used": [{"name": n} for n in names], "filters_used": []}
    findings = []
    with transient_settings(config):
        for rel, full in files:
            collection = SecretsCollection()
            collection.scan_file(str(full))
            for _filename, secret in collection:
                findings.append(
                    {
                        "file": rel,
                        "line": secret.line_number,
                        "rule_id": secret.type,
                        "hash": secret.secret_hash,
                    }
                )
    return findings


# ---------------------------------------------------------------- allowlist


def _valid_path(path: str) -> bool:
    return (
        _PATH_RE.fullmatch(path) is not None
        and not path.startswith("/")
        and ".." not in path.split("/")
    )


def _under_fixture_dir(path: str) -> bool:
    return path.startswith("verification/") or path.startswith("specs/")


def _valid_entry(entry) -> bool:
    if not isinstance(entry, dict) or set(entry) != set(_ENTRY_KEYS):
        return False
    if not all(isinstance(entry[k], str) for k in _ENTRY_KEYS):
        return False
    reason = entry["reason"]
    return (
        _valid_path(entry["file"])
        and _HASH_RE.fullmatch(entry["hashed_secret"]) is not None
        and (
            (reason == "planted-fixture" and _under_fixture_dir(entry["file"]))
            or (reason == "public-constant" and entry["type"] == _HEX_TYPE)
        )
    )


def _frontmatter(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fm = {}
    if lines[:1] == ["---"]:
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, sep, value = line.partition(":")
            if sep:
                fm[key.strip()] = value.strip().strip("\"'")
    return fm


def _sealed_hash(root: Path):
    best = None
    for path in (root / "specs" / "decisions").glob("D*.md"):
        m = _DECISION_RE.fullmatch(path.name)
        if not m:
            continue
        fm = _frontmatter(path)
        number = int(m.group(1))
        if (
            fm.get("status") == "ratified"
            and "allowlist_sha256" in fm
            and (best is None or number > best[0])
        ):
            best = (number, fm["allowlist_sha256"])
    return best[1] if best else None


def _read_allowlist(root: Path) -> list:
    """The shared loader: valid entries, [] when absent; raises when invalid."""
    path = root / _ALLOWLIST_NAME
    if not path.is_file():
        return []
    data = path.read_bytes()
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError as exc:
        raise AllowlistInvalidError(f"not valid JSON: {exc}") from None
    if not isinstance(doc, dict) or set(doc) != _ALLOWLIST_KEYS:
        raise AllowlistInvalidError("must be an object with exactly version and entries")
    if type(doc["version"]) is not int or doc["version"] != 1:
        raise AllowlistInvalidError("version must be the integer 1")
    entries = doc["entries"]
    if not isinstance(entries, list):
        raise AllowlistInvalidError("entries must be a list")
    for entry in entries:
        if not _valid_entry(entry):
            raise AllowlistInvalidError(f"invalid entry: {json.dumps(entry)}")
    if entries:
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        if _sealed_hash(root) != digest:
            raise AllowlistInvalidError("allowlist is not sealed by a ratified decision")
    return [{k: e[k] for k in _ENTRY_KEYS} for e in entries]


def _entry_key(entry) -> tuple:
    return (entry["file"], entry["type"], entry["hashed_secret"])


def _finding_key(finding) -> tuple:
    return (finding["file"], finding["rule_id"], "sha1:" + finding["hash"])


# ---------------------------------------------------------------- result


def _notify(result: SecretScanResult, url: str):
    body = json.dumps(
        {
            "gate_type": GATE_TYPE,
            "scope": result.scope,
            "gate_version": result.gate_version,
            "flagged": result.flagged,
            "matches": result.matches,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(request, timeout=10)
    except Exception as exc:  # noqa: BLE001 -- never raised (R-SECRET-004)
        if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403):
            category = "auth"
        elif isinstance(exc, TimeoutError) or isinstance(
            getattr(exc, "reason", None), TimeoutError
        ):
            category = "timeout"
        else:
            category = "network"
        return {"category": category, "message": str(exc)}
    return None


def _build(scope, gv, findings, entries, invalid) -> SecretScanResult:
    keys = {_entry_key(e) for e in entries}
    used = set()
    matches, allowed = [], []
    for f in findings:
        k = _finding_key(f)
        if k in keys:
            used.add(k)
            allowed.append({"rule_id": f["rule_id"], "file": f["file"], "line": f["line"]})
        else:
            matches.append(
                {
                    "rule_id": f["rule_id"],
                    "risk_tier": "low" if f["rule_id"] in _LOW_RISK_TYPES else "high",
                    "file": f["file"],
                    "line": f["line"],
                }
            )
    if invalid:
        matches.append(
            {
                "rule_id": "allowlist-invalid",
                "risk_tier": "high",
                "file": _ALLOWLIST_NAME,
                "line": 1,
            }
        )
    order = lambda m: (m["file"], m["line"], m["rule_id"])  # noqa: E731
    matches.sort(key=order)
    allowed.sort(key=order)
    unused = [
        {"file": e["file"], "type": e["type"]}
        for e in sorted(entries, key=_entry_key)
        if _entry_key(e) not in used
    ]
    flagged = bool(matches)
    result = SecretScanResult(
        scope=scope,
        gate_version=gv,
        flagged=flagged,
        matches=matches,
        allowed=allowed,
        unused_allowlist_entries=unused,
    )
    # Due when a match blocked or any match is high; an allowed finding is no
    # match, so every high match is itself a blocking match.
    url = os.environ.get(_WEBHOOK_ENV)
    result.notified = flagged and bool(url)
    if result.notified:
        result.notification_delivery_error = _notify(result, url)
    return result


def _load_allowlist_state(root: Path):
    try:
        return _read_allowlist(root), False
    except AllowlistInvalidError:
        return [], True


# ---------------------------------------------------------------- cache


def _load_cache_manager(root: Path):
    try:
        directory = Path(root) / "gen" / "cache-manager"
        if not directory.is_dir():
            tool_root = next(
                d.parent for d in Path(__file__).resolve().parents if d.name == "gen"
            )
            directory = tool_root / "gen" / "cache-manager"
        package = directory / "cache_manager" / "__init__.py"
        if package.is_file():
            spec = importlib.util.spec_from_file_location(
                "cache_manager", package, submodule_search_locations=[str(package.parent)]
            )
        else:
            spec = importlib.util.spec_from_file_location(
                "cache_manager", directory / "cache_manager.py"
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules["cache_manager"] = module
        spec.loader.exec_module(module)
        return module
    except Exception:  # noqa: BLE001 -- unloadable means no lookup
        return None


def _from_payload(payload) -> SecretScanResult:
    return SecretScanResult(
        scope=_get(payload, "scope"),
        gate_version=_get(payload, "gate_version"),
        flagged=_get(payload, "flagged"),
        matches=list(_get(payload, "matches") or []),
        allowed=list(_get(payload, "allowed") or []),
        unused_allowlist_entries=list(_get(payload, "unused_allowlist_entries") or []),
        notified=bool(_get(payload, "notified")),
        notification_delivery_error=_get(payload, "notification_delivery_error"),
        cache_hit=True,
    )


# ---------------------------------------------------------------- library


def gate_version(repo_root: Path) -> str:
    return (
        f"{GATE_TYPE}@{GATE_BASE_VERSION}+detect-secrets."
        f"{importlib.metadata.version('detect-secrets')}"
    )


def scan(repo_root: Path) -> SecretScanResult:
    root = Path(repo_root)
    files = _collect_full(root)
    gv = gate_version(root)
    cm = _load_cache_manager(root)
    key = None
    if cm is not None:
        try:
            key = cm.CacheKey(
                spec_bundle_hash=_hash_files(
                    [(r, d) for r, _f, d in files if r.startswith("specs/")]
                ),
                gate_inputs_hash=_hash_files(
                    [(r, d) for r, _f, d in files if not r.startswith("specs/")]
                ),
                gate_version=gv,
                model_pin="none",
            )
            payload = _get(cm.get(key, repo_root=root), "payload")
            if payload is not None:
                return _from_payload(payload)
        except Exception:  # noqa: BLE001 -- a cache failure never fails a scan
            pass
    entries, invalid = _load_allowlist_state(root)
    findings = _engine([(r, f) for r, f, _d in files])
    result = _build("full", gv, findings, entries, invalid)
    if key is not None:
        try:
            cm.put(
                key,
                cm.CachedResult(
                    gate_type=GATE_TYPE,
                    payload=result.to_dict(),
                    stored_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
                repo_root=root,
            )
        except Exception:  # noqa: BLE001 -- a cache failure never fails a scan
            pass
    return result


def scan_files(paths: list, repo_root: Path | None = None) -> SecretScanResult:
    selected = {}
    for p in paths:
        p = Path(p)
        if repo_root is None:
            full, rel = p, p.as_posix()
        else:
            full = Path(repo_root) / p
            rel = Path(
                os.path.relpath(os.path.abspath(full), os.path.abspath(repo_root))
            ).as_posix()
        if set(Path(rel).parts[:-1]) & _SKIP_DIRS:
            continue
        if _read_text(full) is None:
            continue
        selected[rel] = full
    files = sorted(selected.items())
    if repo_root is None:
        entries, invalid = [], False
    else:
        entries, invalid = _load_allowlist_state(Path(repo_root))
    findings = _engine(files)
    return _build("precommit", gate_version(repo_root), findings, entries, invalid)


def propose(repo_root: Path) -> AllowlistProposal:
    root = Path(repo_root)
    entries = _read_allowlist(root)
    files = _collect_full(root)
    findings = _engine([(r, f) for r, f, _d in files])
    proposed = {_entry_key(e): e for e in entries}
    ineligible = []
    for f in findings:
        k = _finding_key(f)
        if k in proposed:
            continue
        if _valid_path(f["file"]) and _under_fixture_dir(f["file"]):
            reason = "planted-fixture"
        elif _valid_path(f["file"]) and f["rule_id"] == _HEX_TYPE:
            reason = "public-constant"
        else:
            ineligible.append({"file": f["file"], "line": f["line"], "rule_id": f["rule_id"]})
            continue
        proposed[k] = {
            "file": f["file"],
            "type": f["rule_id"],
            "hashed_secret": k[2],
            "reason": reason,
        }
    ineligible.sort(key=lambda m: (m["file"], m["line"], m["rule_id"]))
    return AllowlistProposal(
        allowlist={"version": 1, "entries": [proposed[k] for k in sorted(proposed)]},
        ineligible=ineligible,
    )


# ---------------------------------------------------------------- CLI

_USAGE = {
    "full": "usage: hotdocs secret-scan [--repo-root=<dir>] [--format=json|text]",
    "precommit": (
        "usage: hotdocs secret-scan precommit [--files=<path>]... "
        "[--repo-root=<dir>] [--format=json|text]"
    ),
    "propose": "usage: hotdocs secret-scan propose [--repo-root=<dir>]",
}
_FLAGS = {
    "full": {"--repo-root", "--format"},
    "precommit": {"--repo-root", "--format", "--files"},
    "propose": {"--repo-root"},
}


class _UsageError(Exception):
    pass


def _parse(args: list, flags: set) -> dict:
    opts = {}
    i = 0
    while i < len(args):
        token = args[i]
        i += 1
        name, eq, value = token.partition("=")
        if name not in flags:
            raise _UsageError(f"unknown argument: {token}")
        if not eq:
            if i >= len(args):
                raise _UsageError(f"missing value for {name}")
            value = args[i]
            i += 1
        opts.setdefault(name, []).append(value)
    return opts


def _git_changed(root: Path) -> list:
    commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
    ]
    names = set()
    try:
        for cmd in commands:
            out = subprocess.run(
                cmd, cwd=root, capture_output=True, text=True, check=True
            ).stdout
            names.update(line for line in out.splitlines() if line)
    except (OSError, subprocess.CalledProcessError):
        return []
    return sorted(names)


def main(argv: list | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["secret-scan"]:
        args = args[1:]
    form = "full"
    if args[:1] == ["precommit"] or args[:1] == ["propose"]:
        form = args.pop(0)
    try:
        opts = _parse(args, _FLAGS[form])
        fmt = opts.get("--format", ["text"])[-1]
        if fmt not in ("json", "text"):
            raise _UsageError(f"invalid --format value: {fmt}")
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(_USAGE[form], file=sys.stderr)
        return 2
    root = Path(opts.get("--repo-root", [os.getcwd()])[-1])

    if form == "propose":
        try:
            proposal = propose(root)
        except AllowlistInvalidError as exc:
            print(f"error: invalid allowlist: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(proposal.to_dict(), indent=2))
        return 1 if proposal.ineligible else 0

    if form == "precommit":
        names = opts["--files"] if "--files" in opts else _git_changed(root)
        result = scan_files([root / name for name in names], repo_root=root)
    else:
        result = scan(root)

    if fmt == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("FLAGGED" if result.flagged else "CLEAN")
        for m in result.matches:
            print(f"{m['file']}:{m['line']}: {m['rule_id']} [{m['risk_tier']}]")
    return 1 if result.flagged else 0


if __name__ == "__main__":
    sys.exit(main())
