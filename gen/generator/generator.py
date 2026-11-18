"""Generator: one cold (or hint-informed) candidate per call from a SpecBundle."""

import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "generator@3.0.0"
PROMPT_VERSION = "v11"


@dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool = False
    files: dict = field(default_factory=dict)
    model_call_error: object = None
    refused: object = None
    retry_feedback: object = None
    mode: str = "single"
    transcript_sha256: object = None
    turns: int = 1
    tool_calls: int = 0
    isolation: object = None


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _module_name(component_id):
    return _slug(component_id).replace("-", "_")


def _root(repo_root):
    return Path(repo_root) if repo_root is not None else Path.cwd()


def _load_dependency(module_name, slug, repo_root):
    base = _root(repo_root) / "gen" / slug
    if not base.is_dir():
        gen_dir = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
        base = gen_dir.parent / "gen" / slug
    path = base / f"{module_name}.py"
    package = not path.is_file()
    if package:
        path = base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
        submodule_search_locations=[str(path.parent)] if package else None,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _gate_inputs_hash(retry_feedback):
    data = json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _cache_key(cache_manager, spec_bundle_hash, retry_feedback, model):
    return cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=_gate_inputs_hash(retry_feedback),
        gate_version=GATE_VERSION,
        model_pin=model,
    )


def _mapping(value):
    value = value or {}
    if not value:
        return "(none)"
    return "\n\n".join(f"### {key}\n{value[key]}" for key in sorted(value))


def render_prompt_sections(bundle, retry_feedback=None):
    sections = [
        ("SPEC", _field(bundle, "spec", "")),
        ("INTERFACE", _field(bundle, "interface", "")),
        ("CONSTRAINTS", _field(bundle, "constraints", "")),
        ("DEPENDENCY INTERFACES", _mapping(_field(bundle, "dependency_interfaces", {}))),
        ("DEPENDENCY CONTEXT", _mapping(_field(bundle, "dependency_context", {}))),
        ("VARS", _mapping(_field(bundle, "vars", {}))),
        ("GLOSSARY", _field(bundle, "glossary", "")),
    ]
    usage = _field(bundle, "dependency_usage", {}) or {}
    non_empty = {key: value for key, value in usage.items() if value}
    if non_empty:
        sections.append((
            "DEPENDENCY USAGE",
            "Real, importable symbols from each dependency's actual current code -- "
            "distinct from DEPENDENCY INTERFACES, not acceptance-test content.\n\n"
            + _mapping(non_empty),
        ))
    hint_code = _field(bundle, "hint_code")
    if hint_code is not None:
        blocks = [
            f"--- hint file: {path} ---\n{hint_code[path]}\n--- end hint file: {path} ---"
            for path in sorted(hint_code)
        ]
        sections.append((
            "HINT_CODE",
            "The component's existing code, given as context only -- it is not part "
            "of the spec above.\n\n" + "\n\n".join(blocks),
        ))
    if retry_feedback:
        sections.append((
            "RETRY_FEEDBACK",
            "A prior attempt did not satisfy these requirement ids:\n"
            + "\n".join(f"- {rid}" for rid in retry_feedback),
        ))
    return sections


def _render_prompt(bundle, retry_feedback, nonce):
    component_id = _field(bundle, "component_id")
    slug = _slug(component_id)
    module = _module_name(component_id)
    head = (
        f"You are generating the complete source for one component of a spec-driven "
        f"pipeline, to be written under gen/{slug}/, from the spec bundle sections below.\n"
        f"\n"
        f"PROMPT_VERSION: {PROMPT_VERSION}\n"
        f"\n"
        f"Reply format: wrap each file's content exactly as a line holding the begin marker "
        f"below (with the file's path relative to gen/{slug}/ in place of the placeholder), "
        f"then the complete, exact file content, then a line holding the end marker below. "
        f"After the last file, end your reply with a line holding the end-of-reply marker "
        f"below. Text outside the blocks is ignored.\n"
        f"\n"
        f"-----BEGIN FILE {nonce}: <path relative to gen/{slug}/>-----\n"
        f"<the complete, exact file content, verbatim>\n"
        f"-----END FILE {nonce}-----\n"
        f"\n"
        f"-----END REPLY {nonce}-----\n"
        f"\n"
        f"Rules:\n"
        f"- Construct your answer from exactly the sections given below.\n"
        f"- Implement exactly what the spec requires and nothing more: no validation, "
        f"fallback, option, or error path that the SPEC, INTERFACE and CONSTRAINTS sections "
        f"do not call for. A branch no acceptance criterion reaches is untested and is "
        f"rejected by mutation testing.\n"
        f"- Lay out your output as either a flat {module}.py module or a {module}/ package "
        f"(with __init__.py) directly under gen/{slug}/ -- never a deeper layout (e.g. a "
        f"src/ subdirectory) and never a separately-installed distribution.\n"
        f"- If your own generated code dynamically loads a dependency module at runtime -- "
        f"a bare `import <module_name>`, a `sys.modules` lookup keyed on that bare name, or "
        f"a path relative to your own `__file__` -- it MUST instead resolve that dependency "
        f"from the `repo_root` parameter your own function was actually called with, joined "
        f"to the module path the dependency usage gives for it: `gen/<dep-slug>/`, or a "
        f"sealed dependency's own `source_path`. Only when that directory does not exist "
        f"under `repo_root`, fall back to the same path under the tool root: the parent of "
        f"the nearest directory named `gen` above your own module's `__file__`. Never trust "
        f"a stale bare-named `sys.modules` entry.\n"
        f"- If your own generated code loads a module from a file path at runtime, register "
        f"the loaded module in sys.modules under its load-time name BEFORE exec_module.\n"
        f"- Any value you read from a dependency call -- including the dependency function's "
        f"own top-level return value -- MUST use dual dict-or-attribute access, never a bare "
        f"`.attr` access alone: a dependency may return either a dict or an object.\n"
        f"\n"
        f"## component_id\n"
        f"{component_id}"
    )
    body = "\n\n".join(
        f"## {title}\n{text}" for title, text in render_prompt_sections(bundle, retry_feedback)
    )
    return head + "\n\n" + body


