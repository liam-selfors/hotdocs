"""Generator: one cold (or hint-mode) model call producing gen/<component>/ from a SpecBundle."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import uuid
from collections.abc import Mapping
from pathlib import Path

GATE_VERSION = "generator@3.2.0"
PROMPT_VERSION = "v12"


@dataclasses.dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str = PROMPT_VERSION
    cache_hit: bool = False
    files: dict = dataclasses.field(default_factory=dict)
    model_call_error: dict | None = None
    refused: str | None = None
    retry_feedback: list | None = None
    mode: str = "single"
    transcript_sha256: str | None = None
    turns: int = 1
    tool_calls: int = 0
    isolation: object = None


_FIELDS = [f.name for f in dataclasses.fields(GenerationResult)]

_DEPENDENCY_USAGE_SENTENCE = (
    "Real, importable symbols from each dependency's actual current code -- "
    "distinct from DEPENDENCY INTERFACES, not acceptance-test content."
)
_HINT_CODE_SENTENCE = (
    "The component's current generated code, given as context only -- "
    "distinct from the spec bundle sections above."
)
_RETRY_FEEDBACK_SENTENCE = (
    "Requirement ids a previous attempt failed to satisfy -- "
    "distinct from the spec bundle sections above:"
)


def _get(obj, key):
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _module_name(slug):
    return slug.replace("-", "_")


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load_file(name, path):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
        submodule_search_locations=[str(path.parent)] if path.name == "__init__.py" else None,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dep(dep_slug, module, root):
    directory = root / "gen" / dep_slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / dep_slug
    path = directory / f"{module}.py"
    if not path.is_file():
        path = directory / module / "__init__.py"
    return _load_file(module, path)


def _load_adapter(kind, root):
    relative = Path("gen") / f"kind-{kind}" / f"kind_{kind}.py"
    path = root / relative
    if not path.is_file():
        path = _tool_root() / relative
    if not path.is_file():
        return None
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    return _load_file(f"_generator_kind_{kind}_{digest}", path)


def _frontmatter(root, slug):
    path = root / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return lines[1:lines.index("---", 1)]


def _assets(root, slug):
    for line in _frontmatter(root, slug):
        if line.startswith("assets:"):
            inner = line[line.index("[") + 1:line.index("]")]
            return [
                tuple(part.strip() for part in item.strip().split(":", 1))
                for item in inner.split(",")
                if item.strip()
            ]
    return []


def _strip_prefix(path, slug):
    for prefix in (f"gen/{slug}/", f"{slug}/"):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _cache_key(cm, spec_bundle_hash, retry_feedback, model):
    digest = hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return cm.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash="sha256:" + digest,
        gate_version=GATE_VERSION,
        model_pin=model,
    )


def _result(bundle, model, retry_feedback, *, files=None, error=None, refused=None, cache_hit=False):
    result = GenerationResult(
        component_id=_get(bundle, "component_id"),
        spec_bundle_hash=_get(bundle, "spec_bundle_hash"),
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=cache_hit,
        files=files or {},
        model_call_error=error,
        refused=refused,
        retry_feedback=retry_feedback,
    )
    result._hint_mode = _get(bundle, "hint_code") is not None
    return result


def check_write_allowed(bundle, repo_root: Path = None):
    root = Path(repo_root or ".")
    slug = _slug(_get(bundle, "component_id"))
    if any(re.fullmatch(r"sealed:\s*true", line) for line in _frontmatter(root, slug)):
        return "sealed-component"
    overrides = root / "gen" / slug / ".overrides.json"
    if overrides.is_file() and json.loads(overrides.read_text(encoding="utf-8")):
        return "pinned-override"
    return None


def _mapping(values):
    return "\n\n".join(f"### {key}\n{values[key]}" for key in sorted(values)) or "(none)"


def render_prompt_sections(bundle, retry_feedback: list[str] | None = None):
    sections = [
        ("SPEC", _get(bundle, "spec")),
        ("INTERFACE", _get(bundle, "interface")),
        ("CONSTRAINTS", _get(bundle, "constraints")),
        ("DEPENDENCY INTERFACES", _mapping(_get(bundle, "dependency_interfaces"))),
        ("DEPENDENCY CONTEXT", _mapping(_get(bundle, "dependency_context"))),
        ("VARS", _mapping(_get(bundle, "vars"))),
        ("GLOSSARY", _get(bundle, "glossary")),
    ]
    usage = {key: value for key, value in _get(bundle, "dependency_usage").items() if value}
    if usage:
        sections.append(("DEPENDENCY USAGE", _DEPENDENCY_USAGE_SENTENCE + "\n\n" + _mapping(usage)))
    hint_code = _get(bundle, "hint_code")
    if hint_code is not None:
        blocks = [
            f"--- hint file: {path} ---\n{hint_code[path]}\n--- end hint file: {path} ---"
            for path in sorted(hint_code)
        ]
        sections.append(("HINT_CODE", _HINT_CODE_SENTENCE + "\n\n" + "\n\n".join(blocks)))
    if retry_feedback:
        lines = "\n".join(f"- {rid}" for rid in retry_feedback)
        sections.append(("RETRY_FEEDBACK", _RETRY_FEEDBACK_SENTENCE + "\n" + lines))
    return sections


def _render_prompt(bundle, retry_feedback, nonce, root):
    component_id = _get(bundle, "component_id")
    slug = _slug(component_id)
    module = _module_name(slug)
    asset_paths = ", ".join(f"`{path}`" for _, path in _assets(root, slug)) or "(none)"
    header = f"""You are generating the complete source for one component of a spec-driven pipeline, to be written under gen/{slug}/, from the spec bundle sections below.

