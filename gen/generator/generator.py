"""Generator: one cold (or hint) model call producing gen/<component>/ from a SpecBundle."""

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "generator@3.2.0"
PROMPT_VERSION = "v12"

_USAGE_SENTENCE = (
    "Real, importable symbols from each dependency's actual current code -- "
    "distinct from DEPENDENCY INTERFACES, not acceptance-test content."
)
_HINT_SENTENCE = (
    "The component's current gen/ code, given as context only -- distinct from "
    "the spec bundle sections above, which govern wherever the two differ."
)
_RETRY_SENTENCE = (
    "Requirement ids a caller reports as having failed on a prior attempt:"
)


@dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict = field(default_factory=dict)
    model_call_error: object = None
    refused: object = None
    retry_feedback: object = None
    mode: str = "single"
    transcript_sha256: object = None
    turns: int = 1
    tool_calls: int = 0
    isolation: object = None


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _module_name(component_id):
    return _slug(component_id).replace("-", "_")


def _repo(repo_root):
    return Path(repo_root) if repo_root is not None else Path.cwd()


def _tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _load_path(name, path, locations=None):
    spec = importlib.util.spec_from_file_location(
        name, str(path), submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _unique_name(prefix, path):
    return prefix + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]


def _load_dep(dep_slug, mod_name, repo):
    base = repo / "gen" / dep_slug
    if not base.is_dir():
        base = _tool_root() / "gen" / dep_slug
    flat = base / f"{mod_name}.py"
    if flat.exists():
        path, locations = flat, None
    else:
        path, locations = base / mod_name / "__init__.py", [str(base / mod_name)]
    return _load_path(_unique_name(f"_hotdocs_dep_{mod_name}_", path), path, locations)


def _load_adapter(kind, repo):
    mod = "kind_" + kind.replace("-", "_")
    path = repo / "gen" / f"kind-{kind}" / f"{mod}.py"
    if not path.exists():
        path = _tool_root() / "gen" / f"kind-{kind}" / f"{mod}.py"
    if not path.exists():
        return None
    return _load_path(_unique_name(f"_hotdocs_kind_{mod}_", path), path)


def _frontmatter(repo, component_id):
    path = repo / "specs" / "components" / _slug(component_id) / "component.md"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            out.append(line)
    return out


def _declared_assets(repo, component_id):
    for line in _frontmatter(repo, component_id):
        if line.startswith("assets:"):
            inner = line[line.index("[") + 1:line.index("]")]
            assets = []
            for item in inner.split(","):
                item = item.strip()
                if item:
                    kind, path = item.split(":", 1)
                    assets.append((kind.strip(), path.strip()))
            return assets
    return []


def check_write_allowed(bundle, repo_root=None):
    repo = _repo(repo_root)
    component_id = _get(bundle, "component_id")
    for line in _frontmatter(repo, component_id):
        if line.startswith("sealed:") and line.split(":", 1)[1].strip() == "true":
            return "sealed-component"
    overrides = repo / "gen" / _slug(component_id) / ".overrides.json"
    if overrides.exists():
        data = json.loads(overrides.read_text(encoding="utf-8"))
        pinned = data.get("files", data) if isinstance(data, dict) else data
        if pinned:
            return "pinned-override"
    return None


def _mapping(value):
    value = value or {}
    if not value:
        return "(none)"
    return "\n\n".join(f"### {key}\n{value[key]}" for key in sorted(value))


def render_prompt_sections(bundle, retry_feedback=None):
    sections = [
        ("SPEC", _get(bundle, "spec")),
        ("INTERFACE", _get(bundle, "interface")),
        ("CONSTRAINTS", _get(bundle, "constraints")),
        ("DEPENDENCY INTERFACES", _mapping(_get(bundle, "dependency_interfaces"))),
        ("DEPENDENCY CONTEXT", _mapping(_get(bundle, "dependency_context"))),
        ("VARS", _mapping(_get(bundle, "vars"))),
        ("GLOSSARY", _get(bundle, "glossary")),
    ]
    usage = {k: v for k, v in (_get(bundle, "dependency_usage") or {}).items() if v}
    if usage:
        sections.append(("DEPENDENCY USAGE", _USAGE_SENTENCE + "\n\n" + _mapping(usage)))
    hint_code = _get(bundle, "hint_code")
    if hint_code is not None:
        blocks = "\n\n".join(
            f"--- hint file: {path} ---\n{hint_code[path]}\n--- end hint file: {path} ---"
            for path in sorted(hint_code)
        )
        sections.append(("HINT_CODE", _HINT_SENTENCE + "\n\n" + blocks))
    if retry_feedback:
        lines = "\n".join(f"- {rid}" for rid in retry_feedback)
        sections.append(("RETRY_FEEDBACK", _RETRY_SENTENCE + "\n" + lines))
    return sections


