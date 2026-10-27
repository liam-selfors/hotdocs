"""
test_author
============

Implements the `comp-test-author` component: authors the test code for one
`generated-test`-kind acceptance criterion from spec prose alone (a
`CriterionBundle`), with no access to the implementation under test.

This module is generated from the component's SpecBundle (`requirements/`,
`interface/`, `constraints.md`). It does not read, and must never read,
the target component's own `gen/<component>/` source (R-AUTHOR-002) --
only the `interface/` content carried inside the `CriterionBundle` it is
handed.

Public surface (see `interface/library.md` and `interface/cli.md`):

    author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None)
        -> TestAuthoringResult

    main() -- CLI entry point for `hotdocs author-test ...`.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Prompt version recorded on every TestAuthoringResult -- bumping this is
#: how a prompt-wording change is made visible to the cache key machinery
#: (it participates in gate_inputs_hash, below).
PROMPT_VERSION = "v1"

#: R-AUTHOR-004 -- the <gate_type>@<semver> prefix MUST be exactly
#: "generated_test", matching cache-manager's own gate_type registry
#: (interface/data/CachedResult.md) -- never "test_author".
GATE_VERSION = "generated_test@1.0.0"

#: Maps an importable dependency module name to the hyphenated directory
#: name it lives under, per the corpus-wide `gen/<component>/` layout
#: convention (component id dash-form directory, underscore-form module).
_DEP_DIR_NAMES = {
    "cache_manager": "cache-manager",
    "llm_endpoint": "llm-endpoint",
    "spec_bundle_assembler": "spec-bundle-assembler",
}


# ---------------------------------------------------------------------------
# Data shapes (interface/data/*.md)
# ---------------------------------------------------------------------------


@dataclass
class CriterionBundle:
    """Matches interface/data/CriterionBundle.md exactly.

    Deliberately narrow: no field here ever carries the target
    component's `gen/<component>/` source (R-AUTHOR-002).
    """

    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str


@dataclass
class TestAuthoringResult:
    """Matches interface/data/TestAuthoringResult.md exactly.

    `model_call_error` and `file` are the mutually-exclusive-ish pair
    distinguishing "could not author a test" (R-AUTHOR-007) from a
    successfully authored test: on a model-call error, `file` is `None`
    and nothing is written to disk or to the cache.
    """

    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: Optional[Dict[str, str]]
    model_call_error: Optional[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Dependency loading
#
# `cache-manager`, `llm-endpoint`, and (CLI-only) `spec-bundle-assembler`
# live under hyphenated `gen/<dep>/` directories and are not reachable by a
# plain relative import from this file. We resolve them dynamically at
# call time, trying a normal `import` first (in case the host environment
# already placed them on sys.path) and falling back to loading the module
# straight from its file on disk.
#
# Per this generation run's instructions: when loading a dependency module
# from a file path, the loaded module object MUST be registered in
# sys.modules under its load-time name BEFORE exec_module runs -- skipping
# that step breaks any dependency module defining a dataclass, since a
# dataclass's internals resolve sys.modules[cls.__module__] while the class
# body executes.
# ---------------------------------------------------------------------------


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot build an import spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # MUST happen before exec_module.
    spec.loader.exec_module(module)
    return module


def _candidate_roots(explicit_root: Path) -> List[Path]:
    """Roots to search for a `gen/<dep>/...` dependency module.

    The explicit `repo_root` first, then any ancestor of this file that
    itself contains a `gen/` directory (covers the case where this module
    is executed from a checkout laid out differently than the repo the
    caller is verifying).
    """

    candidates = [Path(explicit_root)]
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "gen").is_dir():
            candidates.append(parent)

    seen = set()
    ordered: List[Path] = []
    for candidate in candidates:
        resolved = Path(candidate)
        try:
            resolved = resolved.resolve()
        except OSError:
            pass
        if resolved not in seen:
            seen.add(resolved)
            ordered.append(candidate)
    return ordered


def _import_dependency(repo_root: Path, module_name: str):
    if module_name in sys.modules:
        return sys.modules[module_name]

    try:
        return importlib.import_module(module_name)
    except ImportError:
        pass

    dep_dir_name = _DEP_DIR_NAMES.get(module_name, module_name)

    for root in _candidate_roots(repo_root):
        base = Path(root) / "gen" / dep_dir_name
        candidates = [
            base / f"{module_name}.py",
            base / module_name / "__init__.py",
        ]
        for candidate in candidates:
            if candidate.exists():
                return _load_module_from_path(module_name, candidate)

    raise ImportError(
        f"Could not locate dependency module '{module_name}' under any "
        f"'gen/{dep_dir_name}/' beneath {repo_root}"
    )


def _cache_manager(repo_root: Path):
    return _import_dependency(repo_root, "cache_manager")


def _llm_endpoint(repo_root: Path):
    return _import_dependency(repo_root, "llm_endpoint")


def _spec_bundle_assembler(repo_root: Path):
    return _import_dependency(repo_root, "spec_bundle_assembler")


# ---------------------------------------------------------------------------
# Component-id / path helpers (glossary: component id / slug)
# ---------------------------------------------------------------------------


def _component_slug(component_id: str) -> str:
    """Strip the `comp-` prefix, per the glossary's component-id rule.

    Load-bearing: every path built from a component_id (here,
    `verification/<slug>/generated-test/...`, R-AUTHOR-006) MUST use the
    bare slug, never the full `comp-<slug>` id.
    """

    prefix = "comp-"
    if component_id.startswith(prefix):
        return component_id[len(prefix):]
    return component_id


def _test_filename(criterion_id: str) -> str:
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _relative_output_path(component_id: str, criterion_id: str) -> str:
    """R-AUTHOR-006 -- written only under verification/<component>/
    generated-test/, never under gen/, never into criterion-compiler's own
    output directory (a sibling, not this one)."""

    slug = _component_slug(component_id)
    filename = _test_filename(criterion_id)
    return f"verification/{slug}/generated-test/{filename}"


def _write_output_file(repo_root: Path, file_obj: Dict[str, str]) -> None:
    target = Path(repo_root) / file_obj["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(file_obj["content"], encoding="utf-8")


# ---------------------------------------------------------------------------
# Hashing / cache key construction (R-AUTHOR-004)
# ---------------------------------------------------------------------------


def _sha256_of(obj: Any) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _criterion_content_hash(bundle: CriterionBundle) -> str:
    payload = {
        "component_id": bundle.component_id,
        "criterion_id": bundle.criterion_id,
        "covers": bundle.covers,
        "criterion_text": bundle.criterion_text,
        "requirement_text": bundle.requirement_text,
        "interface": bundle.interface,
        "glossary": bundle.glossary,
    }
    return _sha256_of(payload)


def _gate_inputs_hash(seed: int) -> str:
    # Inputs to *this* gate call that are not already part of the
    # criterion's own content: the seed requested and the prompt version
    # in force, so a prompt-wording change invalidates prior cache
    # entries even for an unchanged criterion.
    return _sha256_of({"seed": seed, "prompt_version": PROMPT_VERSION})


def _build_cache_key(cache_manager_mod, bundle: CriterionBundle, model: str, seed: int):
    return cache_manager_mod.CacheKey(
        spec_bundle_hash=_criterion_content_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(seed),
        gate_version=GATE_VERSION,
        model_pin=model,
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt(bundle: CriterionBundle) -> str:
    return (
        "You are authoring an automated test for exactly one acceptance "
        "criterion. You have the criterion's own Given/When/Then prose, "
        "the requirement it covers, and the target component's public "
        "interface contract -- and nothing else. In particular, you do "
        "not have access to the target component's implementation "
        "source. Write a single, self-contained test exercising the "
        "component's public interface as described, asserting the "
        "criterion's Then clause. Output only the test code.\n\n"
        f"## Component\n{bundle.component_id}\n\n"
        f"## Criterion {bundle.criterion_id} (covers {bundle.covers})\n"
        f"{bundle.criterion_text}\n\n"
        f"## Covered requirement text ({bundle.covers})\n"
        f"{bundle.requirement_text}\n\n"
        "## Target component interface contract\n"
        f"{bundle.interface}\n\n"
        "## Glossary\n"
        f"{bundle.glossary}\n"
    )


# ---------------------------------------------------------------------------
# Public library entry point
# ---------------------------------------------------------------------------


def author_test(
    bundle: CriterionBundle,
    model: str,
    seed: int = 0,
    *,
    repo_root: Optional[Path] = None,
    llm_backend=None,
) -> TestAuthoringResult:
    """Author the test code for one `generated-test`-kind criterion.

    R-AUTHOR-003: `model` is used exactly as given -- the canonical model
    alone, never an implicit default, never a second candidate tried on
    the side.

    R-AUTHOR-004/005: checks `cache-manager` first; on a miss, calls the
    model via `llm-endpoint`, writes the result to the cache before
    returning, then writes the test file to disk.

    R-AUTHOR-007: a model-call error is returned as a distinct outcome
    (`model_call_error` populated, `file` is `None`) -- never raised as
    an exception, and never written to cache or to disk (constraints.md's
    "no silent partial output").
    """

    resolved_repo_root = Path(repo_root) if repo_root is not None else Path.cwd()

    cache_manager_mod = _cache_manager(resolved_repo_root)

    cache_key = _build_cache_key(cache_manager_mod, bundle, model, seed)
    cached = cache_manager_mod.get(cache_key, repo_root=resolved_repo_root)

    if not isinstance(cached, cache_manager_mod.Miss):
        payload = cached.payload
        return TestAuthoringResult(
            component_id=bundle.component_id,
            criterion_id=bundle.criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=True,
            file=payload["file"],
            model_call_error=None,
        )

    llm_endpoint_mod = _llm_endpoint(resolved_repo_root)
    prompt = _build_prompt(bundle)

    response = llm_endpoint_mod.complete(prompt, model, backend=llm_backend)

    model_call_error = response.get("model_call_error")
    if model_call_error is not None:
        # R-AUTHOR-007 / constraints.md: distinct failure mode, nothing
        # written to cache or to verification/<component>/generated-test/.
        return TestAuthoringResult(
            component_id=bundle.component_id,
            criterion_id=bundle.criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=model_call_error,
        )

    code = response.get("text") or ""
    file_obj = {"path": _relative_output_path(bundle.component_id, bundle.criterion_id), "content": code}

    result = TestAuthoringResult(
        component_id=bundle.component_id,
        criterion_id=bundle.criterion_id,
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file=file_obj,
        model_call_error=None,
    )

    cache_payload = {
        "component_id": result.component_id,
        "criterion_id": result.criterion_id,
        "model": result.model,
        "seed": result.seed,
        "prompt_version": result.prompt_version,
        "file": result.file,
    }
    cache_manager_mod.put(
        cache_key,
        cache_manager_mod.CachedResult(
            gate_type="generated_test",
            payload=cache_payload,
            stored_at=cache_manager_mod.now_iso(),
        ),
        repo_root=resolved_repo_root,
    )

    _write_output_file(resolved_repo_root, file_obj)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hotdocs author-test")
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser


def _cli_main(argv: Optional[List[str]] = None) -> int:
    parser = _build_arg_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse already wrote a usage message; normalize to exit code 2.
        code = exc.code if isinstance(exc.code, int) else 2
        return 2 if code != 0 else 0

    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()

    try:
        sba_mod = _spec_bundle_assembler(repo_root)
    except ImportError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    try:
        bundle = sba_mod.assemble_criterion(args.component_id, args.criterion_id, repo_root)
    except Exception as exc:  # noqa: BLE001 - any assembly failure is a usage error here
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    result = author_test(
        bundle,
        args.model,
        args.seed,
        repo_root=repo_root,
    )

    if result.model_call_error is not None:
        if args.format == "json":
            print(json.dumps(asdict(result)))
        else:
            print(f"model call error: {result.model_call_error}")
        return 1

    if args.format == "json":
        print(json.dumps(asdict(result)))
    else:
        print(f"wrote {result.file['path']} (cache_hit={result.cache_hit})")
    return 0


def main(argv: Optional[List[str]] = None) -> None:
    raise SystemExit(_cli_main(argv))


if __name__ == "__main__":
    main()