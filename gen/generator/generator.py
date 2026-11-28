"""generator: one single-shot model call producing gen/<component>/ from a SpecBundle."""

import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

GATE_VERSION = "generator@3.2.0"
PROMPT_VERSION = "v12"

PROMPT_TEMPLATE = (
    "You are generating the complete source for one component of a spec-driven "
    "pipeline, to be written under gen/{slug}/, from the spec bundle sections below.\n"
    "\n"
    "PROMPT_VERSION: {prompt_version}\n"
    "\n"
    "Reply format: wrap each file's content exactly as a line holding the begin marker "
    "below (with the file's path relative to gen/{slug}/ in place of the placeholder), "
    "then the complete, exact file content, then a line holding the end marker below. "
    "After the last file, end your reply with a line holding the end-of-reply marker "
    "below. Text outside the blocks is ignored.\n"
    "\n"
    "-----BEGIN FILE {nonce}: <path relative to gen/{slug}/>-----\n"
    "<the complete, exact file content, verbatim>\n"
    "-----END FILE {nonce}-----\n"
    "\n"
    "-----END REPLY {nonce}-----\n"
    "\n"
    "Rules:\n"
    "- Construct your answer from exactly the sections given below.\n"
    "- Implement exactly what the spec requires and nothing more: no validation, "
    "fallback, option, or error path that the SPEC, INTERFACE and CONSTRAINTS sections "
    "do not call for. A branch no acceptance criterion reaches is untested and is "
    "rejected by mutation testing.\n"
    "- Lay out your output as either a flat {module}.py module or a {module}/ package "
    "(with __init__.py) directly under gen/{slug}/ -- never a deeper layout (e.g. a src/ "
    "subdirectory) and never a separately-installed distribution.\n"
    "- Also write each declared asset file: {assets}. Write no other non-.py file.\n"
    "- If your own generated code dynamically loads a dependency module at runtime -- a "
    "bare `import <module_name>`, a `sys.modules` lookup keyed on that bare name, or a "
    "path relative to your own `__file__` -- it MUST instead resolve that dependency "
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
    "`.attr` access alone: a dependency may return either a dict or an object.\n"
    "\n"
    "## component_id\n"
    "{component_id}"
)

USAGE_SENTENCE = (
    "Real, importable symbols from each dependency's actual current code -- distinct "
    "from DEPENDENCY INTERFACES, not acceptance-test content."
)
HINT_SENTENCE = (
    "The component's current code, given as context only: it is not part of the "
    "specification, and the sections above take precedence over it."
)
RETRY_SENTENCE = (
    "These requirement ids failed on a prior attempt; make sure the implementation "
    "satisfies each of them:"
)


@dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict
    model_call_error: object
    refused: object
    retry_feedback: object
    mode: str = "single"
    transcript_sha256: object = None
    turns: int = 1
    tool_calls: int = 0
    isolation: object = None


def _get(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _root(repo_root):
    return Path(repo_root) if repo_root is not None else Path.cwd()


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _module(component_id):
    return _slug(component_id).replace("-", "_")


def _tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def _exec_file(name, path, search=None):
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=search)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dep(dep_slug, module, root):
    rel = Path("gen") / dep_slug
    directory = root / rel
    if not directory.is_dir():
        directory = _tool_root() / rel
    path = directory / f"{module}.py"
    if path.is_file():
        return _exec_file(module, path)
    pkg = directory / module
    return _exec_file(module, pkg / "__init__.py", [str(pkg)])


def _load_adapter(kind, root):
    module = "kind_" + kind.replace("-", "_")
    rel = Path("gen") / f"kind-{kind}" / f"{module}.py"
    path = root / rel
    if not path.is_file():
        path = _tool_root() / rel
    if not path.is_file():
        return None
    return _exec_file(f"{module}_{uuid.uuid4().hex}", path)


def _frontmatter(slug, root):
    path = root / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0].strip() != "---":
        return []
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
    return lines[1:end]


def _declared_assets(slug, root):
    for line in _frontmatter(slug, root):
        if line.startswith("assets:"):
            inner = line[line.index("[") + 1:line.index("]")]
            assets = []
            for item in inner.split(","):
                item = item.strip()
                if item:
                    kind, _, path = item.partition(":")
                    assets.append((kind, path))
            return assets
    return []


