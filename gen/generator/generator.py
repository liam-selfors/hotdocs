"""Generator: one cold (or hint-informed) model call per invocation, producing gen/<component>/."""

import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


@dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict = field(default_factory=dict)
    model_call_error: dict | None = None
    refused: str | None = None
    retry_feedback: list | None = None


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root():
    here = Path(__file__).resolve()
    gen = next(p for p in here.parents if p.name == "gen")
    return gen.parent


def _load_dependency(repo_root, dep_slug, module_name):
    base = Path(repo_root) / "gen" / dep_slug
    if not base.is_dir():
        base = _tool_root() / "gen" / dep_slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        pkg = base / module_name / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            module_name, pkg, submodule_search_locations=[str(pkg.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _is_sealed(repo_root, slug):
    component_md = Path(repo_root) / "specs" / "components" / slug / "component.md"
    if not component_md.is_file():
        return False
    lines = component_md.read_text(encoding="utf-8").split("\n")
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        if key.strip() == "sealed" and value.strip().lower() == "true":
            return True
    return False


def _mapping(value):
    value = value or {}
    if not value:
        return "(none)"
    return "\n\n".join(f"### {k}\n{value[k]}" for k in sorted(value))


def _build_prompt(bundle, component_id, module_name, nonce, retry_feedback):
    preamble = "\n".join([
        f"You are generating the complete source for one component of a spec-driven pipeline, "
        f"to be written under gen/{component_id[5:] if component_id.startswith('comp-') else component_id}/, "
        f"from the spec bundle sections below.",
        "",
        f"PROMPT_VERSION: {PROMPT_VERSION}",
        "",
        "Rules:",
        "- Construct your answer from exactly the sections given below. Never invent or assume "
        "anything about this component's \"real\" prior implementation.",
        "- Implement exactly what the spec requires and nothing more: no validation, fallback, "
        "option, or error path that the SPEC, INTERFACE and CONSTRAINTS sections do not call for. "
        "Every branch you write must be one the spec's acceptance criteria can reach; code beyond "
        "the spec is untested and is rejected by mutation testing.",
        f"- Lay out your output as either a flat {module_name}.py module or a {module_name}/ package "
        f"(with __init__.py) directly under the component's gen directory -- never a deeper layout "
        f"(e.g. a src/ subdirectory) and never a separately-installed distribution.",
        "- If your own generated code dynamically loads a dependency module at runtime -- by any "
        "means: a bare `import <module_name>` statement, a `sys.modules` lookup keyed on that bare "
        "name, or resolving a file path relative to your own `__file__` -- it MUST instead resolve "
        "that dependency from the `repo_root` parameter your own function was actually called with, "
        "joined to the module path the dependency usage gives for it: `gen/<dep-slug>/` for an "
        "ordinary dependency, or a sealed dependency's own `source_path`, holding `<module_name>.py` "
        "(flat) or `<module_name>/__init__.py` (package). Only when that directory does not exist "
        "under `repo_root`, fall back to the same path under the tool root: the parent of the "
        "nearest directory named `gen` above your own module's `__file__`. `repo_root` always wins "
        "when it has the directory. Never trust a bare-named `sys.modules` entry.",
        "- If your own generated code loads a module from a file path at runtime, you MUST register "
        "the loaded module object in sys.modules under its load-time name BEFORE executing its code "
        "(exec_module) -- never after, never omitted.",
        "- Any value you read from a dependency call -- including the dependency function's own "
        "top-level return value, not only values nested within it -- MUST use dual "
        "dict-or-attribute access, never a bare `.attr` access alone. A dependency may legitimately "
        "return either a dict or an object.",
        "- Output only the files that belong under the component's gen directory -- no explanation, "
        "no commentary outside of file content itself.",
        "",
        "Reply format: wrap each file's content exactly as a line holding the begin marker below "
        "(with the file's path relative to the component's gen directory in place of the "
        f"placeholder), then the complete, exact file content, then a line holding the end marker "
        f"below. The nonce {nonce} is unique to this call; use it on every marker. Text outside "
        "the blocks is ignored.",
        "",
        f"-----BEGIN FILE {nonce}: <path relative to the component's gen directory>-----",
        "<the complete, exact file content, verbatim>",
        f"-----END FILE {nonce}-----",
    ])

    sections = [
        ("## component_id", component_id),
        ("## SPEC", _get(bundle, "spec", "")),
        ("## INTERFACE", _get(bundle, "interface", "")),
        ("## CONSTRAINTS", _get(bundle, "constraints", "")),
        ("## DEPENDENCY INTERFACES", _mapping(_get(bundle, "dependency_interfaces", {}))),
        ("## DEPENDENCY CONTEXT", _mapping(_get(bundle, "dependency_context", {}))),
        ("## VARS", _mapping(_get(bundle, "vars", {}))),
        ("## GLOSSARY", _get(bundle, "glossary", "")),
    ]

    usage = _get(bundle, "dependency_usage", {}) or {}
    non_empty_usage = {k: v for k, v in usage.items() if v}
    if non_empty_usage:
        sections.append((
            "## DEPENDENCY USAGE",
            "Real, importable symbols from each dependency's actual current code -- use these to "
            "call the dependency correctly. Distinct from DEPENDENCY INTERFACES (the dependency's "
            "contract) and not acceptance-test content.\n\n" + _mapping(non_empty_usage),
        ))

    hint_code = _get(bundle, "hint_code", None)
    if hint_code is not None:
        hint_files = "\n\n".join(
            f"--- hint file: {p} ---\n{hint_code[p]}\n--- end hint file: {p} ---"
            for p in sorted(hint_code)
        )
        sections.append((
            "## HINT_CODE",
            "The component's existing generated code, provided as context only -- this is not "
            "part of the spec.\n\n" + hint_files,
        ))

    if retry_feedback:
        sections.append((
            "## RETRY_FEEDBACK",
            "A prior attempt did not satisfy these requirement ids, whose text is already above:\n"
            + "\n".join(f"- {rid}" for rid in retry_feedback),
        ))

    return preamble + "\n\n" + "\n\n".join(f"{h}\n{c}" for h, c in sections)


def _parse_files(text, nonce, slug):
    pattern = re.compile(
        rf"^-----BEGIN FILE {re.escape(nonce)}: (.+?)-----\n(.*?)^-----END FILE {re.escape(nonce)}-----$",
        re.M | re.S,
    )
    files = {}
    for match in pattern.finditer(text):
        path = match.group(1).strip()
        for prefix in (f"gen/{slug}/", f"{slug}/"):
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        files[path] = match.group(2)
    return files


def _empty_message(text):
    if not text.strip():
        return "the model reply was empty"
    message = "the model reply contained no files; it began:\n" + text[:4000]
    if len(text) > 4000:
        message += f"\n[{len(text) - 4000} more characters]"
    return message


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    repo_root = Path.cwd() if repo_root is None else Path(repo_root)
    component_id = _get(bundle, "component_id")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    module_name = slug.replace("-", "_")
    hint_mode = _get(bundle, "hint_code", None) is not None

    def result(**kwargs):
        return GenerationResult(
            component_id=component_id,
            spec_bundle_hash=spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=kwargs.get("cache_hit", False),
            files=kwargs.get("files", {}),
            model_call_error=kwargs.get("model_call_error"),
            refused=kwargs.get("refused"),
            retry_feedback=retry_feedback,
        )

    # R-GEN-009: precondition, before any cache read or model call.
    if _is_sealed(repo_root, slug):
        return result(refused="sealed-component")
    if (repo_root / "gen" / slug / ".overrides.json").is_file():
        return result(refused="pinned-override")

    cache_manager = _load_dependency(repo_root, "cache-manager", "cache_manager")
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )
    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = _get(cached, "payload")
        return result(cache_hit=True, files=dict(_get(payload, "files")))

    llm_endpoint = _load_dependency(repo_root, "llm-endpoint", "llm_endpoint")
    nonce = uuid.uuid4().hex
    prompt = _build_prompt(bundle, component_id, module_name, nonce, retry_feedback)
    response = llm_endpoint.complete(prompt, model, backend=llm_backend)

    error = _get(response, "model_call_error")
    if error:
        return result(model_call_error=error)

    text = _get(response, "text")
    files = _parse_files(text, nonce, slug)
    if not files:
        return result(model_call_error={"category": "empty_response", "message": _empty_message(text)})

    if not hint_mode:
        out_dir = repo_root / "gen" / slug
        for path, content in files.items():
            target = out_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        cache_manager.put(
            cache_key,
            cache_manager.CachedResult(
                gate_type="generator",
                payload={
                    "component_id": component_id,
                    "model": model,
                    "prompt_version": PROMPT_VERSION,
                    "files": files,
                },
                stored_at=cache_manager.now_iso(),
            ),
            repo_root=repo_root,
        )

    return result(files=files)
