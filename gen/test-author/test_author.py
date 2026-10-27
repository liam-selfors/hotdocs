"""Authors the test code for one generated-test acceptance criterion."""

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
from typing import Any

PROMPT_VERSION = "v4"
GATE_TYPE = "generated_test"
GATE_VERSION = f"{GATE_TYPE}@1.0.0"


@dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: dict | None
    model_call_error: dict | None


def _load_dependency(repo_root: Path, slug: str):
    module_name = slug.replace("-", "_")
    base = Path(repo_root) / "gen" / slug
    flat_path = base / f"{module_name}.py"
    pkg_path = base / "__init__.py"
    if flat_path.is_file():
        path = flat_path
    elif pkg_path.is_file():
        path = pkg_path
    else:
        raise ImportError(f"cannot resolve dependency {slug!r} under {base}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _field(bundle: Any, name: str):
    if hasattr(bundle, name):
        return getattr(bundle, name)
    return bundle[name]


def _component_slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _criterion_filename(criterion_id: str) -> str:
    return f"test_{criterion_id.lower().replace('-', '_')}.py"


def _hash_json(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _criterion_content_hash(bundle: Any) -> str:
    return _hash_json({
        "component_id": _field(bundle, "component_id"),
        "criterion_id": _field(bundle, "criterion_id"),
        "covers": _field(bundle, "covers"),
        "criterion_text": _field(bundle, "criterion_text"),
        "requirement_text": _field(bundle, "requirement_text"),
        "interface": _field(bundle, "interface"),
        "glossary": _field(bundle, "glossary"),
    })


def _gate_inputs_hash(seed: int) -> str:
    return _hash_json({"seed": seed, "prompt_version": PROMPT_VERSION})


def _build_prompt(bundle: Any, nonce: str) -> str:
    component_id = _field(bundle, "component_id")
    criterion_id = _field(bundle, "criterion_id")
    covers = _field(bundle, "covers")
    criterion_text = _field(bundle, "criterion_text")
    requirement_text = _field(bundle, "requirement_text")
    interface = _field(bundle, "interface")
    glossary = _field(bundle, "glossary")
    slug = _component_slug(component_id)
    module_name = slug.replace("-", "_")

    return f"""You are authoring an automated test for one acceptance criterion of a
software component, from spec prose alone. You have no tool access and no
file access of any kind. Produce your answer using only the content given
in this prompt -- nothing invented or explored about the target
component's real implementation.

Target component: {component_id} (module name on PYTHONPATH: {module_name})

Criterion under test: {criterion_id}
Covers requirement: {covers}

=== Criterion (Given/When/Then) ===
{criterion_text}

=== Covered requirement's own text ===
{requirement_text}

=== Target component's interface contract ===
{interface}

=== Glossary ===
{glossary}

=== Your task ===
Write a single Python test file that exercises {component_id}'s public
interface as described above, and asserts the criterion's Then clause.

Import the component under test with a plain import statement, e.g.
"import {module_name}" or "from {module_name} import ..." -- the test
always runs with this component's own gen/{slug}/ directory on
PYTHONPATH, so Python's own import system already resolves this
correctly whether the component is a flat module or a package. Never
write a custom loader for the component under test itself.

=== Dependency-resolution convention (fixed, applies to every component
in this corpus) ===
No dependency is statically importable. The component under test resolves
each of its own dependencies dynamically, at runtime, from
"<repo_root>/gen/<dependency-slug>/<module_name>.py" (flat module shape)
or "<repo_root>/gen/<dependency-slug>/__init__.py" (package shape) --
never a name "sys.modules" injection or "unittest.mock.patch" by name can
intercept by itself. "module_name" is the dependency's own slug with
hyphens replaced by underscores -- never a literal "__init__" or any
other placeholder.

If your test needs to fake a dependency's behavior, write a fake module
file under a fresh temporary repo_root and pass that repo_root through to
the function under test, letting the component's own loader find it
naturally. Always write the fake in the flat-module shape, never the
package shape, regardless of which shape the real dependency happens to
use elsewhere:

    fake_dir = tmp_repo_root / "gen" / "<dependency-slug>"
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "<module_name>.py").write_text(FAKE_SOURCE)

The one correctness-critical step when the component under test loads a
dependency module from a file path at runtime: the freshly created module
object MUST be registered in sys.modules under its load-time name BEFORE
exec_module is called on it, not after:

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module   # before exec_module, not after
    spec.loader.exec_module(module)

Omitting that pre-registration step produces a plausible-looking loader
that still fails on any dependency whose own code defines a dataclass,
since a dataclass's class body resolves its own module via
sys.modules[__module__] while executing.

=== Output format (required) ===
Wrap your test file's complete, exact content exactly as:

-----BEGIN FILE {nonce}-----
<the complete, exact test file content, verbatim>
-----END FILE {nonce}-----

Output nothing else outside those markers -- no markdown code fence, no
narration, nothing before the first marker or after the last.
"""


def _extract_file(text: str, nonce: str) -> str | None:
    pattern = re.compile(
        re.escape(f"-----BEGIN FILE {nonce}-----")
        + r"\n(.*?)\n"
        + re.escape(f"-----END FILE {nonce}-----"),
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1)


def author_test(
    bundle: Any,
    model: str,
    seed: int = 0,
    *,
    repo_root: Path | None = None,
    llm_backend=None,
) -> TestAuthoringResult:
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()

    cache_manager = _load_dependency(repo_root, "cache-manager")
    llm_endpoint = _load_dependency(repo_root, "llm-endpoint")

    component_id = _field(bundle, "component_id")
    criterion_id = _field(bundle, "criterion_id")

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=_criterion_content_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(seed),
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = cached.payload
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=True,
            file=payload["file"],
            model_call_error=None,
        )

    nonce = uuid.uuid4().hex
    prompt = _build_prompt(bundle, nonce)

    response = llm_endpoint.complete(prompt, model, backend=llm_backend)
    error = response.get("model_call_error")
    if error:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=error,
        )

    file_content = _extract_file(response.get("text") or "", nonce)
    if file_content is None:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={
                "category": "malformed_response",
                "message": "no BEGIN/END FILE marker pair found in model response",
            },
        )

    slug = _component_slug(component_id)
    rel_path = f"verification/{slug}/generated-test/{_criterion_filename(criterion_id)}"
    file_obj = {"path": rel_path, "content": file_content}

    payload = {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "file": file_obj,
    }
    cache_manager.put(
        cache_key,
        cache_manager.CachedResult(
            gate_type=GATE_TYPE,
            payload=payload,
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=repo_root,
    )

    out_path = repo_root / rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(file_content)

    return TestAuthoringResult(
        component_id=component_id,
        criterion_id=criterion_id,
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file=file_obj,
        model_call_error=None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hotdocs author-test")
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()

    try:
        spec_bundle_assembler = _load_dependency(repo_root, "spec-bundle-assembler")
        bundle = spec_bundle_assembler.assemble_criterion(
            args.component_id, args.criterion_id, repo_root
        )
    except Exception as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    result = author_test(bundle, args.model, args.seed, repo_root=repo_root)

    if args.format == "json":
        print(json.dumps(asdict(result)))
    elif result.model_call_error:
        print(f"model call error: {result.model_call_error}", file=sys.stderr)
    else:
        print(f"wrote {result.file['path']} (cache_hit={result.cache_hit})")

    return 1 if result.model_call_error else 0


if __name__ == "__main__":
    sys.exit(main())