"""License scanner: k-gram fingerprint comparison of gen/<component>/ against a
precomputed reference corpus (R-LICENSE-001..011)."""

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

__all__ = ["LicenseScanResult", "scan", "gate_version", "main"]

WINDOW_SIZE = 9
DEFAULT_BLOCK_THRESHOLD = 0.70
RISK_TIERS = ("high", "medium", "low")
GATE_TYPE = "license_scanner"
MODEL_PIN = "none"
WEBHOOK_TIMEOUT_SECONDS = 10

CORPUS_ENV = "VAR_LICENSE_CORPUS_PATH"
WEBHOOK_ENV = "VAR_COMPLIANCE_WEBHOOK_URL"

USAGE = "usage: hotdocs license-scan <component-id> [--repo-root=<dir>] [--format=json|text]"

_COMMENT_RE = re.compile(
    r'/\*.*?\*/|""".*?"""|\'\'\'.*?\'\'\'|//[^\n]*|#[^\n]*',
    re.DOTALL,
)
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


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _field(obj, name):
    """Dual dict-or-attribute access."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _corpus_is_valid(corpus) -> bool:
    if not isinstance(corpus, dict):
        return False
    entries = corpus.get("entries")
    if not isinstance(entries, list) or not entries:
        return False
    if "corpus_version" in corpus:
        version = corpus["corpus_version"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            return False
    if "block_threshold" in corpus:
        threshold = corpus["block_threshold"]
        if not _is_number(threshold) or not 0 < threshold <= 1:
            return False
    return all(
        isinstance(entry, dict)
        and isinstance(entry.get("hashes"), list)
        and all(isinstance(h, str) for h in entry["hashes"])
        and entry.get("risk_tier") in RISK_TIERS
        for entry in entries
    )


def _load_corpus(repo_root):
    """Return (reason, corpus, raw_bytes). reason is None for a usable corpus."""
    configured = os.environ.get(CORPUS_ENV, "")
    if not configured:
        return "no-reference-corpus", None, None
    path = Path(repo_root) / configured
    try:
        raw = path.read_bytes()
    except OSError:
        return "corpus-unreadable", None, None
    try:
        corpus = json.loads(raw)
    except ValueError:
        return "corpus-invalid", None, None
    if not _corpus_is_valid(corpus):
        return "corpus-invalid", None, None
    return None, corpus, raw


def _gate_version_for(reason, corpus, raw) -> str:
    if reason is not None:
        return f"license_scanner@4.0.0-{reason}"
    version = corpus.get("corpus_version", 0)
    return f"license_scanner@4.0.{version}+{_sha256_hex(raw)[:12]}"


def _component_files(component_dir: Path) -> list:
    return sorted(p for p in component_dir.rglob("*") if p.is_file())


def _gate_inputs_hash(component_dir: Path, files: list) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(component_dir).as_posix().encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return "sha256:" + digest.hexdigest()


def _window_hashes(text: str) -> set:
    stripped = _COMMENT_RE.sub(" ", text)
    tokens = [t.lower() for t in _TOKEN_RE.findall(stripped)]
    return {
        _sha256_hex("\x1f".join(tokens[i:i + WINDOW_SIZE]).encode("utf-8"))
        for i in range(len(tokens) - WINDOW_SIZE + 1)
    }


def _component_windows(files: list) -> set:
    windows = set()
    for path in files:
        windows |= _window_hashes(path.read_bytes().decode("utf-8", errors="replace"))
    return windows


def _tool_root() -> Path:
    here = Path(__file__).resolve().parent
    return next(d.parent for d in (here, *here.parents) if d.name == "gen")


def _load_cache_manager(repo_root):
    try:
        base = Path(repo_root) / "gen" / "cache-manager"
        if not base.is_dir():
            base = _tool_root() / "gen" / "cache-manager"
        package_init = base / "cache_manager" / "__init__.py"
        if package_init.is_file():
            spec = importlib.util.spec_from_file_location(
                "cache_manager",
                package_init,
                submodule_search_locations=[str(package_init.parent)],
            )
        else:
            spec = importlib.util.spec_from_file_location(
                "cache_manager", base / "cache_manager.py"
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules["cache_manager"] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _classify_delivery_error(exc: Exception) -> dict:
    if isinstance(exc, urllib.error.HTTPError):
        category = "auth" if exc.code in (401, 403) else "network"
        return {"category": category, "message": f"HTTP {exc.code}"}
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, TimeoutError):
        return {"category": "timeout", "message": str(exc)}
    return {"category": "network", "message": str(exc)}


def _send_notification(url: str, payload: dict):
    """Attempt the webhook exactly once; return a delivery error dict or None."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=WEBHOOK_TIMEOUT_SECONDS):
            pass
    except Exception as exc:
        return _classify_delivery_error(exc)
    return None


def _result_from_payload(payload) -> LicenseScanResult:
    values = {f.name: _field(payload, f.name) for f in dataclasses.fields(LicenseScanResult)}
    values["cache_hit"] = True
    return LicenseScanResult(**values)


