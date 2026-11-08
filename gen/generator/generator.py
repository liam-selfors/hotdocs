"""
gen/comp-generator/generator.py

Implementation of the `generator` component: calls a pinned model to
produce `gen/<component>/` from a `SpecBundle` -- cold, with no prior
code (unless the bundle carries `hint_code`), exactly one candidate per
invocation. See `specs/components/generator/` for the full spec this
file implements.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


# R-GEN-003: the prompt template is frozen and versioned; bumped on any
# change to its text or structure. v2 added dependency_usage (D55); v3
# added the per-call nonce delimiter and non-empty-only caching (D56);
# v4 added the explicit dynamic-import sys.modules warning (D57); v5
# added the flat-module/package output-layout instruction (R-GEN-015,
# D62); v6 added the always-included, repo_root-relative dependency-
# loading instruction (R-GEN-018, D138); v7 added the always-included
# dual dict-or-attribute access instruction for a dependency's own
# top-level return value (R-GEN-019, D139); v8 corrected v6's
# instruction to honor a sealed dependency's own source_path (D159); v9
# added the tool-root fallback for a dependency absent under repo_root
# (D199).
PROMPT_VERSION = "v9"

# R-GEN-005/006: the cache-key component identifying this gate's shape.
# Bumped on D56 to orphan two pre-existing poisoned cache entries
# (empty-result responses that had been cached as if valid) without
# needing manual deletion. Bumped again on D62: GATE_VERSION MUST track
# every PROMPT_VERSION change, not just ones that touch caching logic
# itself -- missing this the first time let a stale, pre-fix candidate
# replay from cache instead of triggering a fresh call. Bumped again on
# D138, D139, and D159 for the same reason.
GATE_VERSION = "generator@1.8.0"


_SYSTEM_PROMPT = """You are generating the complete source for one component \
of a spec-driven pipeline, to be written under gen/<component>/, from the \
SpecBundle content below.