def _instructions(component_id, nonce, assets):
    slug = _slug(component_id)
    mod = _module_name(component_id)
    asset_list = ", ".join(path for _, path in assets) or "(none)"
    return (
        "You are generating the complete source for one component of a spec-driven "
        f"pipeline, to be written under gen/{slug}/, from the spec bundle sections below.\n"
        "\n"
        f"PROMPT_VERSION: {PROMPT_VERSION}\n"
        "\n"
        "Reply format: wrap each file's content exactly as a line holding the begin "
        f"marker below (with the file's path relative to gen/{slug}/ in place of the "
        "placeholder), then the complete, exact file content, then a line holding the "
        "end marker below. After the last file, end your reply with a line holding the "
        "end-of-reply marker below. Text outside the blocks is ignored.\n"
        "\n"
        f"-----BEGIN FILE {nonce}: <path relative to gen/{slug}/>-----\n"
        "<the complete, exact file content, verbatim>\n"
        f"-----END FILE {nonce}-----\n"
        "\n"
        f"-----END REPLY {nonce}-----\n"
        "\n"
        "Rules:\n"
        "- Construct your answer from exactly the sections given below.\n"
        "- Implement exactly what the spec requires and nothing more: no validation, "
        "fallback, option, or error path that the SPEC, INTERFACE and CONSTRAINTS "
        "sections do not call for. A branch no acceptance criterion reaches is untested "
        "and is rejected by mutation testing.\n"
        f"- Lay out your output as either a flat {mod}.py module or a {mod}/ package "
        f"(with __init__.py) directly under gen/{slug}/ -- never a deeper layout (e.g. a "
        "src/ subdirectory) and never a separately-installed distribution.\n"
        f"- Also write each declared asset file: {asset_list}. Write no other non-.py file.\n"
        "- If your own generated code dynamically loads a dependency module at runtime -- "
        "a bare `import <module_name>`, a `sys.modules` lookup keyed on that bare name, or "
        "a path relative to your own `__file__` -- it MUST instead resolve that dependency "
        "from the `repo_root` parameter your own function was actually called with, joined "
        "to the module path the dependency usage gives for it: `gen/<dep-slug>/`, or a "
        "sealed dependency's own `source_path`. Only when that directory does not exist "
        "under `repo_root`, fall back to the same path under the tool root: the parent of "
        "the nearest directory named `gen` above your own module's `__file__`. Never trust "
        "a stale bare-named `sys.modules` entry.\n"
        "- If your own generated code loads a module from a file path at runtime, register "
        "the loaded module in sys.modules under its load-time name BEFORE exec_module.\n"
        "- Any value you read from a dependency call -- including the dependency function's "
        "own top-level return value -- MUST use dual dict-or-attribute access, never a bare "
        "`.attr` access alone: a dependency may return either a dict or an object."
    )


def _build_prompt(bundle, retry_feedback, nonce, assets):
    component_id = _get(bundle, "component_id")
    parts = [
        _instructions(component_id, nonce, assets),
        f"## component_id\n{component_id}",
    ]
    parts.extend(f"## {title}\n{text}" for title, text in render_prompt_sections(bundle, retry_feedback))
    return "\n\n".join(parts)


def _strip_prefix(path, slug):
    for prefix in (f"gen/{slug}/", f"{slug}/"):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def _split_lines(text):
    parts = text.split("\n")
    lines = [p + "\n" for p in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _parse_reply(text, nonce, slug):
    """Return (files, error) per R-GEN-021 steps 1-3."""
    begin_re = re.compile(rf"-----BEGIN FILE {nonce}: (.*)-----")
    end_file = f"-----END FILE {nonce}-----"
    end_reply = f"-----END REPLY {nonce}-----"
    files = {}
    saw_begin = False
    saw_end_reply = False
    current = None
    buf = []
    for line in _split_lines(text):
        stripped = line.rstrip("\r\n")
        if current is not None:
            if stripped == end_file:
                files[_strip_prefix(current, slug)] = "".join(buf)
                current = None
            else:
                buf.append(line)
            continue
        match = begin_re.fullmatch(stripped)
        if match:
            saw_begin = True
            current = match.group(1).strip()
            buf = []
        elif stripped == end_reply:
            saw_end_reply = True
    if not saw_begin:
        if not text.strip():
            message = "the model reply was empty"
        else:
            message = "the model reply contained no files; it began:\n" + text[:4000]
            if len(text) > 4000:
                message += f"\n[{len(text) - 4000} more characters]"
        return None, {"category": "empty_response", "message": message}
    if current is not None:
        return None, {
            "category": "truncated_response",
            "message": f"the model reply was truncated: file {current} has no end marker",
        }
    if not saw_end_reply:
        return None, {
            "category": "truncated_response",
            "message": f"the model reply was truncated: the end marker {end_reply} is missing",
        }
    return files, None


def write_files(component_id, files, repo_root=None):
    base = _repo(repo_root) / "gen" / _slug(component_id)
    for path, content in files.items():
        target = base / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))