def _compute(component_id, gv, reason, corpus, files, webhook_url) -> LicenseScanResult:
    if reason is not None:
        evaluated = False
        score = None
        threshold = None
        blocked = reason != "no-reference-corpus"
        matches = []
    else:
        evaluated = True
        windows = _component_windows(files)
        scored = []
        for entry in corpus["entries"]:
            hits = len(windows & set(entry["hashes"]))
            scored.append((hits / max(len(windows), 1), entry))
        score = max(s for s, _ in scored)
        threshold = float(corpus.get("block_threshold", DEFAULT_BLOCK_THRESHOLD))
        blocked = score >= threshold
        matches = [
            {
                "reference_id": entry.get("reference_id"),
                "license_family": entry.get("license_family"),
                "risk_tier": entry["risk_tier"],
                "score": s,
            }
            for s, entry in sorted(scored, key=lambda item: -item[0])
            if s > 0
        ]
    due = blocked or any(m["risk_tier"] == "high" for m in matches)
    notified = bool(webhook_url) and due
    return LicenseScanResult(
        component_id=component_id,
        gate_version=gv,
        evaluated=evaluated,
        reason=reason,
        similarity_score=score,
        block_threshold=threshold,
        blocked=blocked,
        matches=matches,
        notified=notified,
        notification_delivery_error=None,
        cache_hit=False,
    )


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------

def gate_version(repo_root: Path) -> str:
    reason, corpus, raw = _load_corpus(repo_root)
    return _gate_version_for(reason, corpus, raw)


def scan(component_id: str, repo_root: Path) -> LicenseScanResult:
    repo_root = Path(repo_root)
    reason, corpus, raw = _load_corpus(repo_root)
    gv = _gate_version_for(reason, corpus, raw)

    component_dir = repo_root / "gen" / component_id.removeprefix("comp-")
    files = _component_files(component_dir)

    cache_manager = _load_cache_manager(repo_root)
    cache_key = None
    if cache_manager is not None:
        cache_key = cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + _sha256_hex(component_id.encode("utf-8")),
            gate_inputs_hash=_gate_inputs_hash(component_dir, files),
            gate_version=gv,
            model_pin=MODEL_PIN,
        )
        cached = cache_manager.get(cache_key, repo_root=repo_root)
        payload = _field(cached, "payload")
        if payload is not None:
            return _result_from_payload(payload)

    webhook_url = os.environ.get(WEBHOOK_ENV, "")
    result = _compute(component_id, gv, reason, corpus, files, webhook_url)
    if result.notified:
        result.notification_delivery_error = _send_notification(
            webhook_url, dataclasses.asdict(result)
        )

    if cache_manager is not None:
        cached_result = cache_manager.CachedResult(
            gate_type=GATE_TYPE,
            payload=dataclasses.asdict(result),
            stored_at=_now_iso(),
        )
        cache_manager.put(cache_key, cached_result, repo_root=repo_root)
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

class _UsageError(Exception):
    pass


def _parse_args(argv: list) -> dict:
    options = {"repo-root": ".", "format": "text"}
    component_id = None
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            name, sep, value = token[2:].partition("=")
            if name not in options:
                raise _UsageError(f"unknown argument: {token}")
            if not sep:
                if i + 1 >= len(argv):
                    raise _UsageError(f"--{name} requires a value")
                i += 1
                value = argv[i]
            options[name] = value
        elif token.startswith("-") or component_id is not None:
            raise _UsageError(f"unknown argument: {token}")
        else:
            component_id = token
        i += 1
    if component_id is None:
        raise _UsageError("missing <component-id>")
    if options["format"] not in ("json", "text"):
        raise _UsageError(f"invalid --format: {options['format']}")
    return {
        "component_id": component_id,
        "repo_root": Path(options["repo-root"]),
        "format": options["format"],
    }


def _render_text(result: LicenseScanResult) -> str:
    lines = [
        f"component_id: {result.component_id}",
        f"gate_version: {result.gate_version}",
        f"similarity_score: {json.dumps(result.similarity_score)}",
        f"block_threshold: {json.dumps(result.block_threshold)}",
        f"blocked: {json.dumps(result.blocked)}",
        f"notified: {json.dumps(result.notified)}",
    ]
    for match in result.matches:
        lines.append(
            f"match: {match['reference_id']} {match['license_family']} "
            f"risk_tier={match['risk_tier']} score={match['score']}"
        )
    if not result.evaluated:
        lines.append(f"NOT EVALUATED: {result.reason}")
        if result.reason == "no-reference-corpus":
            lines.append(f"hint: set {CORPUS_ENV} to a reference corpus file to enable this scan")
    return "\n".join(lines)


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = _parse_args(list(argv))
    except _UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    result = scan(args["component_id"], args["repo_root"])
    if args["format"] == "json":
        print(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        print(_render_text(result))
    return 1 if result.blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
