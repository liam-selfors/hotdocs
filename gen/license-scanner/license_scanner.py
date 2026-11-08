"""License scanner: k-gram fingerprint comparison against a reference corpus."""

import hashlib
import importlib.util
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRIPLE_DQ_RE = re.compile(r'""".*?"""', re.DOTALL)
_TRIPLE_SQ_RE = re.compile(r"'''.*?'''", re.DOTALL)
_LINE_COMMENT_SLASH_RE = re.compile(r"//.*?$", re.MULTILINE)
_LINE_COMMENT_HASH_RE = re.compile(r"#.*?$", re.MULTILINE)

_WINDOW_SIZE = 9
_WINDOW_SEP = "\x1f"

_VALID_RISK_TIERS = {"high", "medium", "low"}

_CorpusInfo = namedtuple(
    "_CorpusInfo", ["status", "reason", "entries", "block_threshold", "gate_version"]
)


class _UsageError(Exception):
    pass


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Dependency loading (cache-manager)
# ---------------------------------------------------------------------------

def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _find_dependency_dir(repo_root: Path, dep_slug: str):
    candidate = Path(repo_root) / "gen" / dep_slug
    if candidate.exists():
        return candidate
    fallback = _tool_root() / "gen" / dep_slug
    if fallback.exists():
        return fallback
    return None


def _load_module_from_dir(dep_dir: Path, module_name: str):
    pkg_init = dep_dir / module_name / "__init__.py"
    flat_file = dep_dir / f"{module_name}.py"
    if pkg_init.exists():
        spec = importlib.util.spec_from_file_location(
            module_name, pkg_init, submodule_search_locations=[str(pkg_init.parent)]
        )
    elif flat_file.exists():
        spec = importlib.util.spec_from_file_location(module_name, flat_file)
    else:
        return None
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _try_load_cache_manager(repo_root: Path):
    try:
        dep_dir = _find_dependency_dir(Path(repo_root), "cache-manager")
        if dep_dir is None:
            return None
        return _load_module_from_dir(dep_dir, "cache_manager")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Reference corpus loading / validation
# ---------------------------------------------------------------------------

def _validate_corpus(data):
    if not isinstance(data, dict):
        return False, None, None, None
    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        return False, None, None, None

    corpus_version = data.get("corpus_version", 0)
    if "corpus_version" in data:
        if isinstance(corpus_version, bool) or not isinstance(corpus_version, int) or corpus_version < 0:
            return False, None, None, None

    block_threshold = data.get("block_threshold", 0.70)
    if "block_threshold" in data:
        if isinstance(block_threshold, bool) or not isinstance(block_threshold, (int, float)):
            return False, None, None, None
        if not (0 < block_threshold <= 1):
            return False, None, None, None

    if len(raw_entries) == 0:
        return False, None, None, None

    entries = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            return False, None, None, None
        hashes = raw_entry.get("hashes")
        if not isinstance(hashes, list) or not all(isinstance(h, str) for h in hashes):
            return False, None, None, None
        risk_tier = raw_entry.get("risk_tier")
        if risk_tier not in _VALID_RISK_TIERS:
            return False, None, None, None
        entries.append(
            {
                "reference_id": raw_entry.get("reference_id"),
                "license_family": raw_entry.get("license_family"),
                "risk_tier": risk_tier,
                "hashes_set": set(hashes),
            }
        )

    return True, corpus_version, block_threshold, entries