def check_write_allowed(bundle, repo_root=None):
    root = _root(repo_root)
    slug = _slug(_field(bundle, "component_id"))
    component_md = root / "specs" / "components" / slug / "component.md"
    if component_md.is_file() and re.search(
        r"^sealed:\s*true\s*$", component_md.read_text(encoding="utf-8"), re.M
    ):
        return "sealed-component"
    overrides = root / "gen" / slug / ".overrides.json"
    if overrides.is_file() and json.loads(overrides.read_text(encoding="utf-8")):
        return "pinned-override"
    return None


def _strip_prefix(slug, path):
    for prefix in (f"gen/{slug}/", f"{slug}/"):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def write_files(component_id, files, repo_root=None):
    slug = _slug(component_id)
    target = _root(repo_root) / "gen" / slug
    for path, content in files.items():
        dest = target / _strip_prefix(slug, path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _empty_response(text):
    if not text.strip():
        message = "the model reply was empty"
    else:
        message = "the model reply contained no files; it began:\n" + text[:4000]
        if len(text) > 4000:
            message += f"\n[{len(text) - 4000} more characters]"
    return {"category": "empty_response", "message": message}


def _parse_reply(text, nonce, component_id):
    """Return (files, error)."""
    begin = re.compile(r"^-----BEGIN FILE " + nonce + r": (.*)-----$")
    end_file = f"-----END FILE {nonce}-----"
    end_reply = f"-----END REPLY {nonce}-----"
    slug = _slug(component_id)
    lines = text.splitlines(keepends=True)
    stripped = [line.rstrip("\r\n") for line in lines]
    if not any(begin.match(line) for line in stripped):
        return None, _empty_response(text)
    files = {}
    i = 0
    while i < len(lines):
        match = begin.match(stripped[i])
        if not match:
            i += 1
            continue
        path = match.group(1)
        j = i + 1
        while j < len(lines) and stripped[j] != end_file:
            j += 1
        if j == len(lines):
            return None, {
                "category": "truncated_response",
                "message": f"no END FILE marker for {path}",
            }
        files[_strip_prefix(slug, path)] = "".join(lines[i + 1:j])
        i = j + 1
    if end_reply not in stripped:
        return None, {
            "category": "truncated_response",
            "message": "the reply's END REPLY end marker is missing",
        }
    module = _module_name(component_id)
    if f"{module}.py" not in files and f"{module}/__init__.py" not in files:
        return None, {
            "category": "missing_module",
            "message": f"the reply holds neither {module}.py nor {module}/__init__.py",
        }
    return files, None


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = _field(bundle, "component_id")
    spec_bundle_hash = _field(bundle, "spec_bundle_hash")
    hint = _field(bundle, "hint_code") is not None

    def result(**kwargs):
        res = GenerationResult(
            component_id=component_id,
            spec_bundle_hash=spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            retry_feedback=retry_feedback,
            **kwargs,
        )
        res._hint = hint
        return res

    refused = check_write_allowed(bundle, repo_root)
    if refused is not None:
        return result(refused=refused)

    cache_manager = _load_dependency("cache_manager", "cache-manager", repo_root)
    key = _cache_key(cache_manager, spec_bundle_hash, retry_feedback, model)
    cached = cache_manager.get(key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        files = dict(_field(_field(cached, "payload"), "files"))
        if not hint:
            write_files(component_id, files, repo_root)
        return result(cache_hit=True, files=files)

    llm_endpoint = _load_dependency("llm_endpoint", "llm-endpoint", repo_root)
    nonce = uuid.uuid4().hex
    prompt = _render_prompt(bundle, retry_feedback, nonce)
    response = llm_endpoint.complete(prompt, model, backend=llm_backend)
    error = _field(response, "model_call_error")
    if error:
        return result(model_call_error={
            "category": _field(error, "category"),
            "message": _field(error, "message"),
        })

    files, error = _parse_reply(_field(response, "text"), nonce, component_id)
    if error is not None:
        return result(model_call_error=error)
    if not hint:
        write_files(component_id, files, repo_root)
    return result(files=files)


def commit_cache(result, repo_root=None):
    files = _field(result, "files")
    if (
        not files
        or _field(result, "model_call_error")
        or _field(result, "refused")
        or getattr(result, "_hint", False)
    ):
        return
    cache_manager = _load_dependency("cache_manager", "cache-manager", repo_root)
    key = _cache_key(
        cache_manager,
        _field(result, "spec_bundle_hash"),
        _field(result, "retry_feedback"),
        _field(result, "model"),
    )
    payload = {
        "component_id": _field(result, "component_id"),
        "spec_bundle_hash": _field(result, "spec_bundle_hash"),
        "model": _field(result, "model"),
        "prompt_version": _field(result, "prompt_version"),
        "files": dict(files),
    }
    cache_manager.put(
        key,
        cache_manager.CachedResult(
            gate_type="generator", payload=payload, stored_at=cache_manager.now_iso()
        ),
        repo_root=repo_root,
    )
