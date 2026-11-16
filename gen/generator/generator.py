"""Generator: one single-shot model call producing gen/<component>/ from a SpecBundle."""

import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

GATE_VERSION = "generator@3.0.0"
PROMPT_VERSION = "v11"

_GATE_TYPE = GATE_VERSION.split("@", 1)[0]

_RESULT_FIELDS = (
    "component_id",
    "spec_bundle_hash",
    "model",
    "prompt_version",
    "cache_hit",
    "files",
    "model_call_error",
    "refused",
    "retry_feedback",
    "mode",
    "transcript_sha256",
    "turns",
    "tool_calls",
    "isolation",
)

_SEALED_RE = re.compile(r"^sealed:\s*true\s*$", re.M)

PROMPT_TEMPLATE = """You are generating the complete source for one component of a spec-driven pipeline, to be written under gen/{slug}/, from the spec bundle sections below.

PROMPT_VERSION: {prompt_version}

Rules:
- Construct your answer from exactly the sections given below. Never invent or assume anything about this component's "real" prior implementation.
- Implement exactly what the spec requires and nothing more: no validation, fallback, option, or error path that the SPEC, INTERFACE and CONSTRAINTS sections do not call for. Every branch you write must be one the spec's acceptance criteria can reach; code beyond the spec is untested and is rejected by mutation testing.
- Lay out your output as either a flat {module}.py module or a {module}/ package (with __init__.py) directly under gen/{slug}/ -- never a deeper layout (e.g. a src/ subdirectory) and never a separately-installed distribution.
- If your own generated code dynamically loads a dependency module at runtime -- by any means: a bare `import <module_name>` statement, a `sys.modules` lookup keyed on that bare name, or resolving a file path relative to your own `__file__` -- it MUST instead resolve that dependency from the `repo_root` parameter your own function was actually called with, joined to the module path the dependency usage gives for it: `gen/<dep-slug>/` for an ordinary dependency, or a sealed dependency's own `source_path`, holding `<module_name>.py` (flat) or `<module_name>/__init__.py` (package). Only when that directory does not exist under `repo_root`, fall back to the same path under the tool root: the parent of the nearest directory named `gen` above your own module's `__file__`. `repo_root` always wins when it has the directory. Never trust a bare-named `sys.modules` entry.
- If your own generated code loads a module from a file path at runtime, you MUST register the loaded module object in sys.modules under its load-time name BEFORE executing its code (exec_module) -- never after, never omitted.
- Any value you read from a dependency call -- including the dependency function's own top-level return value, not only values nested within it -- MUST use dual dict-or-attribute access, never a bare `.attr` access alone. A dependency may legitimately return either a dict or an object.
- Output only the files that belong under gen/{slug}/ -- no explanation, no commentary outside of file content itself.

Reply format: wrap each file's content exactly as a line holding the begin marker below (with the file's path relative to gen/{slug}/ in place of the placeholder), then the complete, exact file content, then a line holding the end marker below. After the last file, end your reply with a line holding the end-of-reply marker below. The nonce {nonce} is unique to this call; use it on every marker. Text outside the blocks is ignored.

-----BEGIN FILE {nonce}: <path relative to gen/{slug}/>-----
<the complete, exact file content, verbatim>
-----END FILE {nonce}-----

-----END REPLY {nonce}-----

## component_id
{component_id}
"""


@dataclass
class GenerationResult:
    component_id: str = ""
    spec_bundle_hash: str = ""
    model: str = ""
    prompt_version: str = PROMPT_VERSION
    cache_hit: bool = False
    files: dict = field(default_factory=dict)
    model_call_error: Optional[dict] = None
    refused: Optional[str] = None
    retry_feedback: Optional[list] = None
    mode: str = "single"
    transcript_sha256: Optional[str] = None
    turns: int = 1
    tool_calls: int = 0
    isolation: Optional[str] = None


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _module_name(component_id):
    return _slug(component_id).replace("-", "_")


def _root(repo_root):
    return Path(repo_root or Path.cwd())


def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load_dependency(module_name, dep_slug, root):
    base = root / "gen" / dep_slug
    if not base.is_dir():
        base = _tool_root() / "gen" / dep_slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _cache_key(cache_manager, spec_bundle_hash, retry_feedback, model):
    digest = hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash="sha256:" + digest,
        gate_version=GATE_VERSION,
        model_pin=model,
    )


def _strip_prefix(slug, path):
    for prefix in (f"gen/{slug}/", f"{slug}/"):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def _join_entries(entries):
    return "\n\n".join(f"### {name}\n{text}" for name, text in entries.items())


def check_write_allowed(bundle, repo_root=None):
    root = _root(repo_root)
    slug = _slug(_field(bundle, "component_id"))
    component_md = root / "specs" / "components" / slug / "component.md"
    if component_md.is_file() and _SEALED_RE.search(
        component_md.read_text(encoding="utf-8").split("\n---", 1)[0]
    ):
        return "sealed-component"
    overrides = root / "gen" / slug / ".overrides.json"
    if overrides.is_file() and json.loads(overrides.read_text(encoding="utf-8")):
        return "pinned-override"
    return None