def check_asset_environment(component_id, repo_root=None):
    repo = _repo(repo_root)
    kinds = ["python"]
    for kind, _ in _declared_assets(repo, component_id):
        if kind not in kinds:
            kinds.append(kind)
    for kind in kinds:
        adapter = _load_adapter(kind, repo)
        if adapter is None:
            return "environment", [f"unknown asset kind: {kind}"]
        report = adapter.provision(repo)
        if not _get(report, "ok"):
            return "environment", [_get(report, "reason")]
    return None, []


def check_assets(component_id, files, repo_root=None):
    repo = _repo(repo_root)
    slug = _slug(component_id)
    assets = _declared_assets(repo, component_id)
    adapters = {}
    for kind in ["python"] + [k for k, _ in assets]:
        if kind not in adapters:
            adapter = _load_adapter(kind, repo)
            if adapter is None:
                return "environment", [f"unknown asset kind: {kind}"]
            adapters[kind] = adapter

    missing = [f"missing asset: {path}" for _, path in assets if path not in files]
    if missing:
        return "missing_asset", missing

    declared = {path for _, path in assets}
    undeclared = sorted(p for p in files if not p.endswith(".py") and p not in declared)
    if undeclared:
        return "malformed_layout", [f"undeclared file: {p}" for p in undeclared]

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        messages = []
        for kind, path in assets:
            asset_file = tmp / "assets" / slug / path
            asset_file.parent.mkdir(parents=True, exist_ok=True)
            asset_file.write_bytes(files[path].encode("utf-8"))
            messages.extend(f"{path}: {m}" for m in adapters[kind].layout_errors(asset_file))
        if messages:
            return "malformed_layout", messages

        code_dir = tmp / "gen" / slug
        code_dir.mkdir(parents=True)
        for path, content in files.items():
            if path.endswith(".py"):
                target = code_dir / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content.encode("utf-8"))
        messages = list(adapters["python"].layout_errors(code_dir))
        if messages:
            return "malformed_layout", messages
    return None, []


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


def _result(bundle, model, retry_feedback, *, files=None, error=None, refused=None, cache_hit=False):
    return GenerationResult(
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


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    repo = _repo(repo_root)
    component_id = _get(bundle, "component_id")
    slug = _slug(component_id)
    hint_mode = _get(bundle, "hint_code") is not None

    reason = check_write_allowed(bundle, repo)
    if reason:
        return _result(bundle, model, retry_feedback, refused=reason)

    cache_manager = _load_dep("cache-manager", "cache_manager", repo)
    key = _cache_key(cache_manager, _get(bundle, "spec_bundle_hash"), retry_feedback, model)
    hit = cache_manager.get(key, repo_root=repo_root)
    if not isinstance(hit, cache_manager.Miss):
        files = dict(_get(_get(hit, "payload"), "files"))
        if not hint_mode:
            write_files(component_id, files, repo)
        result = _result(bundle, model, retry_feedback, files=files, cache_hit=True)
        result._hint_mode = hint_mode
        return result

    category, messages = check_asset_environment(component_id, repo)
    if category:
        return _result(bundle, model, retry_feedback,
                       error={"category": category, "message": "\n".join(messages)})

    nonce = uuid.uuid4().hex
    prompt = _build_prompt(bundle, retry_feedback, nonce, _declared_assets(repo, component_id))
    llm_endpoint = _load_dep("llm-endpoint", "llm_endpoint", repo)
    response = llm_endpoint.complete(prompt, model, backend=llm_backend)
    error = _get(response, "model_call_error")
    if error:
        return _result(bundle, model, retry_feedback,
                       error={"category": _get(error, "category"), "message": _get(error, "message")})

    files, error = _parse_reply(_get(response, "text"), nonce, slug)
    if error:
        return _result(bundle, model, retry_feedback, error=error)

    mod = _module_name(component_id)
    if f"{mod}.py" not in files and f"{mod}/__init__.py" not in files:
        return _result(bundle, model, retry_feedback, error={
            "category": "missing_module",
            "message": f"the reply wrote neither {mod}.py nor {mod}/__init__.py",
        })

    category, messages = check_assets(component_id, files, repo)
    if category:
        return _result(bundle, model, retry_feedback,
                       error={"category": category, "message": "\n".join(messages)})

    if not hint_mode:
        write_files(component_id, files, repo)
    result = _result(bundle, model, retry_feedback, files=files)
    result._hint_mode = hint_mode
    return result


def commit_cache(result, repo_root=None):
    if (not _get(result, "files") or _get(result, "model_call_error")
            or _get(result, "refused") or _get(result, "_hint_mode", False)):
        return
    cache_manager = _load_dep("cache-manager", "cache_manager", _repo(repo_root))
    key = _cache_key(cache_manager, _get(result, "spec_bundle_hash"),
                     _get(result, "retry_feedback"), _get(result, "model"))
    payload = {f.name: _get(result, f.name) for f in dataclasses.fields(GenerationResult)}
    cached = cache_manager.CachedResult(
        gate_type="generator", payload=payload, stored_at=cache_manager.now_iso()
    )
    cache_manager.put(key, cached, repo_root=repo_root)