def _load_corpus(repo_root: Path) -> _CorpusInfo:
    raw_path = os.environ.get("VAR_LICENSE_CORPUS_PATH", "").strip()
    if not raw_path:
        return _CorpusInfo(
            "no-reference-corpus",
            "no-reference-corpus",
            [],
            None,
            "license_scanner@4.0.0-no-reference-corpus",
        )

    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(repo_root) / path

    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return _CorpusInfo(
            "corpus-unreadable",
            "corpus-unreadable",
            [],
            None,
            "license_scanner@4.0.0-corpus-unreadable",
        )

    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _CorpusInfo(
            "corpus-invalid",
            "corpus-invalid",
            [],
            None,
            "license_scanner@4.0.0-corpus-invalid",
        )

    valid, corpus_version, block_threshold, entries = _validate_corpus(data)
    if not valid:
        return _CorpusInfo(
            "corpus-invalid",
            "corpus-invalid",
            [],
            None,
            "license_scanner@4.0.0-corpus-invalid",
        )

    digest = hashlib.sha256(raw_bytes).hexdigest()[:12]
    gate_version_str = f"license_scanner@4.0.{corpus_version}+{digest}"
    return _CorpusInfo("usable", None, entries, block_threshold, gate_version_str)


# ---------------------------------------------------------------------------
# K-gram fingerprinting
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    text = _BLOCK_COMMENT_RE.sub("", text)
    text = _TRIPLE_DQ_RE.sub("", text)
    text = _TRIPLE_SQ_RE.sub("", text)
    text = _LINE_COMMENT_SLASH_RE.sub("", text)
    text = _LINE_COMMENT_HASH_RE.sub("", text)
    return text


def _tokenize(text: str):
    return [t.lower() for t in _IDENT_RE.findall(text)]


def _window_hashes_for_tokens(tokens):
    hashes = set()
    n = len(tokens)
    for i in range(n - _WINDOW_SIZE + 1):
        window = tokens[i : i + _WINDOW_SIZE]
        joined = _WINDOW_SEP.join(window)
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return hashes


def _component_window_hashes(component_dir: Path):
    all_hashes = set()
    if component_dir.exists():
        for path in sorted(component_dir.rglob("*")):
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                tokens = _tokenize(_normalize(text))
                all_hashes |= _window_hashes_for_tokens(tokens)
    return all_hashes