PROMPT_VERSION: {PROMPT_VERSION}

Reply format: wrap each file's content exactly as a line holding the begin marker below (with the file's path relative to gen/{slug}/ in place of the placeholder), then the complete, exact file content, then a line holding the end marker below. After the last file, end your reply with a line holding the end-of-reply marker below. Text outside the blocks is ignored.

-----BEGIN FILE {nonce}: <path relative to gen/{slug}/>-----
<the complete, exact file content, verbatim>
-----END FILE {nonce}-----

-----END REPLY {nonce}-----

Rules:
- Construct your answer from exactly the sections given below.
- Implement exactly what the spec requires and nothing more: no validation, fallback, option, or error path that the SPEC, INTERFACE and CONSTRAINTS sections do not call for. A branch no acceptance criterion reaches is untested and is rejected by mutation testing.
- Lay out your output as either a flat {module}.py module or a {module}/ package (with __init__.py) directly under gen/{slug}/ -- never a deeper layout (e.g. a src/ subdirectory) and never a separately-installed distribution.
- Also write each declared asset file: {asset_paths}. Write no other non-.py file.
- If your own generated code dynamically loads a dependency module at runtime -- a bare `import <module_name>`, a `sys.modules` lookup keyed on that bare name, or a path relative to your own `__file__` -- it MUST instead resolve that dependency from the `repo_root` parameter your own function was actually called with, joined to the module path the dependency usage gives for it: `gen/<dep-slug>/`, or a sealed dependency's own `source_path`. Only when that directory does not exist under `repo_root`, fall back to the same path under the tool root: the parent of the nearest directory named `gen` above your own module's `__file__`. Never trust a stale bare-named `sys.modules` entry.
- If your own generated code loads a module from a file path at runtime, register the loaded module in sys.modules under its load-time name BEFORE exec_module.
- Any value you read from a dependency call -- including the dependency function's own top-level return value -- MUST use dual dict-or-attribute access, never a bare `.attr` access alone: a dependency may return either a dict or an object.

