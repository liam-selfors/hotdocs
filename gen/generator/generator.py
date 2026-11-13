"""Generator: one pinned-model call turning a SpecBundle into gen/<component>/.

Single-shot by design (R-GEN-011): exactly one candidate per invocation, no
internal retry loop. The cache is checked first (R-GEN-005); in ``cold`` mode
a successful result is written to ``gen/<component>/`` and the cache
(R-GEN-006); ``hint`` mode writes neither (R-GEN-016). A sealed component or a
pinned ``.overrides.json`` is refused before any model call (R-GEN-009).

Dependencies (``cache-manager``, ``llm-endpoint``) are loaded per call from the
``repo_root`` actually passed in, falling back to the tool root only when the
dependency's directory is absent there, and each loaded module is registered in
``sys.modules`` before its code runs (R-GEN-014).
"""

import hashlib
import importlib.util
import json
import re
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"

_FIVE = "-" * 5

# Frozen, versioned prompt template (R-GEN-003). Placeholders: version, slug,
# module, component_id, begin_marker, end_marker, nonce.
PROMPT_TEMPLATE = """You are generating the complete source for one component of a spec-driven pipeline, to be written under gen/{slug}/, from the spec bundle sections below.

PROMPT_VERSION: {version}

Rules:
- Construct your answer from exactly the sections given below. Never invent or assume anything about this component's "real" prior implementation.
- Implement exactly what the spec requires and nothing more: no validation, fallback, option, or error path that the SPEC, INTERFACE and CONSTRAINTS sections do not call for. Every branch you write must be one the spec's acceptance criteria can reach; code beyond the spec is untested and is rejected by mutation testing.
- Lay out your output as either a flat {module}.py module or a {module}/ package (with __init__.py) directly under gen/{slug}/ -- never a deeper layout (e.g. a src/ subdirectory) and never a separately-installed distribution.
- If your own generated code dynamically loads a dependency module at runtime -- by any means: a bare `import <module_name>` statement, a `sys.modules` lookup keyed on that bare name, or resolving a file path relative to your own `__file__` -- it MUST instead resolve that dependency from the `repo_root` parameter your own function was actually called with, joined to the module path the dependency usage gives for it: `gen/<dep-slug>/` for an ordinary dependency, or a sealed dependency's own `source_path`, holding `<module_name>.py` (flat) or `<module_name>/__init__.py` (package). Only when that directory does not exist under `repo_root`, fall back to the same path under the tool root: the parent of the nearest directory named `gen` above your own module's `__file__`. `repo_root` always wins when it has the directory. Never trust a bare-named `sys.modules` entry.
- If your own generated code loads a module from a file path at runtime, you MUST register the loaded module object in sys.modules under its load-time name BEFORE executing its code (exec_module) -- never after, never omitted.
- Any value you read from a dependency call -- including the dependency function's own top-level return value, not only values nested within it -- MUST use dual dict-or-attribute access, never a bare `.attr` access alone. A dependency may legitimately return either a dict or an object.
- Output only the files that belong under gen/{slug}/ -- no explanation, no commentary outside of file content itself.

Reply format: wrap each file's content exactly as a line holding the begin marker below (with the file's path relative to gen/{slug}/ in place of the placeholder), then the complete, exact file content, then a line holding the end marker below. The nonce {nonce} is unique to this call; use it on every marker. Text outside the blocks is ignored.

{begin_marker}
<the complete, exact file content, verbatim>
{end_marker}

## component_id
{component_id}
"""


@dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict
    model_call_error: dict | None
    refused: str | None
    retry_feedback: list | None


