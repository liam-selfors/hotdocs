"""Authors a `generated-test`-kind acceptance criterion's test code from spec
prose alone, via an injectable model backend. See specs/components/test-author/."""

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

PROMPT_VERSION = "v2"

# cache-manager's gate_type registry has no `test_author` entry: this prefix
# names the artifact kind ("generated_test"), never this producing component.
GATE_VERSION = "generated_test@1.0.0"


class AuthoringError(Exception):
    pass


def _load_module(repo_root: Path, slug: str, module_name: str):
    if module_name in sys.modules:
        return sys.modules[module_name]
    comp_dir = Path(repo_root) / "gen" / slug
    flat_path = comp_dir / f"{module_name}.py"
    pkg_path = comp_dir / module_name / "__init__.py"
    if flat_path.is_file():
        source_path = flat_path
    elif pkg_path.is_file():
        source_path = pkg_path
    else:
        raise ImportError(
            f"Cannot locate module '{module_name}' under {comp_dir} "
            f"(looked for {flat_path} and {pkg_path})"
        )
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    module = importlib.util.module_from_spec(spec)
    # Must be registered before exec_module: dataclasses defined in the
    # loaded module resolve their own annotations via sys.modules[__module__]
    # while their class body executes.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@dataclasses.dataclass
class FileOutput:
    path: str
    content: str


@dataclasses.dataclass
class ModelCallError:
    category: str
    message: str


@dataclasses.dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: Optional[FileOutput]
    model_call_error: Optional[ModelCallError]


def _slug_for(component_id: str) -> str:
    return component_id[len("comp-") :] if component_id.startswith("comp-") else component_id


def _output_path(component_id: str, criterion_id: str) -> str:
    slug = _slug_for(component_id)
    filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    return f"verification/{slug}/generated-test/{filename}"


def _write_file(repo_root: Path, file_output: FileOutput) -> None:
    full_path = Path(repo_root) / file_output.path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(file_output.content, encoding="utf-8")


def _build_prompt(bundle: Any, nonce: str) -> str:
    return f"""You are authoring an automated test for one acceptance criterion of a software component, based solely on the specification material given below.

You have no tool access and no file access. You cannot inspect the target component's real implementation, run commands, browse any repository, or invent anything about how it is really built. Produce your answer using only the content given in this prompt.

Component: {bundle.component_id}
Criterion: {bundle.criterion_id}
Covers requirement: {bundle.covers}

## Criterion (Given/When/Then)

{bundle.criterion_text}

## Covered requirement text

{bundle.requirement_text}

## Target component interface

{bundle.interface}

## Glossary

{bundle.glossary}

Write a single Python test file that exercises the component's public interface as described above and asserts the criterion's Then clause.

Wrap the complete, exact content of that test file -- and nothing else -- between these exact markers, with nothing before the BEGIN marker and nothing after the END marker (no narration, no markdown code fence):

-----BEGIN FILE {nonce}-----
<the complete, exact test file content, verbatim>
-----END FILE {nonce}-----
"""


def _extract_file_content(text: str, nonce: str) -> Optional[str]:
    begin_marker = f"-----BEGIN FILE {nonce}-----"
    end_marker = f"-----END FILE {nonce}-----"
    start = text.find(begin_marker)
    if start == -1:
        return None
    start += len(begin_marker)
    end = text.find(end_marker, start)
    if end == -1:
        return None
    return text[start:end].strip("\n")


def _criterion_hash(bundle: Any) -> str:
    payload = {
        "component_id": bundle.component_id,
        "criterion_id": bundle.criterion_id,
        "covers": bundle.covers,
        "criterion_text": bundle.criterion_text,
        "requirement_text": bundle.requirement_text,
        "interface": bundle.interface,
        "glossary": bundle.glossary,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _gate_inputs_hash(seed: int) -> str:
    payload = {"seed": seed, "prompt_version": PROMPT_VERSION}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def author_test(
    bundle: Any,
    model: str,
    seed: int = 0,
    *,
    repo_root: Optional[Path] = None,
    llm_backend=None,
) -> TestAuthoringResult:
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
    cache_manager = _load_module(repo_root, "cache-manager", "cache_manager")

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=_criterion_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(seed),
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = cached.payload
        file_output = FileOutput(path=payload["file"]["path"], content=payload["file"]["content"])
        _write_file(repo_root, file_output)
        return TestAuthoringResult(
            component_id=payload["component_id"],
            criterion_id=payload["criterion_id"],
            model=payload["model"],
            seed=payload.get("seed", seed),
            prompt_version=payload.get("prompt_version", PROMPT_VERSION),
            cache_hit=True,
            file=file_output,
            model_call_error=None,
        )

    llm_endpoint = _load_module(repo_root, "llm-endpoint", "llm_endpoint")

    nonce = uuid.uuid4().hex
    prompt = _build_prompt(bundle, nonce)
    response = llm_endpoint.complete(prompt, model, backend=llm_backend)

    error = response.get("model_call_error")
    if error:
        return TestAuthoringResult(
            component_id=bundle.component_id,
            criterion_id=bundle.criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=ModelCallError(
                category=error.get("category", "unknown"),
                message=error.get("message", ""),
            ),
        )

    content = _extract_file_content(response.get("text") or "", nonce)
    if content is None:
        return TestAuthoringResult(
            component_id=bundle.component_id,
            criterion_id=bundle.criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=ModelCallError(
                category="malformed_response",
                message="Response did not contain a matching BEGIN/END FILE marker pair.",
            ),
        )

    file_output = FileOutput(path=_output_path(bundle.component_id, bundle.criterion_id), content=content)
    _write_file(repo_root, file_output)

    cache_manager.put(
        cache_key,
        cache_manager.CachedResult(
            gate_type="generated_test",
            payload={
                "component_id": bundle.component_id,
                "criterion_id": bundle.criterion_id,
                "model": model,
                "seed": seed,
                "prompt_version": PROMPT_VERSION,
                "file": {"path": file_output.path, "content": file_output.content},
            },
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=repo_root,
    )

    return TestAuthoringResult(
        component_id=bundle.component_id,
        criterion_id=bundle.criterion_id,
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file=file_output,
        model_call_error=None,
    )


def _result_to_dict(result: TestAuthoringResult) -> Dict[str, Any]:
    return dataclasses.asdict(result)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="hotdocs author-test")
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()

    try:
        spec_bundle_assembler = _load_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
        bundle = spec_bundle_assembler.assemble_criterion(args.component_id, args.criterion_id, repo_root)
    except Exception as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    result = author_test(bundle, args.model, args.seed, repo_root=repo_root)

    if args.format == "json":
        print(json.dumps(_result_to_dict(result), indent=2))
    elif result.model_call_error:
        print(f"model call error: {result.model_call_error.category}: {result.model_call_error.message}", file=sys.stderr)
    else:
        print(f"wrote {result.file.path} (cache_hit={result.cache_hit})")

    return 1 if result.model_call_error else 0


if __name__ == "__main__":
    sys.exit(main())