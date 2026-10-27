"""generator — bootstrap implementation.

HAND-AUTHORED BOOTSTRAP, structurally permanent like llm-endpoint (see
verification/generator/BOOTSTRAP.md): nothing could cold-regenerate the
component that does the cold-regenerating, even once this file itself
makes that possible for everything else.

Implements R-GEN-001..012: constructs a frozen, versioned prompt from
exactly a SpecBundle's fields (never anything else -- R-GEN-001),
dispatches through llm-endpoint (never holding a credential itself,
R-GEN-004), checks/writes cache-manager around the call (R-GEN-005/006),
enforces the sealed/pinned-override precondition before ever calling a
model (R-GEN-009), and writes gen/<component>/ only on a real success.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "llm-endpoint"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cache-manager"))
import llm_endpoint  # noqa: E402
import cache_manager  # noqa: E402

PROMPT_VERSION = "v4"  # D57: warn against the sys.modules dynamic-import pitfall
GATE_VERSION = "generator@1.1.0"  # D56: generate() no longer caches an empty-files result

# R-GEN-003: frozen, versioned -- any substantive edit to this text, other
# than this changelog note, MUST bump PROMPT_VERSION.
#
# D56: the fixed "-----BEGIN FILE:...-----"/"-----END FILE-----" delimiter
# was found, by a real failure, to collide with itself: asked to
# regenerate *this exact file*, a model reasonably wrote out this very
# docstring's own worked example of the delimiter as a string literal
# inside the new generator.py it produced -- and the old parser's regex
# matched that inner, illustrative "-----END FILE-----" first, truncating
# the real file well before its actual end. generator is the one
# component whose own source legitimately contains this exact text, so
# it is the one component where a fixed delimiter can never be made safe.
# A fresh, random nonce per call closes this: it cannot collide with
# anything a model writes, illustrative or otherwise, because it never
# appears anywhere before this one call generates it.
_SYSTEM_PROMPT = """You simulate exactly one thing: a cold-regen model call for ONE
component in a spec-driven pipeline. You have no tools. The only facts
you are allowed to use are the ones given to you in this turn's prompt
-- a SpecBundle (and, if present, hint_code and retry_feedback).

Hard rules:
- Cold mode (no hint_code section below): construct your answer from
  exactly the SPEC / INTERFACE / CONSTRAINTS / DEPENDENCY INTERFACES /
  DEPENDENCY CONTEXT / VARS / GLOSSARY sections. Never assume or invent
  anything about this component's "real" existing implementation,
  including anything you might otherwise recall from training -- treat
  this component as if it has never been implemented before.
- Hint mode (a HINT_CODE section is present): you may use it as a
  starting point for a revision, but keep it mentally distinct from the
  cold spec fields.
- If a RETRY_FEEDBACK section is present, it is a bare list of R-ids
  that previously failed verification -- nothing else. Pay particular
  attention to satisfying exactly those requirements correctly.
- You will never be given this component's acceptance/ criteria -- do
  not infer a specific test's shape from naming conventions.
- Output only gen/<component_id>/ file contents -- no explanation, no
  commentary, nothing else.
- If you are generating `generator`'s own code and it dynamically
  loads a dependency module from a file path per call (rather than a
  static sys.path-relative-to-file import, R-GEN-014), you MUST
  register the loaded module in sys.modules under its load-time name
  BEFORE running its code (exec_module) -- omitting this crashes on
  any dependency defining a dataclass, because dataclasses' internals
  look up sys.modules[cls.__module__] to resolve its own annotations.
  A real prior attempt chose exactly this technique, omitted this
  step, and crashed for real loading cache-manager (D57).

Output format -- emit each file exactly like this, one block per file,
nothing before the first block or after the last. {nonce} below is a
one-time token for this call only -- copy it verbatim into every BEGIN
and END marker; it will never match anything else, including any
illustrative example you might otherwise be tempted to write out
literally (if you are generating code that itself documents this exact
delimiter format, describe the format in prose instead of reproducing
this literal token sequence as a worked example):

