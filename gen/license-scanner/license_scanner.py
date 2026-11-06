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

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRIPLE_DOUBLE_RE = re.compile(r'""".*?"""', re.DOTALL)
_TRIPLE_SINGLE_RE = re.compile(r"'''.*?'''", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?://|#).*?$", re.MULTILINE)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_WINDOW_SIZE = 9
_GATE_NAME = "license_scanner"


def _component_slug(component_id: str) -> str:
    prefix = "comp-"
    return component_id[len(prefix):] if component_id.startswith(prefix) else component_id


def _strip_comments(text: str) -> str:
    text = _BLOCK_COMMENT_RE.sub(" ", text)
    text = _TRIPLE_DOUBLE_RE.sub(" ", text)
    text = _TRIPLE_SINGLE_RE.sub(" ", text)
    text = _LINE_COMMENT_RE.sub("", text)
    return text


def _tokenize(text: str) -> list:
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


def _component_files(repo_root: Path, slug: str):
    component_dir = Path(repo_root) / "gen" / slug
    if not component_dir.is_dir():
        return []
    return [p for p in sorted(component_dir.rglob("*")) if p.is_file()]


def _fingerprint_component(repo_root: Path, slug: str) -> set:
    texts = []
    for path in _component_files(repo_root, slug):
        try:
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    combined = "\n".join(texts)
    tokens = _tokenize(_strip_comments(combined))
    hashes = set()
    for i in range(len(tokens) - _WINDOW_SIZE + 1):
        window = "\x1f".join(tokens[i:i + _WINDOW_SIZE])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return hashes


def _hash_component_dir(repo_root: Path, slug: str) -> str:
    h = hashlib.sha256()
    for path in _component_files(repo_root, slug):
        component_dir = Path(repo_root) / "gen" / slug
        rel = path.relative_to(component_dir).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        try:
            h.update(path.read_bytes())
        except OSError:
            pass
        h.update(b"\x00")
    return h.hexdigest()


def _validate_corpus(data) -> bool:
    if not isinstance(data, dict):
        return False
    entries = data.get("entries")
    if not isinstance(entries, list):
        return False
    if "corpus_version" in data:
        cv = data["corpus_version"]
        if isinstance(cv, bool) or not isinstance(cv, int) or cv < 0:
            return False
    if "block_threshold" in data:
        bt = data["block_threshold"]
        if isinstance(bt, bool) or not isinstance(bt, (int, float)) or not (0 < bt <= 1):
            return False
    if len(entries) < 1:
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        hashes = entry.get("hashes")
        if not isinstance(hashes, list) or not all(isinstance(x, str) for x in hashes):
            return False
        if entry.get("risk_tier") not in ("high", "medium", "low"):
            return False
    return True


def _corpus_status(repo_root: Path) -> dict:
    raw_path = os.environ.get("VAR_LICENSE_CORPUS_PATH", "")
    if not raw_path:
        return {"status": "no-reference-corpus", "corpus": None, "file_bytes": None}
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(repo_root) / path
    try:
        file_bytes = path.read_bytes()
    except OSError:
        return {"status": "corpus-unreadable", "corpus": None, "file_bytes": None}
    try:
        data = json.loads(file_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "corpus-invalid", "corpus": None, "file_bytes": file_bytes}
    if not _validate_corpus(data):
        return {"status": "corpus-invalid", "corpus": None, "file_bytes": file_bytes}
    return {"status": "usable", "corpus": data, "file_bytes": file_bytes}


def _gate_version_for_status(status_info: dict) -> str:
    status = status_info["status"]
    if status == "usable":
        corpus = status_info["corpus"]
        corpus_version = corpus.get("corpus_version", 0)
        digest = hashlib.sha256(status_info["file_bytes"]).hexdigest()[:12]
        return f"{_GATE_NAME}@4.0.{corpus_version}+{digest}"
    return f"{_GATE_NAME}@4.0.0-{status}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_cache_manager(repo_root: Path):
    base = Path(repo_root) / "gen" / "cache-manager"
    flat = base / "cache_manager.py"
    pkg_init = base / "cache_manager" / "__init__.py"
    if flat.is_file():
        module_path = flat
        submodule_locations = None
    elif pkg_init.is_file():
        module_path = pkg_init
        submodule_locations = [str(pkg_init.parent)]
    else:
        return None

    module_name = f"_license_scanner_dep_cache_manager_{abs(hash(str(module_path.resolve())))}"
    try:
        if submodule_locations is not None:
            spec = importlib.util.spec_from_file_location(
                module_name, module_path, submodule_search_locations=submodule_locations
            )
        else:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        # Must be registered before exec_module: dataclasses defined in the
        # loaded module resolve their own annotations via sys.modules[cls.__module__].
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        sys.modules.pop(module_name, None)
        return None


def _send_webhook(url: str, payload: dict):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        return None
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {"category": "auth", "message": str(exc)}
        return {"category": "network", "message": str(exc)}
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            return {"category": "timeout", "message": str(exc)}
        return {"category": "network", "message": str(exc)}
    except TimeoutError as exc:
        return {"category": "timeout", "message": str(exc)}
    except Exception as exc:
        return {"category": "network", "message": str(exc)}


def _fresh_scan(component_id: str, status_info: dict, gate_version_str: str, component_hashes: set) -> dict:
    status = status_info["status"]
    if status != "usable":
        evaluated = False
        reason = status
        similarity_score = None
        block_threshold = None
        matches = []
        blocked = status in ("corpus-unreadable", "corpus-invalid")
    else:
        evaluated = True
        reason = None
        corpus = status_info["corpus"]
        block_threshold = corpus.get("block_threshold", 0.70)
        entries = corpus.get("entries", [])
        scored = []
        for entry in entries:
            entry_hashes = set(entry.get("hashes", []))
            if component_hashes:
                score = len(component_hashes & entry_hashes) / len(component_hashes)
            else:
                score = 0.0
            scored.append((entry, score))
        similarity_score = max((s for _, s in scored), default=0.0)
        matches = [
            {
                "reference_id": entry.get("reference_id"),
                "license_family": entry.get("license_family"),
                "risk_tier": entry.get("risk_tier"),
                "score": score,
            }
            for entry, score in scored
            if score > 0.0
        ]
        blocked = similarity_score >= block_threshold

    has_high_risk_match = any(m["risk_tier"] == "high" for m in matches)
    due = blocked or has_high_risk_match
    webhook_url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL", "")

    notified = False
    notification_delivery_error = None
    if due and webhook_url:
        notified = True
        webhook_payload = {
            "component_id": component_id,
            "gate_version": gate_version_str,
            "evaluated": evaluated,
            "reason": reason,
            "similarity_score": similarity_score,
            "block_threshold": block_threshold,
            "blocked": blocked,
            "matches": matches,
        }
        notification_delivery_error = _send_webhook(webhook_url, webhook_payload)

    return {
        "component_id": component_id,
        "gate_version": gate_version_str,
        "evaluated": evaluated,
        "reason": reason,
        "similarity_score": similarity_score,
        "block_threshold": block_threshold,
        "blocked": blocked,
        "matches": matches,
        "notified": notified,
        "notification_delivery_error": notification_delivery_error,
    }


def gate_version(repo_root) -> str:
    status_info = _corpus_status(Path(repo_root))
    return _gate_version_for_status(status_info)


def scan(component_id: str, repo_root) -> dict:
    repo_root = Path(repo_root)
    slug = _component_slug(component_id)

    status_info = _corpus_status(repo_root)
    gate_version_str = _gate_version_for_status(status_info)
    gate_inputs_hash = _hash_component_dir(repo_root, slug)
    spec_bundle_hash = f"sha256:{gate_inputs_hash}"
    model_pin = "none"

    cache_module = _load_cache_manager(repo_root)
    cache_key = None
    if cache_module is not None:
        try:
            cache_key = cache_module.CacheKey(
                spec_bundle_hash=spec_bundle_hash,
                gate_inputs_hash=gate_inputs_hash,
                gate_version=gate_version_str,
                model_pin=model_pin,
            )
            get_result = cache_module.get(cache_key, repo_root=repo_root)
            payload = (
                get_result.get("payload")
                if isinstance(get_result, dict)
                else getattr(get_result, "payload", None)
            )
        except Exception:
            payload = None
            cache_key = None

        if payload is not None:
            result = dict(payload) if isinstance(payload, dict) else dict(vars(payload))
            result["cache_hit"] = True
            return result

    component_hashes = _fingerprint_component(repo_root, slug)
    result = _fresh_scan(component_id, status_info, gate_version_str, component_hashes)
    result["cache_hit"] = False

    if cache_module is not None and cache_key is not None:
        cached_result = cache_module.CachedResult(
            gate_type="license_scanner",
            payload=dict(result),
            stored_at=_now_iso(),
        )
        cache_module.put(cache_key, cached_result, repo_root=repo_root)

    return result


def _usage_error(message: str) -> int:
    print(f"usage error: {message}", file=sys.stderr)
    return 2


def main(argv) -> int:
    args = list(argv)
    repo_root = "."
    fmt = "text"
    positional = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--repo-root":
            if i + 1 >= len(args):
                return _usage_error("--repo-root requires a value")
            repo_root = args[i + 1]
            i += 2
        elif arg.startswith("--repo-root="):
            repo_root = arg[len("--repo-root="):]
            i += 1
        elif arg == "--format":
            if i + 1 >= len(args):
                return _usage_error("--format requires a value")
            fmt = args[i + 1]
            i += 2
        elif arg.startswith("--format="):
            fmt = arg[len("--format="):]
            i += 1
        elif arg.startswith("-"):
            return _usage_error(f"unknown argument {arg}")
        else:
            positional.append(arg)
            i += 1

    if fmt not in ("json", "text"):
        return _usage_error(f"invalid --format value {fmt!r}")

    if len(positional) != 1:
        return _usage_error("expected exactly one <component-id>")

    component_id = positional[0]
    result = scan(component_id, Path(repo_root))

    if fmt == "json":
        print(json.dumps(result))
    else:
        print(f"component_id: {result['component_id']}")
        print(f"gate_version: {result['gate_version']}")
        print(f"similarity_score: {result['similarity_score']}")
        print(f"block_threshold: {result['block_threshold']}")
        print(f"blocked: {result['blocked']}")
        print(f"notified: {result['notified']}")
        if not result["evaluated"]:
            hint = ""
            if result["reason"] == "no-reference-corpus":
                hint = " (set VAR_LICENSE_CORPUS_PATH to configure a reference corpus)"
            print(f"NOT EVALUATED: {result['reason']}{hint}")

    return 1 if result["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))