def _field(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load_dependency(dep_slug, module_name, repo_root):
    base = repo_root / "gen" / dep_slug
    if not base.is_dir():
        base = _tool_root() / "gen" / dep_slug
    flat = base / f"{module_name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        package_dir = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _is_sealed(repo_root, slug):
    path = repo_root / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return False
    match = re.match(r"---\s*\n(.*?)\n---", path.read_text(encoding="utf-8"), re.S)
    return bool(match and re.search(r"^sealed:\s*true\s*$", match.group(1), re.M | re.I))


def _has_pinned_overrides(repo_root, slug):
    path = repo_root / "gen" / slug / ".overrides.json"
    if not path.is_file():
        return False
    return bool(json.loads(path.read_text(encoding="utf-8")))


def _gate_inputs_hash(retry_feedback):
    text = json.dumps(sorted(retry_feedback or []), sort_keys=True)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _render_mapping(mapping):
    return "\n\n".join(f"### {key}\n{mapping[key]}" for key in sorted(mapping)) or "(none)"


def _build_prompt(bundle, slug, component_id, nonce, retry_feedback, hint_code):
    module = slug.replace("-", "_")
    begin_marker = f"{_FIVE}BEGIN FILE {nonce}: <path relative to gen/{slug}/>{_FIVE}"
    end_marker = f"{_FIVE}END FILE {nonce}{_FIVE}"
    parts = [
        PROMPT_TEMPLATE.format(
            version=PROMPT_VERSION,
            slug=slug,
            module=module,
            component_id=component_id,
            begin_marker=begin_marker,
            end_marker=end_marker,
            nonce=nonce,
        ),
        "## SPEC\n" + _field(bundle, "spec", ""),
        "## INTERFACE\n" + _field(bundle, "interface", ""),
        "## CONSTRAINTS\n" + _field(bundle, "constraints", ""),
        "## DEPENDENCY INTERFACES\n" + _render_mapping(_field(bundle, "dependency_interfaces", {})),
        "## DEPENDENCY CONTEXT\n" + _render_mapping(_field(bundle, "dependency_context", {})),
        "## VARS\n" + _render_mapping(_field(bundle, "vars", {})),
        "## GLOSSARY\n" + _field(bundle, "glossary", ""),
    ]
    usage = {k: v for k, v in _field(bundle, "dependency_usage", {}).items() if v}
    if usage:
        parts.append(
            "## DEPENDENCY USAGE\n"
            "Real, importable symbols from each dependency's actual current code -- "
            "use these to call the dependency correctly. Distinct from DEPENDENCY "
            "INTERFACES (the dependency's contract) and not acceptance-test content.\n\n"
            + _render_mapping(usage)
        )
    if hint_code is not None:
        files = "\n\n".join(
            f"--- hint file: {path} ---\n{hint_code[path]}\n--- end hint file: {path} ---"
            for path in sorted(hint_code)
        )
        parts.append(
            "## HINT_CODE\n"
            "Existing code -- a revision starting point only. It is NOT part of the "
            "spec sections above; keep it distinct from them.\n\n" + files
        )
    if retry_feedback:
        parts.append(
            "## RETRY_FEEDBACK\n"
            "A bare list of requirement ids a prior attempt failed to satisfy -- "
            "nothing else. Pay particular attention to satisfying exactly these "
            "requirements correctly.\n"
            + "\n".join(f"- {rid}" for rid in retry_feedback)
        )
    return "\n\n".join(parts) + "\n"


def _parse_files(text, nonce, slug):
    pattern = re.compile(
        "^"
        + re.escape(f"{_FIVE}BEGIN FILE {nonce}: ")
        + r"([^\n]+?)"
        + re.escape(_FIVE)
        + r"\n(.*?)^"
        + re.escape(f"{_FIVE}END FILE {nonce}{_FIVE}"),
        re.M | re.S,
    )
    files = {}
    for match in pattern.finditer(text):
        files[_strip_component_prefix(match.group(1).strip(), slug)] = match.group(2)
    return files


def _strip_component_prefix(path, slug):
    for prefix in (f"gen/{slug}/", f"{slug}/"):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def _write_files(repo_root, slug, files):
    gen_dir = repo_root / "gen" / slug
    for rel_path, content in files.items():
        target = gen_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    repo_root = Path.cwd() if repo_root is None else Path(repo_root)
    component_id = _field(bundle, "component_id")
    spec_bundle_hash = _field(bundle, "spec_bundle_hash")
    hint_code = _field(bundle, "hint_code", None)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id

    def result(*, cache_hit=False, files=None, model_call_error=None, refused=None):
        return GenerationResult(
            component_id=component_id,
            spec_bundle_hash=spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=cache_hit,
            files=files if files is not None else {},
            model_call_error=model_call_error,
            refused=refused,
            retry_feedback=retry_feedback,
        )

    # R-GEN-009: precondition refusal, before any cache or model access.
    if _is_sealed(repo_root, slug):
        return result(refused="sealed-component")
    if _has_pinned_overrides(repo_root, slug):
        return result(refused="pinned-override")

    cache_manager = _load_dependency("cache-manager", "cache_manager", repo_root)
    key = cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=_gate_inputs_hash(retry_feedback),
        gate_version=GATE_VERSION,
        model_pin=model,
    )
    cached = cache_manager.get(key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        files = dict(_field(_field(cached, "payload", {}), "files", {}))
        if hint_code is None:
            _write_files(repo_root, slug, files)
        return result(cache_hit=True, files=files)

    nonce = uuid.uuid4().hex
    prompt = _build_prompt(bundle, slug, component_id, nonce, retry_feedback, hint_code)
    llm_endpoint = _load_dependency("llm-endpoint", "llm_endpoint", repo_root)
    response = llm_endpoint.complete(prompt, model, backend=llm_backend)

    error = _field(response, "model_call_error")
    if error:
        return result(model_call_error=error)

    files = _parse_files(_field(response, "text"), nonce, slug)
    if not files:
        return result(
            model_call_error={
                "category": "empty_response",
                "message": "model response contained no files",
            }
        )

    if hint_code is None:
        _write_files(repo_root, slug, files)
        cache_manager.put(
            key,
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