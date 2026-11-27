"""License scanner: k-gram fingerprint comparison of gen/<component>/ against a reference corpus."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["LicenseScanResult", "scan", "gate_version", "main"]

GATE_TYPE = "license_scanner"
WINDOW = 9
DEFAULT_BLOCK_THRESHOLD = 0.70
DEFAULT_CORPUS_VERSION = 0
RISK_TIERS = ("high", "medium", "low")
USAGE = "usage: hotdocs license-scan <component-id> [--repo-root=<dir>] [--format=json|text]"

_COMMENT_RE = re.compile(
    r"/\*.*?\*/|\"\"\".*?\"\"\"|'''.*?'''|//[^\n]*|#[^\n]*",
    re.DOTALL,
)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


@dataclass
class LicenseScanResult:
    component_id: str
    gate_version: str
    evaluated: bool
    reason: str | None
    similarity_score: float | None
    block_threshold: float | None
    blocked: bool
    matches: list = field(default_factory=list)
    notified: bool = False
    notification_delivery_error: dict | None = None
    cache_hit: bool = False

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _read(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


# ---------------------------------------------------------------- corpus


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _corpus_is_valid(corpus) -> bool:
    if not isinstance(corpus, dict) or not isinstance(corpus.get("entries"), list):
        return False
    if "corpus_version" in corpus:
        version = corpus["corpus_version"]
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            return False
    if "block_threshold" in corpus:
        threshold = corpus["block_threshold"]
        if not _is_number(threshold) or not (0 < threshold <= 1):
            return False
    for entry in corpus["entries"]:
        if not isinstance(entry, dict):
            return False
        hashes = entry.get("hashes")
        if not isinstance(hashes, list) or not all(isinstance(h, str) for h in hashes):
            return False
        if entry.get("risk_tier") not in RISK_TIERS:
            return False
    return len(corpus["entries"]) > 0


def _load_corpus(repo_root: Path):
    """Return (reason, corpus, raw_bytes); reason is None for a usable corpus."""
    raw_path = os.environ.get("VAR_LICENSE_CORPUS_PATH", "")
    if not raw_path:
        return "no-reference-corpus", None, None
    path = Path(repo_root) / raw_path
    try:
        data = path.read_bytes()
    except OSError:
        return "corpus-unreadable", None, None
    try:
        corpus = json.loads(data)
    except ValueError:
        return "corpus-invalid", None, None
    if not _corpus_is_valid(corpus):
        return "corpus-invalid", None, None
    return None, corpus, data


def _gate_version_for(reason, corpus, data) -> str:
    if reason is not None:
        return f"{GATE_TYPE}@4.0.0-{reason}"
    version = corpus.get("corpus_version", DEFAULT_CORPUS_VERSION)
    digest = hashlib.sha256(data).hexdigest()[:12]
    return f"{GATE_TYPE}@4.0.{version}+{digest}"


def gate_version(repo_root: Path) -> str:
    reason, corpus, data = _load_corpus(Path(repo_root))
    return _gate_version_for(reason, corpus, data)


# ---------------------------------------------------------------- content


def _component_files(component_dir: Path) -> list:
    files = []
    for dirpath, dirnames, filenames in os.walk(component_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__" and not d.startswith(".")]
        for name in filenames:
            if name.startswith(".") or name.endswith(".pyc"):
                continue
            files.append(Path(dirpath) / name)
    return sorted(files, key=lambda p: p.relative_to(component_dir).as_posix())


def _inputs_hash(component_dir: Path, files: list) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(component_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _window_hashes(text: str) -> set:
    stripped = _COMMENT_RE.sub(" ", text)
    tokens = [t.lower() for t in _TOKEN_RE.findall(stripped)]
    return {
        hashlib.sha256("\x1f".join(tokens[i:i + WINDOW]).encode("utf-8")).hexdigest()
        for i in range(len(tokens) - WINDOW + 1)
    }


def _component_hashes(files: list) -> set:
    hashes = set()
    for path in files:
        hashes |= _window_hashes(path.read_bytes().decode("utf-8", errors="replace"))
    return hashes


# ---------------------------------------------------------------- evaluation


def _evaluate(component_id, gv, reason, corpus, files) -> LicenseScanResult:
    if reason is not None:
        return LicenseScanResult(
            component_id=component_id,
            gate_version=gv,
            evaluated=False,
            reason=reason,
            similarity_score=None,
            block_threshold=None,
            blocked=reason != "no-reference-corpus",
            matches=[],
        )
    threshold = corpus.get("block_threshold", DEFAULT_BLOCK_THRESHOLD)
    mine = _component_hashes(files)
    matches = []
    for entry in corpus["entries"]:
        score = len(mine & set(entry["hashes"])) / len(mine) if mine else 0.0
        if score > 0:
            matches.append({
                "reference_id": entry.get("reference_id"),
                "license_family": entry.get("license_family"),
                "risk_tier": entry["risk_tier"],
                "score": score,
            })
    matches.sort(key=lambda m: (-m["score"], str(m["reference_id"])))
    similarity = max((m["score"] for m in matches), default=0.0)
    return LicenseScanResult(
        component_id=component_id,
        gate_version=gv,
        evaluated=True,
        reason=None,
        similarity_score=similarity,
        block_threshold=threshold,
        blocked=similarity >= threshold,
        matches=matches,
    )


def _classify_error(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403):
        return "auth"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (socket.timeout, TimeoutError)):
        return "timeout"
    return "network"


def _notify(result: LicenseScanResult) -> None:
    url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL", "")
    due = result.blocked or any(m["risk_tier"] == "high" for m in result.matches)
    result.notified = bool(due and url)
    if not result.notified:
        return
    body = json.dumps(result.to_dict()).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            pass
    except Exception as exc:  # noqa: BLE001 - R-LICENSE-003: never raised
        result.notification_delivery_error = {
            "category": _classify_error(exc),
            "message": str(exc),
        }


# ---------------------------------------------------------------- cache-manager


def _load_cache_manager(repo_root: Path):
    try:
        base = Path(repo_root) / "gen" / "cache-manager"
        if not base.is_dir():
            tool_root = next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")
            base = tool_root / "gen" / "cache-manager"
        package_init = base / "cache_manager" / "__init__.py"
        if package_init.is_file():
            spec = importlib.util.spec_from_file_location(
                "cache_manager", package_init,
                submodule_search_locations=[str(package_init.parent)],
            )
        else:
            spec = importlib.util.spec_from_file_location("cache_manager", base / "cache_manager.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["cache_manager"] = module
        spec.loader.exec_module(module)
        return module
    except Exception:  # noqa: BLE001 - unloadable means no cache lookup
        return None


def _from_payload(payload) -> LicenseScanResult:
    values = {f.name: _read(payload, f.name) for f in dataclasses.fields(LicenseScanResult)}
    values["matches"] = list(values["matches"] or [])
    values["cache_hit"] = True
    return LicenseScanResult(**values)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- scan


def scan(component_id: str, repo_root: Path) -> LicenseScanResult:
    repo_root = Path(repo_root)
    reason, corpus, data = _load_corpus(repo_root)
    gv = _gate_version_for(reason, corpus, data)
    slug = component_id.removeprefix("comp-")
    component_dir = repo_root / "gen" / slug
    files = _component_files(component_dir)
    inputs_hash = _inputs_hash(component_dir, files)

    cm = _load_cache_manager(repo_root)
    if cm is not None:
        key = cm.CacheKey(
            spec_bundle_hash=inputs_hash,
            gate_inputs_hash=inputs_hash,
            gate_version=gv,
            model_pin="none",
        )
        cached = cm.get(key, repo_root=repo_root)
        payload = _read(cached, "payload")
        if payload is not None:
            return _from_payload(payload)

    result = _evaluate(component_id, gv, reason, corpus, files)
    _notify(result)

    if cm is not None:
        cm.put(
            key,
            cm.CachedResult(gate_type=GATE_TYPE, payload=result.to_dict(), stored_at=_now_iso()),
            repo_root=repo_root,
        )
    return result


# ---------------------------------------------------------------- CLI


class _UsageError(Exception):
    pass


def _parse(argv: list) -> dict:
    opts = {"component_id": None, "repo_root": ".", "format": "text"}
    flags = {"--repo-root": "repo_root", "--format": "format"}
    i = 0
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in flags:
            if not eq:
                if i + 1 >= len(argv):
                    raise _UsageError(f"{name} requires a value")
                i += 1
                value = argv[i]
            opts[flags[name]] = value
        elif not token.startswith("-") and opts["component_id"] is None:
            opts["component_id"] = token
        else:
            raise _UsageError(f"unknown argument: {token}")
        i += 1
    if opts["component_id"] is None:
        raise _UsageError("missing <component-id>")
    if opts["format"] not in ("json", "text"):
        raise _UsageError(f"invalid --format: {opts['format']}")
    return opts


def _text(result: LicenseScanResult) -> str:
    lines = [
        f"component_id: {result.component_id}",
        f"gate_version: {result.gate_version}",
        f"similarity_score: {result.similarity_score}",
        f"block_threshold: {result.block_threshold}",
        f"blocked: {str(result.blocked).lower()}",
        f"matches: {len(result.matches)}",
        f"notified: {str(result.notified).lower()}",
    ]
    if not result.evaluated:
        lines.append(f"NOT EVALUATED: {result.reason}")
        if result.reason == "no-reference-corpus":
            lines.append("hint: set VAR_LICENSE_CORPUS_PATH to a reference corpus file")
    return "\n".join(lines)


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    result = scan(opts["component_id"], Path(opts["repo_root"]))
    if opts["format"] == "json":
        print(json.dumps(result.to_dict()))
    else:
        print(_text(result))
    return 1 if result.blocked else 0


if __name__ == "__main__":
    sys.exit(main())