def _compute_gen_content_hash(component_dir: Path) -> str:
    h = hashlib.sha256()
    if component_dir.exists():
        for path in sorted(component_dir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(component_dir).as_posix()
                h.update(rel.encode("utf-8"))
                h.update(b"\x00")
                try:
                    h.update(path.read_bytes())
                except OSError:
                    pass
                h.update(b"\x00")
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Webhook notification
# ---------------------------------------------------------------------------

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
        if isinstance(e.reason, socket.timeout):
            return {"category": "timeout", "message": str(e)}
        return {"category": "network", "message": str(e)}
    except Exception as e:
        return {"category": "network", "message": str(e)}


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------

def _do_scan(component_id: str, component_dir: Path, corpus_info: _CorpusInfo) -> dict:
    if corpus_info.status != "usable":
        evaluated = False
        reason = corpus_info.reason
        similarity_score = None
        block_threshold = None
        matches = []
        blocked = reason != "no-reference-corpus"
    else:
        evaluated = True
        reason = None
        component_hashes = _component_window_hashes(component_dir)
        scored = []
        for entry in corpus_info.entries:
            if component_hashes:
                overlap = component_hashes & entry["hashes_set"]
                score = len(overlap) / len(component_hashes)
            else:
                score = 0.0
            scored.append((score, entry))

        similarity_score = max((s for s, _ in scored), default=0.0)
        block_threshold = corpus_info.block_threshold
        blocked = similarity_score >= block_threshold
        matches = [
            {
                "reference_id": entry["reference_id"],
                "license_family": entry["license_family"],
                "risk_tier": entry["risk_tier"],
                "score": score,
            }
            for score, entry in sorted(scored, key=lambda t: -t[0])
            if score > 0.0
        ]

    high_risk_match = any(m["risk_tier"] == "high" for m in matches)
    due = blocked or high_risk_match
    webhook_url = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL", "").strip()

    notified = False
    notification_delivery_error = None
    if due and webhook_url:
        notified = True
        notification_delivery_error = _send_webhook(
            webhook_url,
            {
                "component_id": component_id,
                "gate_version": corpus_info.gate_version,
                "evaluated": evaluated,
                "reason": reason,
                "similarity_score": similarity_score,
                "block_threshold": block_threshold,
                "blocked": blocked,
                "matches": matches,
            },
        )

    return {
        "component_id": component_id,
        "gate_version": corpus_info.gate_version,
        "evaluated": evaluated,
        "reason": reason,
        "similarity_score": similarity_score,
        "block_threshold": block_threshold,
        "blocked": blocked,
        "matches": matches,
        "notified": notified,
        "notification_delivery_error": notification_delivery_error,
        "cache_hit": False,
    }


def _component_dir_for(component_id: str, repo_root: Path) -> Path:
    slug = component_id[len("comp-") :] if component_id.startswith("comp-") else component_id
    return Path(repo_root) / "gen" / slug


def scan(component_id: str, repo_root) -> dict:
    repo_root = Path(repo_root)
    component_dir = _component_dir_for(component_id, repo_root)

    corpus_info = _load_corpus(repo_root)
    content_hash = _compute_gen_content_hash(component_dir)

    cache_manager_mod = _try_load_cache_manager(repo_root)
    cache_key = None

    if cache_manager_mod is not None:
        try:
            cache_key = cache_manager_mod.CacheKey(
                spec_bundle_hash=content_hash,
                gate_inputs_hash=content_hash,
                gate_version=corpus_info.gate_version,
                model_pin="n/a",
            )
            cached = cache_manager_mod.get(cache_key, repo_root=repo_root)
            payload = _get(cached, "payload")
            if payload is not None:
                result = dict(payload)
                result["cache_hit"] = True
                return result
        except Exception:
            pass

    result = _do_scan(component_id, component_dir, corpus_info)

    if cache_manager_mod is not None and cache_key is not None:
        try:
            cached_result = cache_manager_mod.CachedResult(
                gate_type="license_scanner",
                payload=dict(result),
                stored_at=_now_iso(),
            )
            cache_manager_mod.put(cache_key, cached_result, repo_root=repo_root)
        except Exception:
            pass

    return result


def gate_version(repo_root) -> str:
    corpus_info = _load_corpus(Path(repo_root))
    return corpus_info.gate_version


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv):
    component_id = None
    repo_root = "."
    fmt = "text"
    args = list(argv)
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--repo-root" or arg.startswith("--repo-root="):
            if "=" in arg:
                repo_root = arg.split("=", 1)[1]
                i += 1
            else:
                if i + 1 >= len(args):
                    raise _UsageError("--repo-root requires a value")
                repo_root = args[i + 1]
                i += 2
        elif arg == "--format" or arg.startswith("--format="):
            if "=" in arg:
                fmt = arg.split("=", 1)[1]
                i += 1
            else:
                if i + 1 >= len(args):
                    raise _UsageError("--format requires a value")
                fmt = args[i + 1]
                i += 2
        elif arg.startswith("-"):
            raise _UsageError(f"unknown argument: {arg}")
        else:
            if component_id is not None:
                raise _UsageError(f"unexpected argument: {arg}")
            component_id = arg
            i += 1

    if component_id is None:
        raise _UsageError("missing <component-id>")
    if fmt not in ("json", "text"):
        raise _UsageError(f"invalid --format: {fmt}")

    return component_id, repo_root, fmt


def _print_text(result: dict) -> None:
    print(f"component: {result['component_id']}")
    print(f"gate_version: {result['gate_version']}")
    print(f"similarity_score: {result['similarity_score']}")
    print(f"blocked: {result['blocked']}")
    if not result["evaluated"]:
        hint = ""
        if result["reason"] == "no-reference-corpus":
            hint = " (set VAR_LICENSE_CORPUS_PATH)"
        print(f"NOT EVALUATED: {result['reason']}{hint}")


def main(argv) -> int:
    try:
        component_id, repo_root, fmt = _parse_args(argv)
    except _UsageError as e:
        print(f"usage error: {e}", file=sys.stderr)
        return 2

    result = scan(component_id, Path(repo_root))

    if fmt == "json":
        print(json.dumps(result))
    else:
        _print_text(result)

    return 1 if result["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))