"""License scanner: k-gram fingerprint scan of gen/<component>/ against a reference corpus."""

import hashlib
import importlib.util
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRIPLE_DQ_RE = re.compile(r'""".*?"""', re.DOTALL)
_TRIPLE_SQ_RE = re.compile(r"'''.*?'''", re.DOTALL)
_LINE_COMMENT_SLASH_RE = re.compile(r"//[^\n]*")
_LINE_COMMENT_HASH_RE = re.compile(r"#[^\n]*")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_WINDOW_SIZE = 9

# Filters near-zero-overlap noise out of the reported matches list; strictly
# below any realistic block_threshold so a flagged result always has matches.
_REPORTING_FLOOR = 0.1


def _dual_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _component_slug(component_id: str) -> str:
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _read_component_files(component_dir: Path):
    files = []
    if not component_dir.is_dir():
        return files
    for path in sorted(component_dir.rglob("*")):
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = path.relative_to(component_dir).as_posix()
            files.append((rel, text))
    return files


def _content_hash(files) -> str:
    h = hashlib.sha256()
    for rel, text in files:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(text.encode("utf-8"))
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()


def _normalize_and_tokenize(text: str):
    text = _COMMENT_BLOCK_RE.sub("", text)
    text = _TRIPLE_DQ_RE.sub("", text)
    text = _TRIPLE_SQ_RE.sub("", text)
    text = _LINE_COMMENT_SLASH_RE.sub("", text)
    text = _LINE_COMMENT_HASH_RE.sub("", text)
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _window_hashes(tokens):
    hashes = set()
    if len(tokens) < _WINDOW_SIZE:
        return hashes
    for i in range(len(tokens) - _WINDOW_SIZE + 1):
        joined = "\x1f".join(tokens[i:i + _WINDOW_SIZE])
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


def _component_hashes(files):
    all_hashes = set()
    for _rel, text in files:
        all_hashes |= _window_hashes(_normalize_and_tokenize(text))
    return all_hashes


def _load_corpus(repo_root: Path):
    path_str = os.environ.get("VAR_LICENSE_CORPUS_PATH", "")
    if not path_str:
        return 0, 0.70, []
    p = Path(path_str)
    if not p.is_absolute():
        p = Path(repo_root) / p
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return 0, 0.70, []
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return 0, 0.70, []
    corpus_version = data.get("corpus_version", 0)
    block_threshold = data.get("block_threshold", 0.70)
    entries = data.get("entries", [])
    return corpus_version, block_threshold, entries


def _load_cache_manager(repo_root: Path):
    base = Path(repo_root) / "gen" / "cache-manager"
    pkg_init = base / "__init__.py"
    flat = base / "cache_manager.py"
    module_name = "cache_manager"
    if pkg_init.exists():
        module_path = pkg_init
        search_locations = [str(base)]
    elif flat.exists():
        module_path = flat
        search_locations = None
    else:
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            module_name, module_path, submodule_search_locations=search_locations
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _send_webhook(url: str, payload: dict):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        return None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {"category": "auth", "message": str(e)}
        return {"category": "network", "message": str(e)}
    except (socket.timeout, TimeoutError):
        return {"category": "timeout", "message": "request timed out"}
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return {"category": "timeout", "message": str(e)}
        return {"category": "network", "message": str(e)}
    except Exception as e:
        return {"category": "network", "message": str(e)}


def gate_version(repo_root: Path) -> str:
    corpus_version, _block_threshold, _entries = _load_corpus(Path(repo_root))
    return f"license_scanner@3.1.{corpus_version}"


