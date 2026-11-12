"""License scanner: k-gram fingerprint comparison of gen/<component>/ against a
reference corpus of precomputed window hashes (R-LICENSE-001..011)."""

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

WINDOW_SIZE = 9
DEFAULT_BLOCK_THRESHOLD = 0.70
DEFAULT_CORPUS_VERSION = 0
GATE_TYPE = "license_scanner"
MODEL_PIN = "none"
RISK_TIERS = ("high", "medium", "low")
CORPUS_ENV = "VAR_LICENSE_CORPUS_PATH"
WEBHOOK_ENV = "VAR_COMPLIANCE_WEBHOOK_URL"
WEBHOOK_TIMEOUT_SECONDS = 10

REASON_NO_CORPUS = "no-reference-corpus"
REASON_UNREADABLE = "corpus-unreadable"
REASON_INVALID = "corpus-invalid"

_COMMENT_RE = re.compile(
    r'/\*.*?\*/|""".*?"""|\'\'\'.*?\'\'\'|//[^\n]*|#[^\n]*', re.DOTALL
)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")

USAGE = (
    "usage: hotdocs license-scan <component-id> "
    "[--repo-root=<dir>] [--format=json|text]"
)


@dataclasses.dataclass
class LicenseScanResult:
    component_id: str
    gate_version: str
    evaluated: bool
    reason: object
    similarity_score: object
    block_threshold: object
    blocked: bool
    matches: list
    notified: bool
    notification_delivery_error: object
    cache_hit: bool


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(component_id: str) -> str:
    return component_id.removeprefix("comp-")


# --------------------------------------------------------------------------
# reference corpus
# --------------------------------------------------------------------------


def _is_nonneg_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_threshold(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 < value <= 1
    )


def _is_valid_entry(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    hashes = entry.get("hashes")
    if not isinstance(hashes, list) or not all(isinstance(h, str) for h in hashes):
        return False
    return entry.get("risk_tier") in RISK_TIERS


def _is_usable_corpus(data) -> bool:
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return False
    if "corpus_version" in data and not _is_nonneg_int(data["corpus_version"]):
        return False
    if "block_threshold" in data and not _is_threshold(data["block_threshold"]):
        return False
    if not data["entries"]:
        return False
    return all(_is_valid_entry(entry) for entry in data["entries"])


def _load_corpus(repo_root: Path):
    """Return (reason, corpus, raw_bytes); reason is None for a usable corpus."""
    configured = os.environ.get(CORPUS_ENV, "")
    if not configured:
        return REASON_NO_CORPUS, None, None
    path = Path(repo_root) / configured
    try:
        raw = path.read_bytes()
    except OSError:
        return REASON_UNREADABLE, None, None
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        return REASON_INVALID, None, None
    if not _is_usable_corpus(data):
        return REASON_INVALID, None, None
    return None, data, raw


def _gate_version_for(reason, corpus, raw) -> str:
    if reason is not None:
        return f"license_scanner@4.0.0-{reason}"
    version = corpus.get("corpus_version", DEFAULT_CORPUS_VERSION)
    return f"license_scanner@4.0.{version}+{_sha256_hex(raw)[:12]}"


def gate_version(repo_root: Path) -> str:
    return _gate_version_for(*_load_corpus(Path(repo_root)))


# --------------------------------------------------------------------------
# fingerprinting
# --------------------------------------------------------------------------


def _component_files(repo_root: Path, component_id: str):
    gen_dir = Path(repo_root) / "gen" / _slug(component_id)
    return [
        (path.relative_to(gen_dir).as_posix(), path.read_bytes())
        for path in sorted(p for p in gen_dir.rglob("*") if p.is_file())
    ]


def _tokens(text: str):
    stripped = _COMMENT_RE.sub(" ", text)
    return [tok.lower() for tok in _TOKEN_RE.findall(stripped)]


def _window_hashes(files) -> set:
    hashes = set()
    for _name, data in files:
        tokens = _tokens(data.decode("utf-8", errors="replace"))
        for i in range(len(tokens) - WINDOW_SIZE + 1):
            window = "\x1f".join(tokens[i : i + WINDOW_SIZE])
            hashes.add(_sha256_hex(window.encode("utf-8")))
    return hashes


def _inputs_hash(component_id: str, files) -> str:
    digest = hashlib.sha256()
    digest.update(component_id.encode("utf-8") + b"\x00")
    for name, data in files:
        digest.update(name.encode("utf-8") + b"\x00")
        digest.update(_sha256_hex(data).encode("ascii") + b"\x00")
    return "sha256:" + digest.hexdigest()


# --------------------------------------------------------------------------
# notification
# --------------------------------------------------------------------------


def _deliver(url: str, result: LicenseScanResult):
    body = json.dumps(dataclasses.asdict(result)).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=WEBHOOK_TIMEOUT_SECONDS) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        category = "auth" if exc.code in (401, 403) else "network"
        return {"category": category, "message": f"HTTP {exc.code}"}
    except TimeoutError as exc:
        return {"category": "timeout", "message": str(exc)}
    except urllib.error.URLError as exc:
        category = "timeout" if isinstance(exc.reason, TimeoutError) else "network"
        return {"category": category, "message": str(exc.reason)}
    except Exception as exc:  # any other delivery failure is never raised
        return {"category": "network", "message": str(exc)}
    return None