## component_id
{component_id}"""
    body = "\n\n".join(f"## {title}\n{text}" for title, text in render_prompt_sections(bundle, retry_feedback))
    return header + "\n\n" + body


def _empty_message(text):
    if not text.strip():
        return "the model reply was empty"
    message = "the model reply contained no files; it began:\n" + text[:4000]
    if len(text) > 4000:
        message += f"\n[{len(text) - 4000} more characters]"
    return message


def _parse_reply(text, nonce, slug):
    begin = re.compile(r"-----BEGIN FILE " + nonce + r": (.+)-----")
    end_file = f"-----END FILE {nonce}-----"
    end_reply = f"-----END REPLY {nonce}-----"
    lines = text.splitlines(keepends=True)
    stripped = [line.strip() for line in lines]
    files = {}
    i = 0
    while i < len(lines):
        match = begin.fullmatch(stripped[i])
        if not match:
            i += 1
            continue
        path = match.group(1).strip()
        end = next((k for k in range(i + 1, len(lines)) if stripped[k] == end_file), None)
        if end is None:
            return {}, {
                "category": "truncated_response",
                "message": f"the model reply was truncated: file {path} has no end marker",
            }
        files[_strip_prefix(path, slug)] = "".join(lines[i + 1:end])
        i = end + 1
    if not files:
        return {}, {"category": "empty_response", "message": _empty_message(text)}
    if end_reply not in stripped:
        return {}, {
            "category": "truncated_response",
            "message": f"the model reply was truncated: the end marker {end_reply} is missing",
        }
    module = _module_name(slug)
    if f"{module}.py" not in files and f"{module}/__init__.py" not in files:
        return {}, {
            "category": "missing_module",
            "message": f"the model reply wrote neither {module}.py nor {module}/__init__.py",
        }
    return files, None


def write_files(component_id: str, files: dict, repo_root: Path = None) -> None:
    target = Path(repo_root or ".") / "gen" / _slug(component_id)
    for path, content in files.items():
        _write(target / path, content)


def check_assets(component_id: str, files: dict, repo_root: Path = None):
    root = Path(repo_root or ".")
    slug = _slug(component_id)
    python = _load_adapter("python", root)
    if python is None:
        return "environment", ["unknown asset kind: python"]
    assets = _assets(root, slug)
    declared = [path for _, path in assets]
    missing = [f"missing asset: {path}" for path in declared if path not in files]
    if missing:
        return "missing_asset", missing
    undeclared = [
        f"undeclared file: {path}"
        for path in sorted(files)
        if not path.endswith(".py") and path not in declared
    ]
    if undeclared:
        return "malformed_layout", undeclared
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        messages = []
        for kind, path in assets:
            asset_file = tmp / "assets" / path
            _write(asset_file, files[path])
            messages += [f"{path}: {m}" for m in _load_adapter(kind, root).layout_errors(asset_file)]
        if messages:
            return "malformed_layout", messages
        code = tmp / "code" / slug
        code.mkdir(parents=True)
        for path, content in files.items():
            if path.endswith(".py"):
                _write(code / path, content)
        messages = list(python.layout_errors(code))
    if messages:
        return "malformed_layout", messages
    return None, []


def check_asset_environment(component_id: str, repo_root: Path = None):
    root = Path(repo_root or ".")
    kinds = list(dict.fromkeys(["python"] + [kind for kind, _ in _assets(root, _slug(component_id))]))
    for kind in kinds:
        adapter = _load_adapter(kind, root)
        if adapter is None:
            return "environment", [f"unknown asset kind: {kind}"]
        report = adapter.provision(root)
        if not _get(report, "ok"):
            return "environment", [_get(report, "reason")]
    return None, []


def generate(bundle, model: str, retry_feedback: list[str] | None = None, *, repo_root: Path = None, llm_backend=None):
    root = Path(repo_root or ".")
    component_id = _get(bundle, "component_id")
    slug = _slug(component_id)

    reason = check_write_allowed(bundle, repo_root)
    if reason:
        return _result(bundle, model, retry_feedback, refused=reason)

    cm = _load_dep("cache-manager", "cache_manager", root)
    key = _cache_key(cm, _get(bundle, "spec_bundle_hash"), retry_feedback, model)
    hit = cm.get(key, repo_root=repo_root)
    if not isinstance(hit, cm.Miss):
        files = dict(_get(_get(hit, "payload"), "files"))
        return _result(bundle, model, retry_feedback, files=files, cache_hit=True)

    category, messages = check_asset_environment(component_id, repo_root)
    if category:
        return _result(bundle, model, retry_feedback,
                       error={"category": category, "message": "\n".join(messages)})

    nonce = uuid.uuid4().hex
    prompt = _render_prompt(bundle, retry_feedback, nonce, root)
    endpoint = _load_dep("llm-endpoint", "llm_endpoint", root)
    response = endpoint.complete(prompt, model, backend=llm_backend)
    error = _get(response, "model_call_error")
    if error:
        return _result(bundle, model, retry_feedback,
                       error={"category": _get(error, "category"), "message": _get(error, "message")})

    files, error = _parse_reply(_get(response, "text"), nonce, slug)
    if error:
        return _result(bundle, model, retry_feedback, error=error)

    category, messages = check_assets(component_id, files, repo_root)
    if category:
        return _result(bundle, model, retry_feedback,
                       error={"category": category, "message": "\n".join(messages)})

    if _get(bundle, "hint_code") is None:
        write_files(component_id, files, repo_root)
    return _result(bundle, model, retry_feedback, files=files)


def commit_cache(result, repo_root: Path = None) -> None:
    if (
        not _get(result, "files")
        or _get(result, "model_call_error")
        or _get(result, "refused")
        or getattr(result, "_hint_mode", False)
    ):
        return
    cm = _load_dep("cache-manager", "cache_manager", Path(repo_root or "."))
    key = _cache_key(cm, _get(result, "spec_bundle_hash"), _get(result, "retry_feedback"), _get(result, "model"))
    payload = {name: _get(result, name) for name in _FIELDS}
    cm.put(
        key,
        cm.CachedResult(gate_type="generator", payload=payload, stored_at=cm.now_iso()),
        repo_root=repo_root,
    )
