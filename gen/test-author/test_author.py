"""Authors the test code for one `generated-test`-kind acceptance criterion."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import secrets
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROMPT_VERSION = "v3"
GATE_VERSION = "generated_test@1.0.0"

DEPENDENCY_CONVENTION_INSTRUCTION = """No component in this corpus is statically importable by another. A
component's own code resolves each dependency dynamically, at runtime,
from `<repo_root>/gen/<dependency-slug>/<module_name>.py` (a flat module)
or `<repo_root>/gen/<dependency-slug>/__init__.py` (a package) -- never a
name Python's own import system would find on sys.path without that
explicit file-path resolution, and never a name sys.modules injection or
unittest.mock.patch("<name>...") can intercept by itself.

If the test you are writing needs to fake a dependency's behavior, you
MUST write a fake module file at that exact real path, under a fresh
temporary repo_root, and pass that repo_root through to the function
under test, letting the component's own loader find it naturally. Do
not attempt to patch an import name directly -- the loader described
above will never see it.

The one correctness-critical step, as a literal worked example:

    import importlib.util
    import sys
    from pathlib import Path

    def install_fake_module(repo_root: Path, slug: str, module_name: str, source: str):
        module_dir = repo_root / "gen" / slug
        module_dir.mkdir(parents=True, exist_ok=True)
        module_path = module_dir / f"{module_name}.py"
        module_path.write_text(source)
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # MUST happen before exec_module below
        spec.loader.exec_module(module)
        return module

The sys.modules registration MUST happen before exec_module is called:
a dataclass's class body resolves its own module via
sys.modules[__module__] while the class body executes, so a loader
missing this step still looks correct but fails on any dependency whose
own code defines a dataclass."""


@dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: Optional[Dict[str, str]]
    model_call_error: Optional[Dict[str, Any]]


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _criterion_filename(criterion_id: str) -> str:
    return f"test_{criterion_id.lower().replace('-', '_')}.py"


def _hash_json(obj: Any) -> str:
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _criterion_content_hash(bundle) -> str:
    return _hash_json({
        "component_id": bundle.component_id,
        "criterion_id": bundle.criterion_id,
        "covers": bundle.covers,
        "criterion_text": bundle.criterion_text,
        "requirement_text": bundle.requirement_text,
        "interface": bundle.interface,
        "glossary": bundle.glossary,
    })


def _gate_inputs_hash(seed: int) -> str:
    return _hash_json({"seed": seed, "prompt_version": PROMPT_VERSION})


def _load_dependency(repo_root: Path, slug: str, module_name: str):
    base = repo_root / "gen" / slug
    flat = base / f"{module_name}.py"
    pkg = base / "__init__.py"
    if flat.is_file():
        path = flat
    elif pkg.is_file():
        path = pkg
    else:
        raise ImportError(f"cannot find dependency module {module_name!r} for slug {slug!r} under {base}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _build_prompt(bundle, nonce: str) -> str:
    return f"""You are authoring an automated test file for exactly one acceptance
criterion in a spec-driven software pipeline. The test you write will be
run, independently, to check whether the target component actually
satisfies this criterion.

You have NO tool access and NO file access of any kind. You cannot
explore, read, or guess at the target component's real implementation.
Produce your answer using only the material given below in this
prompt -- nothing invented or explored about the target component's
real implementation. The target component's actual source code has been
deliberately withheld from you; you are given its public interface
contract only.

== Target component ==
component_id: {bundle.component_id}

== Criterion to test ==
criterion_id: {bundle.criterion_id}
covers: {bundle.covers}

Criterion (Given/When/Then):
{bundle.criterion_text}

== Requirement text ({bundle.covers}) ==
{bundle.requirement_text}

== Target component interface (its public contract only) ==
{bundle.interface}

== Glossary ==
{bundle.glossary}

== Dependency-resolution convention for this corpus ==
{DEPENDENCY_CONVENTION_INSTRUCTION}

== Output format ==
Produce exactly one test file that exercises the target component's
public interface as described above and asserts the criterion's Then
clause. Wrap its complete, exact content between these markers, with
nothing else between them:

-----BEGIN FILE {nonce}-----
<the complete, exact test file content, verbatim>
-----END FILE {nonce}-----

Output nothing else between those two marker lines. You may write brief
commentary outside the markers if you wish, but the content between the
markers must be the complete, exact file content and nothing more.
"""


def _extract_file_content(text: str, nonce: str) -> Optional[str]:
    pattern = re.compile(
        r"-----BEGIN FILE " + re.escape(nonce) + r"-----\r?\n(.*?)\r?\n-----END FILE " + re.escape(nonce) + r"-----",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1)


def author_test(
    bundle,
    model: str,
    seed: int = 0,
    *,
    repo_root: Path = None,
    llm_backend=None,
) -> TestAuthoringResult:
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()

    cache_manager = _load_dependency(repo_root, "cache-manager", "cache_manager")
    llm_endpoint = _load_dependency(repo_root, "llm-endpoint", "llm_endpoint")

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=_criterion_content_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(seed),
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = cached.payload
        file_record = dict(payload["file"])
        _write_file(repo_root, file_record)
        return TestAuthoringResult(
            component_id=payload["component_id"],
            criterion_id=payload["criterion_id"],
            model=payload["model"],
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=True,
            file=file_record,
            model_call_error=None,
        )

    nonce = secrets.token_hex(16)
    prompt = _build_prompt(bundle, nonce)
    response = llm_endpoint.complete(prompt, model, backend=llm_backend)

    model_call_error = response.get("model_call_error")
    if model_call_error:
        return TestAuthoringResult(
            component_id=bundle.component_id,
            criterion_id=bundle.criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=dict(model_call_error),
        )

    text = response.get("text") or ""
    content = _extract_file_content(text, nonce)
    if content is None:
        return TestAuthoringResult(
            component_id=bundle.component_id,
            criterion_id=bundle.criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={
                "category": "malformed_response",
                "message": "no matching BEGIN/END FILE marker pair found in model response",
            },
        )

    rel_path = f"verification/{_slug(bundle.component_id)}/generated-test/{_criterion_filename(bundle.criterion_id)}"
    file_record = {"path": rel_path, "content": content}

    cached_result = cache_manager.CachedResult(
        gate_type="generated_test",
        payload={
            "component_id": bundle.component_id,
            "criterion_id": bundle.criterion_id,
            "model": model,
            "file": file_record,
        },
        stored_at=cache_manager.now_iso(),
    )

    _write_file(repo_root, file_record)
    cache_manager.put(cache_key, cached_result, repo_root=repo_root)

    return TestAuthoringResult(
        component_id=bundle.component_id,
        criterion_id=bundle.criterion_id,
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file=file_record,
        model_call_error=None,
    )


def _write_file(repo_root: Path, file_record: Dict[str, str]) -> None:
    abs_path = repo_root / file_record["path"]
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(file_record["content"])


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="hotdocs author-test")
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = _parse_args(argv)
    except SystemExit as exc:
        return exc.code if exc.code is not None else 2

    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()

    try:
        spec_bundle_assembler = _load_dependency(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
        bundle = spec_bundle_assembler.assemble_criterion(args.component_id, args.criterion_id, repo_root)
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