# --------------------------------------------------------------------------
# cache-manager loading
# --------------------------------------------------------------------------


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_cache_manager(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / "cache-manager"
    if not dep_dir.is_dir():
        tool_root = _tool_root()
        if tool_root is None:
            return None
        dep_dir = tool_root / "gen" / "cache-manager"
    flat = dep_dir / "cache_manager.py"
    package_init = dep_dir / "cache_manager" / "__init__.py"
    name = "_license_scanner_dep_cache_manager_" + _sha256_hex(
        str(dep_dir.resolve()).encode("utf-8")
    )[:16]
    try:
        if flat.is_file():
            spec = importlib.util.spec_from_file_location(name, flat)
        else:
            spec = importlib.util.spec_from_file_location(
                name,
                package_init,
                submodule_search_locations=[str(package_init.parent)],
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        return None
    return module


# --------------------------------------------------------------------------
# scan
# --------------------------------------------------------------------------


def _evaluate(component_id, reason, corpus, version, files) -> LicenseScanResult:
    if reason is None:
        component_hashes = _window_hashes(files)
        threshold = corpus.get("block_threshold", DEFAULT_BLOCK_THRESHOLD)
        matches = []
        similarity = 0.0
        for entry in corpus["entries"]:
            shared = len(component_hashes & set(entry["hashes"]))
            score = shared / len(component_hashes) if component_hashes else 0.0
            similarity = max(similarity, score)
            if score > 0:
                matches.append(
                    {
                        "reference_id": entry.get("reference_id"),
                        "license_family": entry.get("license_family"),
                        "risk_tier": entry["risk_tier"],
                        "score": score,
                    }
                )
        matches = sorted(matches, key=lambda m: -m["score"])
        blocked = similarity >= threshold
    else:
        similarity = None
        threshold = None
        matches = []
        blocked = reason != REASON_NO_CORPUS

    high_risk = any(m["risk_tier"] == "high" for m in matches)
    webhook = os.environ.get(WEBHOOK_ENV, "")
    notified = bool(webhook) and (blocked or high_risk)

    result = LicenseScanResult(
        component_id=component_id,
        gate_version=version,
        evaluated=reason is None,
        reason=reason,
        similarity_score=similarity,
        block_threshold=threshold,
        blocked=blocked,
        matches=matches,
        notified=notified,
        notification_delivery_error=None,
        cache_hit=False,
    )
    if notified:
        result.notification_delivery_error = _deliver(webhook, result)
    return result


def _from_payload(payload) -> LicenseScanResult:
    values = {
        f.name: _field(payload, f.name)
        for f in dataclasses.fields(LicenseScanResult)
        if f.name != "cache_hit"
    }
    return LicenseScanResult(**values, cache_hit=True)


def scan(component_id: str, repo_root: Path) -> LicenseScanResult:
    repo_root = Path(repo_root)
    reason, corpus, raw = _load_corpus(repo_root)
    version = _gate_version_for(reason, corpus, raw)
    files = _component_files(repo_root, component_id)

    cache_manager = _load_cache_manager(repo_root)
    cache_key = None
    if cache_manager is not None:
        cache_key = cache_manager.CacheKey(
            spec_bundle_hash="sha256:" + _sha256_hex(component_id.encode("utf-8")),
            gate_inputs_hash=_inputs_hash(component_id, files),
            gate_version=version,
            model_pin=MODEL_PIN,
        )
        cached = cache_manager.get(cache_key, repo_root=repo_root)
        payload = _field(cached, "payload")
        if payload is not None:
            return _from_payload(payload)

    result = _evaluate(component_id, reason, corpus, version, files)

    if cache_manager is not None:
        cached_result = cache_manager.CachedResult(
            gate_type=GATE_TYPE,
            payload=dataclasses.asdict(result),
            stored_at=_utc_now_iso(),
        )
        cache_manager.put(cache_key, cached_result, repo_root=repo_root)
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _usage_error(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _print_text(result: LicenseScanResult) -> None:
    print(f"component_id: {result.component_id}")
    print(f"gate_version: {result.gate_version}")
    print(f"evaluated: {json.dumps(result.evaluated)}")
    print(f"similarity_score: {json.dumps(result.similarity_score)}")
    print(f"block_threshold: {json.dumps(result.block_threshold)}")
    print(f"blocked: {json.dumps(result.blocked)}")
    print(f"matches: {len(result.matches)}")
    for match in result.matches:
        print(
            f"  - {match['reference_id']} ({match['license_family']}, "
            f"risk_tier={match['risk_tier']}): {match['score']}"
        )
    print(f"notified: {json.dumps(result.notified)}")
    print(
        "notification_delivery_error: "
        f"{json.dumps(result.notification_delivery_error)}"
    )
    print(f"cache_hit: {json.dumps(result.cache_hit)}")
    if not result.evaluated:
        print(f"NOT EVALUATED: {result.reason}")
        if result.reason == REASON_NO_CORPUS:
            print(
                f"hint: set {CORPUS_ENV} to a reference corpus file "
                "to enable license scanning"
            )


def main(argv) -> int:
    argv = list(argv)
    options = {"--repo-root": ".", "--format": "text"}
    component_id = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        name, sep, value = arg.partition("=")
        if name in options:
            if not sep:
                if i + 1 >= len(argv):
                    return _usage_error(f"{name} requires a value")
                i += 1
                value = argv[i]
            options[name] = value
        elif component_id is None and not arg.startswith("-"):
            component_id = arg
        else:
            return _usage_error(f"unknown argument: {arg}")
        i += 1

    if component_id is None:
        return _usage_error("missing <component-id>")
    if options["--format"] not in ("json", "text"):
        return _usage_error(f"invalid --format: {options['--format']}")

    result = scan(component_id, Path(options["--repo-root"]))
    if options["--format"] == "json":
        print(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        _print_text(result)
    return 1 if result.blocked else 0