def _kinds(assets):
    kinds = ["python"]
    for kind, _ in assets:
        if kind not in kinds:
            kinds.append(kind)
    return kinds


def _write(base, rel, content):
    dest = base / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content.encode("utf-8"))
    return dest


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


def _mapping(value):
    if not value:
        return "(none)"
    return "\n\n".join(f"### {key}\n{value[key]}" for key in sorted(value))


def check_write_allowed(bundle, repo_root=None):
    root = _root(repo_root)
    slug = _slug(_get(bundle, "component_id"))
    for line in _frontmatter(slug, root):
        if line.startswith("sealed:") and line.split(":", 1)[1].strip().lower() == "true":
            return "sealed-component"
    overrides = root / "gen" / slug / ".overrides.json"
    if overrides.is_file():
        data = json.loads(overrides.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "files" in data:
            data = data["files"]
        if data:
            return "pinned-override"
    return None


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
    usage = {k: v for k, v in _get(bundle, "dependency_usage").items() if v}
    if usage:
        sections.append(("DEPENDENCY USAGE", USAGE_SENTENCE + "\n\n" + _mapping(usage)))
    hint_code = _get(bundle, "hint_code")
    if hint_code is not None:
        blocks = []
        for path in sorted(hint_code):
            content = hint_code[path]
            sep = "" if content.endswith("\n") else "\n"
            blocks.append(
                f"--- hint file: {path} ---\n{content}{sep}--- end hint file: {path} ---"
            )
        sections.append(("HINT_CODE", HINT_SENTENCE + "\n\n" + "\n\n".join(blocks)))
    if retry_feedback:
        sections.append(
            ("RETRY_FEEDBACK", RETRY_SENTENCE + "\n" + "\n".join(f"- {r}" for r in retry_feedback))
        )
    return sections


def _render_prompt(bundle, retry_feedback, nonce, root):
    component_id = _get(bundle, "component_id")
    slug = _slug(component_id)
    assets = [path for _, path in _declared_assets(slug, root)]
    header = PROMPT_TEMPLATE.format(
        slug=slug,
        prompt_version=PROMPT_VERSION,
        nonce=nonce,
        module=_module(component_id),
        assets=", ".join(assets) or "(none)",
        component_id=component_id,
    )
    sections = [f"## {title}\n{text}" for title, text in render_prompt_sections(bundle, retry_feedback)]
    return "\n\n".join([header] + sections)


def _strip_prefix(path, slug):
    for prefix in (f"gen/{slug}/", f"{slug}/"):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def _empty_message(text):
    if not text.strip():
        return "the model reply was empty"
    message = "the model reply contained no files; it began:\n" + text[:4000]
    if len(text) > 4000:
        message += f"\n[{len(text) - 4000} more characters]"
    return message


def _parse_reply(text, nonce, slug):
    begin = re.compile(r"-----BEGIN FILE " + nonce + r": (.*)-----")
    end_file = f"-----END FILE {nonce}-----"
    end_reply = f"-----END REPLY {nonce}-----"
    lines = text.splitlines(keepends=True)
    files = {}
    ended = False
    i = 0
    while i < len(lines):
        bare = lines[i].strip()
        match = begin.fullmatch(bare)
        if match:
            path = match.group(1).strip()
            j = next((k for k in range(i + 1, len(lines)) if lines[k].strip() == end_file), None)
            if j is None:
                return {}, {
                    "category": "truncated_response",
                    "message": f"the reply's file {path} has no END FILE line",
                }
            files[_strip_prefix(path, slug)] = "".join(lines[i + 1:j])
            i = j + 1
            continue
        if bare == end_reply:
            ended = True
        i += 1
    if not files:
        return {}, {"category": "empty_response", "message": _empty_message(text)}
    if not ended:
        return {}, {
            "category": "truncated_response",
            "message": f"the reply's end marker {end_reply} is missing",
        }
    return files, None


def write_files(component_id, files, repo_root=None):
    target = _root(repo_root) / "gen" / _slug(component_id)
    for path, content in files.items():
        _write(target, path, content)


def check_asset_environment(component_id, repo_root=None):
    root = _root(repo_root)
    for kind in _kinds(_declared_assets(_slug(component_id), root)):
        adapter = _load_adapter(kind, root)
        if adapter is None:
            return "environment", [f"unknown asset kind: {kind}"]
        report = adapter.provision(root)
        if not _get(report, "ok"):
            return "environment", [_get(report, "reason")]
    return None, []


def check_assets(component_id, files, repo_root=None):
    root = _root(repo_root)
    assets = _declared_assets(_slug(component_id), root)
    adapters = {}
    for kind in _kinds(assets):
        adapters[kind] = _load_adapter(kind, root)
        if adapters[kind] is None:
            return "environment", [f"unknown asset kind: {kind}"]
    missing = [f"missing asset: {path}" for _, path in assets if path not in files]
    if missing:
        return "missing_asset", missing
    declared = {path for _, path in assets}
    undeclared = [
        f"undeclared file: {path}"
        for path in sorted(files)
        if not path.endswith(".py") and path not in declared
    ]
    if undeclared:
        return "malformed_layout", undeclared
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        errors = []
        for kind, path in assets:
            asset_file = _write(tmp / "assets", path, files[path])
            errors += [f"{path}: {m}" for m in adapters[kind].layout_errors(asset_file)]
        if errors:
            return "malformed_layout", errors
        code = tmp / "code"
        code.mkdir()
        for path, content in files.items():
            if path.endswith(".py"):
                _write(code, path, content)
        errors = list(adapters["python"].layout_errors(code))
    if errors:
        return "malformed_layout", errors
    return None, []


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    root = _root(repo_root)
    component_id = _get(bundle, "component_id")
    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    hint = _get(bundle, "hint_code") is not None

    def result(files=None, error=None, refused=None, cache_hit=False):
        r = GenerationResult(
            component_id=component_id,
            spec_bundle_hash=spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=cache_hit,
            files=files or {},
            model_call_error=error,
            refused=refused,
            retry_feedback=retry_feedback,
        )
        r._hint_mode = hint
        return r

    refusal = check_write_allowed(bundle, root)
    if refusal is not None:
        return result(refused=refusal)

    cm = _load_dep("cache-manager", "cache_manager", root)
    hit = cm.get(_cache_key(cm, spec_bundle_hash, retry_feedback, model), repo_root=repo_root)
    if not isinstance(hit, cm.Miss):
        files = dict(_get(_get(hit, "payload"), "files"))
        if not hint:
            write_files(component_id, files, root)
        return result(files=files, cache_hit=True)

    category, messages = check_asset_environment(component_id, root)
    if category is not None:
        return result(error={"category": category, "message": "\n".join(messages)})

    nonce = uuid.uuid4().hex
    prompt = _render_prompt(bundle, retry_feedback, nonce, root)
    llm = _load_dep("llm-endpoint", "llm_endpoint", root)
    response = llm.complete(prompt, model, backend=llm_backend)
    call_error = _get(response, "model_call_error")
    if call_error is not None:
        return result(error={
            "category": _get(call_error, "category"),
            "message": _get(call_error, "message"),
        })

    files, error = _parse_reply(_get(response, "text"), nonce, _slug(component_id))
    if error is not None:
        return result(error=error)

    module = _module(component_id)
    if f"{module}.py" not in files and f"{module}/__init__.py" not in files:
        return result(error={
            "category": "missing_module",
            "message": f"the reply wrote neither {module}.py nor {module}/__init__.py",
        })

    category, messages = check_assets(component_id, files, root)
    if category is not None:
        return result(error={"category": category, "message": "\n".join(messages)})

    if not hint:
        write_files(component_id, files, root)
    return result(files=files)


def commit_cache(result, repo_root=None):
    files = _get(result, "files")
    if (
        not files
        or _get(result, "model_call_error") is not None
        or _get(result, "refused") is not None
        or getattr(result, "_hint_mode", False)
    ):
        return
    cm = _load_dep("cache-manager", "cache_manager", _root(repo_root))
    key = _cache_key(
        cm, _get(result, "spec_bundle_hash"), _get(result, "retry_feedback"), _get(result, "model")
    )
    payload = {
        "component_id": _get(result, "component_id"),
        "model": _get(result, "model"),
        "prompt_version": _get(result, "prompt_version"),
        "files": dict(files),
    }
    cm.put(
        key,
        cm.CachedResult(gate_type="generator", payload=payload, stored_at=cm.now_iso()),
        repo_root=repo_root,
    )