def render_prompt_sections(bundle, retry_feedback=None):
    sections = [
        ("SPEC", _field(bundle, "spec", "")),
        ("INTERFACE", _field(bundle, "interface", "")),
        ("CONSTRAINTS", _field(bundle, "constraints", "")),
        ("DEPENDENCY INTERFACES", _join_entries(_field(bundle, "dependency_interfaces", {}))),
        ("VARS", _join_entries(_field(bundle, "vars", {}))),
        ("GLOSSARY", _field(bundle, "glossary", "")),
    ]
    usage = {
        dep: text
        for dep, text in _field(bundle, "dependency_usage", {}).items()
        if text
    }
    if usage:
        sections.append((
            "DEPENDENCY USAGE (real, importable symbols from each dependency's actual "
            "current code -- distinct from DEPENDENCY INTERFACES, not acceptance-test content)",
            _join_entries(usage),
        ))
    hint_code = _field(bundle, "hint_code")
    if hint_code is not None:
        sections.append((
            "HINT CODE (the component's existing gen/<component>/ files -- "
            "context only, NOT part of the spec)",
            _join_entries(hint_code),
        ))
    if retry_feedback:
        sections.append((
            "RETRY FEEDBACK (requirement ids a prior attempt failed to satisfy -- ids only)",
            "\n".join(retry_feedback),
        ))
    return sections


def write_files(component_id, files, repo_root=None):
    slug = _slug(component_id)
    target = _root(repo_root) / "gen" / slug
    for rel, content in files.items():
        path = target / _strip_prefix(slug, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _render_prompt(bundle, retry_feedback, nonce):
    component_id = _field(bundle, "component_id")
    header = PROMPT_TEMPLATE.format(
        slug=_slug(component_id),
        module=_module_name(component_id),
        prompt_version=PROMPT_VERSION,
        nonce=nonce,
        component_id=component_id,
    )
    body = "\n\n".join(
        f"## {title}\n{text}" for title, text in render_prompt_sections(bundle, retry_feedback)
    )
    return header + "\n" + body + "\n"


def _parse_reply(text, nonce, component_id):
    """Return (files, model_call_error)."""
    slug = _slug(component_id)
    module = _module_name(component_id)
    begin_re = re.compile(rf"^-----BEGIN FILE {nonce}: (.+)-----$")
    end_file = f"-----END FILE {nonce}-----"
    end_reply = f"-----END REPLY {nonce}-----"
    files = {}
    path = None
    buf = []
    saw_end_reply = False
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if path is None:
            match = begin_re.match(stripped)
            if match:
                path = match.group(1)
                buf = []
            elif stripped == end_reply:
                saw_end_reply = True
        elif stripped == end_file:
            files[_strip_prefix(slug, path)] = "".join(buf)
            path = None
        else:
            buf.append(line)
    if not files and path is None:
        return {}, {"category": "empty_response", "message": "the model reply contained no files"}
    if path is not None:
        return {}, {
            "category": "truncated_response",
            "message": f"no END FILE marker after the BEGIN FILE line for {path}",
        }
    if not saw_end_reply:
        return {}, {
            "category": "truncated_response",
            "message": "the reply's end marker is missing (no END REPLY line)",
        }
    if f"{module}.py" not in files and f"{module}/__init__.py" not in files:
        return {}, {
            "category": "missing_module",
            "message": f"the reply holds neither {module}.py nor {module}/__init__.py",
        }
    return files, None


def _result(bundle, model, retry_feedback, hint, **values):
    result = GenerationResult(
        component_id=_field(bundle, "component_id"),
        spec_bundle_hash=_field(bundle, "spec_bundle_hash"),
        model=model,
        prompt_version=PROMPT_VERSION,
        retry_feedback=retry_feedback,
        **values,
    )
    result._hint_mode = hint
    return result


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    root = _root(repo_root)
    component_id = _field(bundle, "component_id")
    hint = _field(bundle, "hint_code") is not None

    refused = check_write_allowed(bundle, root)
    if refused:
        return _result(bundle, model, retry_feedback, hint, refused=refused)

    cache_manager = _load_dependency("cache_manager", "cache-manager", root)
    key = _cache_key(cache_manager, _field(bundle, "spec_bundle_hash"), retry_feedback, model)
    hit = cache_manager.get(key, repo_root=root)
    if not isinstance(hit, cache_manager.Miss):
        files = dict(_field(_field(hit, "payload"), "files"))
        if not hint:
            write_files(component_id, files, root)
        return _result(bundle, model, retry_feedback, hint, cache_hit=True, files=files)

    llm_endpoint = _load_dependency("llm_endpoint", "llm-endpoint", root)
    nonce = uuid.uuid4().hex
    response = llm_endpoint.complete(
        _render_prompt(bundle, retry_feedback, nonce), model, backend=llm_backend
    )
    error = _field(response, "model_call_error")
    if error:
        return _result(
            bundle, model, retry_feedback, hint,
            model_call_error={
                "category": _field(error, "category"),
                "message": _field(error, "message"),
            },
        )

    files, error = _parse_reply(_field(response, "text"), nonce, component_id)
    if error:
        return _result(bundle, model, retry_feedback, hint, model_call_error=error)

    if not hint:
        write_files(component_id, files, root)
    return _result(bundle, model, retry_feedback, hint, files=files)


def commit_cache(result, repo_root=None):
    if (
        not _field(result, "files")
        or _field(result, "model_call_error")
        or _field(result, "refused")
        or _field(result, "_hint_mode", False)
    ):
        return
    root = _root(repo_root)
    cache_manager = _load_dependency("cache_manager", "cache-manager", root)
    key = _cache_key(
        cache_manager,
        _field(result, "spec_bundle_hash"),
        _field(result, "retry_feedback"),
        _field(result, "model"),
    )
    payload = {name: _field(result, name) for name in _RESULT_FIELDS}
    cache_manager.put(
        key,
        cache_manager.CachedResult(
            gate_type=_GATE_TYPE,
            payload=payload,
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=root,
    )