-----BEGIN FILE {nonce}: <path relative to gen/{component_id}/>-----
<the complete, exact file content, verbatim>
-----END FILE {nonce}-----
"""


@dataclass
class GenerationResult:
    """Matches `interface/data/GenerationResult.md` exactly."""

    component_id: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict[str, str]
    model_call_error: dict[str, str] | None
    refused: str | None
    retry_feedback: list[str] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "cache_hit": self.cache_hit,
            "files": self.files,
            "model_call_error": self.model_call_error,
            "refused": self.refused,
            "retry_feedback": self.retry_feedback,
        }


def _build_prompt(bundle: Any, retry_feedback: list[str] | None) -> str:
    """R-GEN-001/002/012 -- every section clearly, distinctly labeled."""
    sections = [
        f"SPEC:\n{bundle.spec}",
        f"\nINTERFACE:\n{bundle.interface}",
        f"\nCONSTRAINTS:\n{bundle.constraints}",
        f"\nDEPENDENCY INTERFACES:\n{json.dumps(bundle.dependency_interfaces)}",
        f"\nDEPENDENCY CONTEXT:\n{json.dumps(bundle.dependency_context)}",
        f"\nDEPENDENCY USAGE (R-ASSEMBLE-011, real -- how to actually import "
        f"and call each dependency's current code; empty for a dependency "
        f"with none yet):\n{json.dumps(getattr(bundle, 'dependency_usage', {}))}",
        f"\nVARS:\n{json.dumps(bundle.vars)}",
        f"\nGLOSSARY:\n{bundle.glossary}",
    ]
    if bundle.hint_code:
        sections.append(f"\nHINT_CODE:\n{json.dumps(bundle.hint_code)}")
    if retry_feedback:
        sections.append(f"\nRETRY_FEEDBACK:\n{json.dumps(list(retry_feedback))}")
    return "\n".join(sections)


def _parse_files(text: str, nonce: str) -> dict[str, str]:
    """D56 -- the delimiter is compiled fresh per call, keyed to that
    call's own nonce, so it can never match an illustrative example of
    the (differently-nonced, or un-nonced) format a model might
    reasonably write out as part of generating this exact file."""
    pattern = re.compile(
        r"-----BEGIN FILE " + re.escape(nonce) + r": (?P<path>[^\n]+)-----\n"
        r"(?P<content>.*?)\n-----END FILE " + re.escape(nonce) + r"-----",
        re.DOTALL,
    )
    return {m.group("path").strip(): m.group("content") for m in pattern.finditer(text)}


def _as_dict(response: Any) -> dict:
    """llm-endpoint's own interface spec only ever shows `ModelResponse`
    as a JSON object shape (interface/data/ModelResponse.md) -- not a
    specific Python type. Each self-hosted regeneration of llm-endpoint
    has returned a different concrete shape for it (a dataclass with
    `.to_dict()`, D51; a plain dict, D53) -- all equally spec-conformant,
    since the spec never pinned one. This adapter lets generator depend
    on the actual JSON contract rather than whichever shape the
    currently-installed llm-endpoint happens to return."""
    if isinstance(response, dict):
        return response
    if hasattr(response, "to_dict"):
        return response.to_dict()
    return vars(response)


def _gate_inputs_hash(retry_feedback: list[str] | None) -> str:
    """R-GEN-005 -- MUST incorporate retry_feedback when present, so a
    blind call and an informed one never collide in the cache."""
    import hashlib
    serialized = json.dumps(sorted(retry_feedback) if retry_feedback else [])
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _check_refusal(component_id: str, repo_root: Path) -> str | None:
    """R-GEN-009 -- a precondition check, resolved before any model call.
    Reads the real component.md frontmatter directly (never from the
    bundle, which excludes frontmatter by construction, R-ASSEMBLE-001)
    and gen/<component>/.overrides.json. Returns a reason string or None."""
    bare_name = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    component_md = repo_root / "specs" / "components" / bare_name / "component.md"
    if component_md.is_file():
        text = component_md.read_text(encoding="utf-8")
        if re.search(r"^sealed:\s*true", text, re.MULTILINE):
            return "sealed-component"
    overrides_path = repo_root / "gen" / bare_name / ".overrides.json"
    if overrides_path.is_file():
        try:
            data = json.loads(overrides_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if data:  # any non-empty overrides declaration refuses the whole component
            return "pinned-override"
    return None


def generate(
    bundle: Any,
    model: str,
    retry_feedback: list[str] | None = None,
    *,
    repo_root: Path | None = None,
    llm_backend=None,
) -> GenerationResult:
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()

    refusal = _check_refusal(bundle.component_id, repo_root)
    if refusal is not None:
        return GenerationResult(
            component_id=bundle.component_id, model=model, prompt_version=PROMPT_VERSION,
            cache_hit=False, files={}, model_call_error=None, refused=refusal,
            retry_feedback=retry_feedback,
        )

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=bundle.spec_bundle_hash,
        gate_inputs_hash=_gate_inputs_hash(retry_feedback),
        gate_version=GATE_VERSION,
        model_pin=model,
    )
    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if isinstance(cached, cache_manager.CachedResult):
        payload = cached.payload
        return GenerationResult(
            component_id=payload["component_id"], model=payload["model"],
            prompt_version=payload["prompt_version"], cache_hit=True,
            files=payload["files"], model_call_error=None, refused=None,
            retry_feedback=retry_feedback,
        )

    prompt = _build_prompt(bundle, retry_feedback)
    nonce = uuid.uuid4().hex
    raw_response = llm_endpoint.complete(
        prompt, model, backend=llm_backend,
        system_prompt=_SYSTEM_PROMPT.format(component_id=bundle.component_id, nonce=nonce),
    )
    response = _as_dict(raw_response)

    if response.get("model_call_error") is not None:
        return GenerationResult(
            component_id=bundle.component_id, model=model, prompt_version=PROMPT_VERSION,
            cache_hit=False, files={}, model_call_error=response["model_call_error"],
            refused=None, retry_feedback=retry_feedback,
        )

    files = _parse_files(response.get("text") or "", nonce)
    result = GenerationResult(
        component_id=bundle.component_id, model=model, prompt_version=PROMPT_VERSION,
        cache_hit=False, files=files, model_call_error=None, refused=None,
        retry_feedback=retry_feedback,
    )

    # R-GEN-006 -- write-through on success only. D56: a response that
    # parsed to zero files is not a success -- GenerationResult.md
    # requires exactly one of files (non-empty)/model_call_error/refused
    # populated, and caching an empty-files result as if it were valid
    # would permanently poison every future call for this exact bundle
    # hash (found this way for real: an earlier call's degenerate empty
    # result was cached and would have been silently replayed forever).
    if files:
        cache_manager.put(
            cache_key,
            cache_manager.CachedResult(gate_type="generator", payload=result.to_dict(), stored_at=cache_manager.now_iso()),
            repo_root=repo_root,
        )
    return result


def write_output(result: GenerationResult, repo_root: Path) -> None:
    """Writes `gen/<component>/` only for a real success -- never a
    partial tree on error (constraints.md)."""
    if not result.files:
        return
    bare_name = result.component_id[len("comp-"):] if result.component_id.startswith("comp-") else result.component_id
    target_dir = Path(repo_root) / "gen" / bare_name
    for rel_path, content in result.files.items():
        file_path = target_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
