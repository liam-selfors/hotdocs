"""License scanner: k-gram fingerprint comparison of gen/<component>/ against
a precomputed reference corpus of known-licensed-code window hashes."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GATE_TYPE = "license_scanner"
WINDOW = 9
DEFAULT_BLOCK_THRESHOLD = 0.70
DEFAULT_CORPUS_VERSION = 0
RISK_TIERS = ("high", "medium", "low")
CORPUS_ENV = "VAR_LICENSE_CORPUS_PATH"
WEBHOOK_ENV = "VAR_COMPLIANCE_WEBHOOK_URL"
MODEL_PIN = "none"
WEBHOOK_TIMEOUT = 10

USAGE = "usage: hotdocs license-scan <component-id> [--repo-root=<dir>] [--format=json|text]"

_COMMENT_RE = re.compile(r"/\*.*?\*/|\"\"\".*?\"\"\"|'''.*?'''|//[^\n]*|#[^\n]*", re.DOTALL)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


@dataclasses.dataclass
class LicenseScanResult:
    component_id: str
    gate_version: str
    evaluated: bool
    reason: str | None
    similarity_score: float | None
    block_threshold: float | None
    blocked: bool
    matches: list
    notified: bool
    notification_delivery_error: dict | None
    cache_hit: bool


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access
# ---------------------------------------------------------------------------

def _read(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


# ---------------------------------------------------------------------------
# Reference corpus
# ---------------------------------------------------------------------------

def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _corpus_is_valid(data) -> bool:
    if not isinstance(data, dict):
        return False
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return False
    if "corpus_version" in data:
        v = data["corpus_version"]
        if not (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
            return False
    if "block_threshold" in data:
        t = data["block_threshold"]
        if not (_is_number(t) and 0 < t <= 1):
            return False
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        hashes = entry.get("hashes")
        if not isinstance(hashes, list) or not all(isinstance(h, str) for h in hashes):
            return False
        if entry.get("risk_tier") not in RISK_TIERS:
            return False
    return True


def _load_corpus(repo_root: Path):
    """Return (gate_version, reason, corpus_dict_or_None)."""
    value = os.environ.get(CORPUS_ENV) or ""
    if not value:
        reason = "no-reference-corpus"
        return f"{GATE_TYPE}@4.0.0-{reason}", reason, None
    path = Path(value)
    if not path.is_absolute():
        path = Path(repo_root) / path
    try:
        raw = path.read_bytes()
    except OSError:
        reason = "corpus-unreadable"
        return f"{GATE_TYPE}@4.0.0-{reason}", reason, None
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if not _corpus_is_valid(data):
        reason = "corpus-invalid"
        return f"{GATE_TYPE}@4.0.0-{reason}", reason, None
    version = data.get("corpus_version", DEFAULT_CORPUS_VERSION)
    digest = hashlib.sha256(raw).hexdigest()[:12]
    return f"{GATE_TYPE}@4.0.{version}+{digest}", None, data


def gate_version(repo_root: Path) -> str:
    return _load_corpus(Path(repo_root))[0]


# ---------------------------------------------------------------------------
# Component content and fingerprinting
# ---------------------------------------------------------------------------

def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _component_files(component_dir: Path) -> list:
    found = []
    for dirpath, dirnames, filenames in os.walk(component_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__" and not d.startswith(".")]
        for name in filenames:
            if name.startswith(".") or name.endswith(".pyc"):
                continue
            full = Path(dirpath) / name
            found.append((full.relative_to(component_dir).as_posix(), full))
    found.sort(key=lambda item: item[0])
    return found


def _inputs_hash(files: list) -> str:
    h = hashlib.sha256()
    for rel, full in files:
        data = full.read_bytes()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(len(data)).encode("ascii"))
        h.update(b"\0")
        h.update(data)
    return "sha256:" + h.hexdigest()


def _window_hashes(text: str) -> set:
    stripped = _COMMENT_RE.sub(" ", text)
    tokens = [t.lower() for t in _TOKEN_RE.findall(stripped)]
    hashes = set()
    for i in range(len(tokens) - WINDOW + 1):
        window = "\x1f".join(tokens[i:i + WINDOW])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return hashes


def _component_hashes(files: list) -> set:
    hashes = set()
    for _rel, full in files:
        hashes |= _window_hashes(full.read_bytes().decode("utf-8", errors="replace"))
    return hashes


# ---------------------------------------------------------------------------
# cache-manager loading
# ---------------------------------------------------------------------------

def _tool_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_cache_manager(repo_root: Path):
    base = Path(repo_root) / "gen" / "cache-manager"
    if not base.is_dir():
        tool_root = _tool_root()
        if tool_root is None:
            return None
        base = tool_root / "gen" / "cache-manager"
    pkg_init = base / "cache_manager" / "__init__.py"
    flat = base / "cache_manager.py"
    try:
        if pkg_init.is_file():
            spec = importlib.util.spec_from_file_location(
                "cache_manager", pkg_init, submodule_search_locations=[str(pkg_init.parent)]
            )
        elif flat.is_file():
            spec = importlib.util.spec_from_file_location("cache_manager", flat)
        else:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules["cache_manager"] = module
        spec.loader.exec_module(module)
        for name in ("CacheKey", "CachedResult", "get", "put"):
            if not hasattr(module, name):
                return None
        return module
    except Exception:
        sys.modules.pop("cache_manager", None)
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def _notify(url: str, result: LicenseScanResult):
    body = json.dumps(dataclasses.asdict(result)).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=WEBHOOK_TIMEOUT) as response:
            response.read()
        return None
    except urllib.error.HTTPError as exc:
        category = "auth" if exc.code in (401, 403) else "network"
        return {"category": category, "message": str(exc)}
    except Exception as exc:
        is_timeout = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
        return {"category": "timeout" if is_timeout else "network", "message": str(exc)}


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def _evaluate(component_id: str, version: str, reason, corpus, files: list) -> LicenseScanResult:
    if corpus is None:
        return LicenseScanResult(
            component_id=component_id,
            gate_version=version,
            evaluated=False,
            reason=reason,
            similarity_score=None,
            block_threshold=None,
            blocked=reason != "no-reference-corpus",
            matches=[],
            notified=False,
            notification_delivery_error=None,
            cache_hit=False,
        )
    threshold = corpus.get("block_threshold", DEFAULT_BLOCK_THRESHOLD)
    windows = _component_hashes(files)
    matches = []
    best = 0.0
    for entry in corpus["entries"]:
        score = len(windows & set(entry["hashes"])) / len(windows) if windows else 0.0
        best = max(best, score)
        if score > 0:
            matches.append({
                "reference_id": entry.get("reference_id"),
                "license_family": entry.get("license_family"),
                "risk_tier": entry["risk_tier"],
                "score": score,
            })
    matches.sort(key=lambda m: (-m["score"], str(m["reference_id"])))
    return LicenseScanResult(
        component_id=component_id,
        gate_version=version,
        evaluated=True,
        reason=None,
        similarity_score=best,
        block_threshold=threshold,
        blocked=best >= threshold,
        matches=matches,
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def scan(component_id: str, repo_root: Path) -> LicenseScanResult:
    repo_root = Path(repo_root)
    version, reason, corpus = _load_corpus(repo_root)
    files = _component_files(repo_root / "gen" / _slug(component_id))

    cm = _load_cache_manager(repo_root)
    cache_key = None
    if cm is not None:
        cache_key = cm.CacheKey(
            spec_bundle_hash="sha256:" + hashlib.sha256(component_id.encode("utf-8")).hexdigest(),
            gate_inputs_hash=_inputs_hash(files),
            gate_version=version,
            model_pin=MODEL_PIN,
        )
        cached = cm.get(cache_key, repo_root=repo_root)
        payload = _read(cached, "payload")
        if payload is not None:
            fields = {f.name: _read(payload, f.name) for f in dataclasses.fields(LicenseScanResult)}
            fields["cache_hit"] = True
            return LicenseScanResult(**fields)

    result = _evaluate(component_id, version, reason, corpus, files)
    webhook = os.environ.get(WEBHOOK_ENV) or ""
    due = result.blocked or any(m["risk_tier"] == "high" for m in result.matches)
    result.notified = bool(webhook) and due
    if result.notified:
        result.notification_delivery_error = _notify(webhook, result)

    if cm is not None:
        cached_result = cm.CachedResult(
            gate_type=GATE_TYPE,
            payload=dataclasses.asdict(result),
            stored_at=_now_iso(),
        )
        cm.put(cache_key, cached_result, repo_root=repo_root)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _usage_error(cause: str) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _render_text(result: LicenseScanResult) -> str:
    lines = [
        f"component: {result.component_id}",
        f"gate_version: {result.gate_version}",
        f"evaluated: {str(result.evaluated).lower()}",
        f"similarity_score: {'null' if result.similarity_score is None else result.similarity_score}",
        f"block_threshold: {'null' if result.block_threshold is None else result.block_threshold}",
        f"blocked: {str(result.blocked).lower()}",
        f"notified: {str(result.notified).lower()}",
    ]
    for m in result.matches:
        lines.append(
            f"match: {m['reference_id']} {m['license_family']} risk_tier={m['risk_tier']} score={m['score']}"
        )
    if result.notification_delivery_error is not None:
        err = result.notification_delivery_error
        lines.append(f"notification_delivery_error: {err['category']}: {err['message']}")
    if not result.evaluated:
        lines.append(f"NOT EVALUATED: {result.reason}")
        if result.reason == "no-reference-corpus":
            lines.append(f"hint: set {CORPUS_ENV} to a reference corpus file to enable the license scan")
    return "\n".join(lines)


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    component_id = None
    repo_root = "."
    fmt = "text"
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("--repo-root="):
            repo_root = token[len("--repo-root="):]
        elif token.startswith("--format="):
            fmt = token[len("--format="):]
        elif token in ("--repo-root", "--format"):
            if i + 1 >= len(argv):
                return _usage_error(f"{token} requires a value")
            i += 1
            if token == "--repo-root":
                repo_root = argv[i]
            else:
                fmt = argv[i]
        elif token.startswith("-") or component_id is not None:
            return _usage_error(f"unknown argument: {token}")
        else:
            component_id = token
        i += 1
    if component_id is None:
        return _usage_error("missing <component-id>")
    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format: {fmt}")

    result = scan(component_id, Path(repo_root))
    if fmt == "json":
        print(json.dumps(dataclasses.asdict(result)))
    else:
        print(_render_text(result))
    return 1 if result.blocked else 0


if __name__ == "__main__":
    sys.exit(main())