def scan(component_id: str, repo_root: Path) -> dict:
    repo_root = Path(repo_root)
    slug = _component_slug(component_id)
    component_dir = repo_root / "gen" / slug
    files = _read_component_files(component_dir)

    corpus_version, block_threshold, entries = _load_corpus(repo_root)
    gv = f"license_scanner@3.1.{corpus_version}"

    # No spec bundle object is passed to scan(); the only deterministic input
    # available is the scanned content itself, so it stands in for both hash
    # fields. No model is involved, so model_pin is empty.
    content_hash = _content_hash(files)
    cache_key_fields = {
        "spec_bundle_hash": content_hash,
        "gate_inputs_hash": content_hash,
        "gate_version": gv,
        "model_pin": "",
    }

    cache_manager = _load_cache_manager(repo_root)
    cache_key = None
    cached = None
    if cache_manager is not None:
        try:
            cache_key = cache_manager.CacheKey(**cache_key_fields)
            cached = cache_manager.get(cache_key, repo_root=repo_root)
        except Exception:
            cache_key = None
            cached = None

    payload = _dual_get(cached, "payload", None) if cached is not None else None
    if payload is not None:
        if isinstance(payload, dict):
            result = dict(payload)
        else:
            result = dict(vars(payload))
        result["cache_hit"] = True
        return result

    component_hashes = _component_hashes(files)
    scored_entries = []
    for entry in entries:
        entry_hashes = set(entry.get("hashes", []) or [])
        if not component_hashes:
            score = 0.0
        else:
            score = len(component_hashes & entry_hashes) / len(component_hashes)
        scored_entries.append((entry, score))

    similarity_score = max((score for _e, score in scored_entries), default=0.0)
    blocked = similarity_score >= block_threshold

    matches = []
    for entry, score in sorted(scored_entries, key=lambda pair: pair[1], reverse=True):
        if score > _REPORTING_FLOOR:
            matches.append({
                "reference_id": entry.get("reference_id"),
                "license_family": entry.get("license_family"),
                "risk_tier": entry.get("risk_tier"),
                "score": score,
            })

    webhook_url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL", "")
    due = blocked or any(m["risk_tier"] == "high" for m in matches)
    notified = bool(due and webhook_url)

    notification_delivery_error = None
    if notified:
        notification_delivery_error = _send_webhook(webhook_url, {
            "component_id": component_id,
            "gate_version": gv,
            "similarity_score": similarity_score,
            "blocked": blocked,
            "matches": matches,
        })

    result = {
        "component_id": component_id,
        "gate_version": gv,
        "similarity_score": similarity_score,
        "block_threshold": block_threshold,
        "blocked": blocked,
        "matches": matches,
        "notified": notified,
        "notification_delivery_error": notification_delivery_error,
        "cache_hit": False,
    }

    if cache_manager is not None and cache_key is not None:
        try:
            cached_result = cache_manager.CachedResult(
                gate_type="license_scanner",
                payload=dict(result),
                stored_at=datetime.now(timezone.utc).isoformat(),
            )
            cache_manager.put(cache_key, cached_result, repo_root=repo_root)
        except Exception:
            pass

    return result


def _format_text(result: dict) -> str:
    lines = [
        f"component_id: {result['component_id']}",
        f"gate_version: {result['gate_version']}",
        f"similarity_score: {result['similarity_score']}",
        f"block_threshold: {result['block_threshold']}",
        f"blocked: {result['blocked']}",
        f"notified: {result['notified']}",
        f"cache_hit: {result['cache_hit']}",
    ]
    if result["matches"]:
        lines.append("matches:")
        for m in result["matches"]:
            lines.append(
                f"  - reference_id={m['reference_id']} license_family={m['license_family']} "
                f"risk_tier={m['risk_tier']} score={m['score']}"
            )
    if result["notification_delivery_error"]:
        lines.append(f"notification_delivery_error: {result['notification_delivery_error']}")
    return "\n".join(lines)


def main(argv) -> int:
    if not argv:
        sys.stderr.write("usage error: missing <component-id>\n")
        return 2

    component_id = argv[0]
    if component_id.startswith("--"):
        sys.stderr.write("usage error: missing <component-id>\n")
        return 2

    rest = argv[1:]
    repo_root_value = "."
    format_value = "text"
    i = 0
    while i < len(rest):
        tok = rest[i]
        if not tok.startswith("--"):
            sys.stderr.write(f"usage error: unknown argument {tok!r}\n")
            return 2
        if "=" in tok:
            flag, _, value = tok.partition("=")
            i += 1
        else:
            flag = tok
            if i + 1 >= len(rest):
                sys.stderr.write(f"usage error: flag {flag!r} given with no value\n")
                return 2
            value = rest[i + 1]
            i += 2
        if flag == "--repo-root":
            repo_root_value = value
        elif flag == "--format":
            format_value = value
        else:
            sys.stderr.write(f"usage error: unknown flag {flag!r}\n")
            return 2

    if format_value not in ("json", "text"):
        sys.stderr.write(f"usage error: invalid --format {format_value!r}\n")
        return 2

    result = scan(component_id, Path(repo_root_value))

    if format_value == "json":
        print(json.dumps(result))
    else:
        print(_format_text(result))

    return 1 if result["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))