Rules:
- Construct your answer from exactly the SPEC / INTERFACE / CONSTRAINTS / \
DEPENDENCY INTERFACES / DEPENDENCY CONTEXT / VARS / GLOSSARY sections \
given below, plus DEPENDENCY USAGE and HINT_CODE / RETRY_FEEDBACK when \
present. Never invent or assume anything about this component's "real" \
prior implementation.
- HINT_CODE, when present, is existing code -- a revision starting point \
only. Keep it clearly distinct from the spec fields; never silently \
merge it with them in a way that makes a later audit unable to tell \
which parts of the prompt were "the spec" versus "the existing code."
- RETRY_FEEDBACK, when present, is a bare list of R-ids that a prior \
attempt failed to satisfy -- nothing else (no Gherkin text, no \
rationale, no expected/actual values). Pay particular attention to \
satisfying exactly those requirements correctly.
- DEPENDENCY USAGE, when present for a dependency, names real, \
importable symbols from that dependency's actual current code -- use it \
to call the dependency correctly, distinct from DEPENDENCY INTERFACES \
(the dependency's contract) and from acceptance-test content.
- If your own generated code needs to dynamically load a dependency \
module from a file path at runtime (rather than a static import \
relative to its own file), you MUST register the loaded module object \
in sys.modules under its load-time name BEFORE executing its code \
(exec_module) -- never after, never omitted. Skipping this step crashes \
on any dependency module that defines a dataclass, because dataclasses' \
internals look up sys.modules[cls.__module__] to resolve the class's \
own annotations at class-body-execution time.
- Output only the files that belong under gen/<component>/ for the \
target component -- no explanation, no commentary outside of file \
content itself.
- Lay out your output as either a flat <slug_with_underscores>.py \
module or a <slug_with_underscores>/ package (with __init__.py) \
directly under gen/<component>/ -- never a deeper layout (e.g. a src/ \
subdirectory) and never a separately-installed distribution. This is \
load-bearing, not stylistic: a future dependent's dependency_usage \
only ever looks for your code in those two exact shapes, and silently \
sees nothing there otherwise.
- If your own generated code dynamically loads a dependency module at \
runtime -- by any means: a bare `import <module_name>` statement, a \
`sys.modules` lookup keyed on that bare name, or resolving a file path \
relative to your own `__file__` -- it MUST instead resolve that \
dependency from the `repo_root` parameter your own function was \
actually called with, joined to the module path DEPENDENCY USAGE gives \
for it: `gen/<dep-slug>/` for an ordinary dependency, or a sealed \
dependency's own `source_path` (e.g. `pipeline/criterion-compiler/`), \
holding `<module_name>.py` (flat) or `<module_name>/__init__.py` \
(package). Only when that directory does not exist under `repo_root`, \
fall back to the same path under the tool root: the parent of the \
nearest directory named `gen` above your own module's `__file__` \
(a project holds only its own components; the tool's stay in the \
tool). `repo_root` always wins when it has the directory, so a test's \
fake planted there is never bypassed. Never trust a bare-named `sys.modules` entry -- a different \
`repo_root`'s earlier call in the same process may already have \
populated it with the wrong module, which is exactly what makes a bare \
`import <module_name>` dangerous even when it happens to work the \
first time it runs.
- Any value you read from a dependency call -- including the \
dependency function's own top-level return value, not only values \
nested within it -- MUST use dual dict-or-attribute access, never a \
bare `.attr` access alone. A dependency may legitimately return either \
a dict or an object; applying dual access only to nested entries and \
not to the dependency's own outer return value is still a bug.

For each file you produce, wrap its content exactly as instructed below."""


@dataclass
class GenerationResult:
    """Matches `interface/data/GenerationResult.md` exactly."""

    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: Dict[str, str]
    model_call_error: Optional[dict]
    refused: Optional[str]
    retry_feedback: Optional[List[str]]


# ---------------------------------------------------------------------------
# R-GEN-014: dynamic, per-call dependency loading.
#
# Dependencies are resolved from the *actual* repo_root passed to generate()
# on each call, rather than via a static sys.path-relative-to-__file__
# import -- that would silently keep reusing the first call's module if
# generate() is ever invoked more than once in the same process against two
# different repo_root values (e.g. a verification harness staging an
# untested candidate elsewhere while exercising it against real
# dependencies). The loaded module MUST be registered in sys.modules under
# its load-time name BEFORE exec_module runs its code -- omitting this
# crashes on any dependency defining a dataclass, because dataclasses'
# internals look up sys.modules[cls.__module__] to resolve the class's own
# annotations (D57).
# ---------------------------------------------------------------------------


def _tool_root() -> Path:
    # D199: the parent of the nearest `gen` directory above this file.
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    raise ImportError("generator is not under a gen/ directory")


def _load_module_from_repo(repo_root: Path, component_dir: str, module_name: str):
    # D199: repo_root first, so a test's fake wins; else the tool's own.
    base = Path(repo_root) / "gen" / component_dir
    if not base.is_dir():
        base = _tool_root() / "gen" / component_dir
    module_path = base / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_name!r} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec_module -- see R-GEN-014 / D57.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_cache_manager(repo_root: Path):
    return _load_module_from_repo(repo_root, "cache-manager", "cache_manager")


def _load_llm_endpoint(repo_root: Path):
    return _load_module_from_repo(repo_root, "llm-endpoint", "llm_endpoint")


def _load_spec_bundle_assembler(repo_root: Path):
    return _load_module_from_repo(
        repo_root, "spec-bundle-assembler", "spec_bundle_assembler"
    )


# ---------------------------------------------------------------------------
# R-GEN-009: precondition check -- sealed component / pinned override.
# ---------------------------------------------------------------------------


def _component_dir_name(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _read_frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end].strip("\n")
    result: dict = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        result[key] = value
    return result


def _check_precondition(repo_root: Path, component_id: str) -> Optional[str]:
    """Returns a refusal reason string (R-GEN-009), or None if generation
    may proceed. Resolved entirely before any model call is attempted."""

    comp_dir = _component_dir_name(component_id)

    component_md = Path(repo_root) / "specs" / "components" / comp_dir / "component.md"
    if component_md.exists():
        frontmatter = _read_frontmatter(component_md)
        if frontmatter.get("sealed") is True:
            return "sealed-component"

    overrides_path = Path(repo_root) / "gen" / comp_dir / ".overrides.json"
    if overrides_path.exists():
        try:
            overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            overrides = None
        if overrides:
            return "pinned-override"

    return None


# ---------------------------------------------------------------------------
# Cache key construction (R-GEN-005/006).
# ---------------------------------------------------------------------------


def _compute_gate_inputs_hash(retry_feedback: Optional[List[str]]) -> str:
    """retry_feedback MUST be incorporated when present (R-GEN-012/D33) so
    a blind call and a call carrying retry_feedback never collide in the
    cache, even for the same spec_bundle_hash/model_pin. Deterministic for
    both the present and absent case."""

    material = json.dumps(sorted(retry_feedback) if retry_feedback else [], sort_keys=True)
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Prompt construction (R-GEN-001/002/003/012/013).
# ---------------------------------------------------------------------------


def _make_nonce() -> str:
    # D56: a per-call random nonce, embedded in both the delimiter this
    # prompt asks the model to use and the regex that later parses it --
    # closes the one self-referential class of bug unique to this
    # component (its own source legitimately documents this delimiter
    # convention as a worked example; a fixed marker text could collide
    # with that and truncate the real file).
    return uuid.uuid4().hex


def _delimiter_instructions(nonce: str) -> str:
    return (
        "Wrap each file's content exactly as:\n\n"
        f"-----BEGIN FILE {nonce}: <path relative to gen/<component>/>-----\n"
        "<the complete, exact file content, verbatim>\n"
        f"-----END FILE {nonce}-----\n\n"
        f"Use exactly this nonce ({nonce}) on every BEGIN/END marker in "
        "your response -- it is unique to this call. This lets the caller "
        "reliably tell your real file output apart from any illustrative "
        "example of this same delimiter format your own source might "
        "legitimately need to describe in prose, since generator is the "
        "one component whose own code documents this exact convention. "
        "Do not reuse this nonce as a literal example elsewhere in your "
        "output; if your generated code needs to describe this format, "
        "describe it in prose instead of reproducing a literal worked "
        "example of the marker text."
    )


def _build_prompt(bundle: Any, retry_feedback: Optional[List[str]], nonce: str) -> str:
    parts: List[str] = [
        _SYSTEM_PROMPT,
        _delimiter_instructions(nonce),
        f"PROMPT_VERSION: {PROMPT_VERSION}",
        f"## component_id\n{bundle.component_id}",
        f"## SPEC\n{bundle.spec}",
        f"## INTERFACE\n{bundle.interface}",
        f"## CONSTRAINTS\n{bundle.constraints}",
        "## DEPENDENCY INTERFACES\n" + json.dumps(bundle.dependency_interfaces, indent=2),
        "## DEPENDENCY CONTEXT\n" + json.dumps(bundle.dependency_context, indent=2),
        "## VARS\n" + json.dumps(bundle.vars, indent=2),
        f"## GLOSSARY\n{bundle.glossary}",
    ]

    # R-GEN-013: dependency_usage, its own distinct section, only when
    # non-empty for a given dependency. Absence (an empty string for a
    # dependency with no real code yet) is not an error or refusal.
    nonempty_usage = {
        dep: usage for dep, usage in (bundle.dependency_usage or {}).items() if usage
    }
    if nonempty_usage:
        parts.append("## DEPENDENCY USAGE\n" + json.dumps(nonempty_usage, indent=2))

    # R-GEN-002: hint_code, present only in hint mode, clearly distinguished
    # from every cold spec field above -- never silently merged with them.
    if bundle.hint_code:
        parts.append(
            "## HINT_CODE (existing code -- a revision starting point "
            "only, NOT spec; distinct from every section above)\n"
            + json.dumps(bundle.hint_code, indent=2)
        )

    # R-GEN-012: retry_feedback, bare R-id list only, its own section,
    # never merged with or indistinguishable from the SpecBundle's own
    # fields.
    if retry_feedback:
        parts.append(
            "## RETRY_FEEDBACK (bare R-id list only -- a prior attempt "
            "did not satisfy exactly these; no other content)\n"
            + json.dumps(list(retry_feedback))
        )

    parts.append(
        "Respond with each file wrapped in the delimiter format above, "
        "one block per file, nothing before the first block or after "
        "the last."
    )

    return "\n\n".join(parts)


_FILE_BLOCK_TEMPLATE = (
    r"-----BEGIN FILE {nonce}: (?P<path>.*?)-----\n"
    r"(?P<content>.*?)"
    r"\n-----END FILE {nonce}-----"
)


def _parse_files(text: str, nonce: str) -> Dict[str, str]:
    pattern = re.compile(
        _FILE_BLOCK_TEMPLATE.format(nonce=re.escape(nonce)), re.DOTALL
    )
    files: Dict[str, str] = {}
    for match in pattern.finditer(text):
        path = match.group("path").strip()
        content = match.group("content")
        if path:
            files[path] = content
    return files


def _as_dict(response: Any) -> dict:
    """Adapter around llm-endpoint's complete() return value (D53) --
    interface/data/ModelResponse.md only ever fixes a JSON shape, not a
    Python type, and different regenerations of llm-endpoint have
    returned different concrete ones."""

    if isinstance(response, dict):
        return response
    if hasattr(response, "_asdict"):
        return dict(response._asdict())
    if hasattr(response, "__dict__"):
        return dict(vars(response))
    raise TypeError(f"unrecognized ModelResponse type: {type(response)!r}")


# ---------------------------------------------------------------------------
# Writing gen/<component>/ (R-GEN-009, scope).
# ---------------------------------------------------------------------------


def _strip_redundant_prefix(files: Dict[str, str], component_id: str) -> Dict[str, str]:
    """R-GEN-015 (D165): a model that restates the directory it is
    already writing into (`<component>/x.py` or `gen/<component>/x.py`)
    has that one leading prefix removed. No other path is rewritten."""
    comp_dir = _component_dir_name(component_id)
    out: Dict[str, str] = {}
    for rel_path, content in files.items():
        for prefix in (f"gen/{comp_dir}/", f"{comp_dir}/"):
            if rel_path.startswith(prefix):
                rel_path = rel_path[len(prefix):]
                break
        out[rel_path] = content
    return out


def _write_files(repo_root: Path, component_id: str, files: Dict[str, str]) -> None:
    comp_dir = _component_dir_name(component_id)
    base = (Path(repo_root) / "gen" / comp_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    for rel_path, content in files.items():
        target = (base / rel_path).resolve()
        # Defense-in-depth: never write outside gen/<component>/ for the
        # target component, regardless of what a file path in the model's
        # response claims (R-GEN-009).
        if target != base and base not in target.parents:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public library entry point.
# ---------------------------------------------------------------------------


def generate(
    bundle: Any,
    model: str,
    retry_feedback: Optional[List[str]] = None,
    *,
    repo_root: Optional[Path] = None,
    llm_backend=None,
) -> GenerationResult:
    """R-GEN-001..014. Produces exactly one candidate per call -- single-
    shot, stateless about prior attempts, no retry logic of its own
    (R-GEN-011)."""

    if repo_root is None:
        repo_root = Path.cwd()
    repo_root = Path(repo_root)

    component_id = bundle.component_id
    echoed_retry_feedback = list(retry_feedback) if retry_feedback else None

    # R-GEN-009: precondition check, resolved before any model call.
    refusal = _check_precondition(repo_root, component_id)
    if refusal is not None:
        return GenerationResult(
            component_id=component_id,
            spec_bundle_hash=bundle.spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error=None,
            refused=refusal,
            retry_feedback=echoed_retry_feedback,
        )

    cache_manager = _load_cache_manager(repo_root)

    gate_inputs_hash = _compute_gate_inputs_hash(retry_feedback)
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    # R-GEN-005: check the cache before calling any model.
    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = cached.payload
        files = payload.get("files", {})
        if files:
            if not bundle.hint_code:  # R-GEN-016: hint mode never writes gen/
                _write_files(repo_root, component_id, files)
        return GenerationResult(
            component_id=payload.get("component_id", component_id),
            spec_bundle_hash=bundle.spec_bundle_hash,
            model=payload.get("model", model),
            prompt_version=payload.get("prompt_version", PROMPT_VERSION),
            cache_hit=True,
            files=files,
            model_call_error=None,
            refused=None,
            retry_feedback=echoed_retry_feedback,
        )

    llm_endpoint = _load_llm_endpoint(repo_root)

    nonce = _make_nonce()
    prompt = _build_prompt(bundle, retry_feedback, nonce)

    # R-GEN-004: model is an explicit parameter, passed through unchanged.
    # R-GEN-011: no retry-with-backoff logic here -- a single call either
    # succeeds or comes back as a model_call_error exactly once.
    raw_response = llm_endpoint.complete(prompt, model, backend=llm_backend)
    response = _as_dict(raw_response)

    error = response.get("model_call_error")
    if error:
        # R-GEN-008: a model-call error is its own distinct failure mode,
        # never conflated with "produced code that fails verification."
        # No partial output -- gen/<component>/ is left untouched.
        return GenerationResult(
            component_id=component_id,
            spec_bundle_hash=bundle.spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error=error,
            refused=None,
            retry_feedback=echoed_retry_feedback,
        )

    files = _strip_redundant_prefix(
        _parse_files(response.get("text") or "", nonce), component_id
    )

    # R-GEN-008: a response with no file blocks produced no candidate, so
    # it is reported as a model-call error rather than an empty success.
    if not files:
        return GenerationResult(
            component_id=component_id,
            spec_bundle_hash=bundle.spec_bundle_hash,
            model=model,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error={
                "category": "empty_response",
                "message": "the model's response held no file blocks",
            },
            refused=None,
            retry_feedback=echoed_retry_feedback,
        )

    # R-GEN-006/D56: cache only non-empty results -- a response that
    # parses to zero files must never poison the cache for every future
    # call with this exact bundle hash.
    # R-GEN-016/D81: a hint-mode preview never writes gen/ or the cache.
    if files and not bundle.hint_code:
        _write_files(repo_root, component_id, files)
        payload = {
            "component_id": component_id,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "files": files,
        }
        cache_manager.put(
            cache_key,
            cache_manager.CachedResult(
                gate_type="generator",
                payload=payload,
                stored_at=cache_manager.now_iso(),
            ),
            repo_root=repo_root,
        )

    return GenerationResult(
        component_id=component_id,
        spec_bundle_hash=bundle.spec_bundle_hash,
        model=model,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        files=files,
        model_call_error=None,
        refused=None,
        retry_feedback=echoed_retry_feedback,
    )


# ---------------------------------------------------------------------------
# CLI (interface/cli.md).
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hotdocs generate")
    parser.add_argument("component_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--retry-feedback", default=None)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        return 2 if code != 0 else 0

    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()

    try:
        spec_bundle_assembler = _load_spec_bundle_assembler(repo_root)
        bundle = spec_bundle_assembler.assemble(args.component_id, repo_root)
    except Exception as exc:  # noqa: BLE001 - usage/precondition failure
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    retry_feedback = (
        [r.strip() for r in args.retry_feedback.split(",") if r.strip()]
        if args.retry_feedback
        else None
    )

    result = generate(bundle, args.model, retry_feedback, repo_root=repo_root)

    if args.format == "json":
        print(json.dumps(asdict(result), indent=2))
    elif result.model_call_error is not None:
        print(f"model_call_error: {result.model_call_error}")
    elif result.refused is not None:
        print(f"refused: {result.refused}")
    else:
        print(
            f"generated {len(result.files)} file(s) for {result.component_id} "
            f"(cache_hit={result.cache_hit})"
        )

    if result.model_call_error is not None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())