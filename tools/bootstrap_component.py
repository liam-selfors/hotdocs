#!/usr/bin/env python3
"""Mechanical, deterministic generate-verify-swap driver.

HAND-AUTHORED REPO TOOL (SPEC_GUIDELINES.md section 1, `tools/`), not a
spec-driven component. Used to cold-generate this repository's own
components in an isolated sandbox before the real `component-gate-runner`
existed, and still the way a component is landed here: it differs from
`hotdocs generate` in that it never writes provenance and swaps the
verified result into this repository's `gen/` and `verification/`. Never touches the real repo's gen/ or
verification/ for a component until that component's own candidate has
passed full verification in an isolated sandbox. On any failure, the
real repo tree is left byte-for-byte untouched -- no partial, no stale
sibling files, nothing to manually clean up.

Usage:
    python bootstrap_component.py <component-id> --model=<model> \
        [--seed=N] [--retry-feedback=R-id,R-id,...] [--keep-sandbox]

Exit 0 on a verified swap, 1 on any failure (nothing swapped), 2 on
usage error.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

REAL_REPO = Path(__file__).resolve().parents[1]

for _dep_dir in ("spec-bundle-assembler", "generator", "verifier-orchestrator", "test-author", "license-scanner", "secret-scanner"):
    sys.path.insert(0, str(REAL_REPO / "gen" / _dep_dir))

import spec_bundle_assembler  # noqa: E402
import generator  # noqa: E402
import verifier_orchestrator  # noqa: E402
import test_author  # noqa: E402
import license_scanner  # noqa: E402
import secret_scanner  # noqa: E402


def _get(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _direct_depends_on_slugs(component_id: str) -> list[str]:
    """Reads the one `depends_on: [comp-a, comp-b]` frontmatter line directly
    -- no PyYAML in this venv, and the only shape this ever takes in this
    corpus (SPEC_GUIDELINES.md) is a flat bracketed list on one line."""
    slug = _slug(component_id)
    text = (REAL_REPO / "specs" / "components" / slug / "component.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("depends_on:"):
            raw = line.split(":", 1)[1].strip().strip("[]")
            ids = [p.strip() for p in raw.split(",") if p.strip()]
            return [_slug(d) for d in ids]
    return []


def _depends_on_slugs(component_id: str) -> list[str]:
    """Transitive closure of _direct_depends_on_slugs, never just the
    target's own direct depends_on -- the real, live gen/ directory
    always has every already-built component present regardless of
    depth, so a sandbox must mirror that or a dependency-of-a-dependency
    (e.g. capability-scenario-verifier's own need for spec-linter) is
    silently missing. Found only once a real provenance-tracker retry's
    generated test for a criterion exercising capability-scenario-
    verifier failed with an ImportError for spec-linter, a dependency
    of a dependency, never provenance-tracker's own direct depends_on."""
    seen: set[str] = set()
    frontier = [_slug(component_id)]
    while frontier:
        slug = frontier.pop()
        if slug in seen:
            continue
        seen.add(slug)
        comp_md = REAL_REPO / "specs" / "components" / slug / "component.md"
        if not comp_md.is_file():
            continue
        frontier.extend(_direct_depends_on_slugs(slug))
    seen.discard(_slug(component_id))
    return sorted(seen)


def _build_sandbox(component_id: str) -> Path:
    """A sandbox whose specs/ and pipeline/ are REAL COPIES of the real
    repo (never symlinks -- a symlink is writable through, and a test that
    resolves "repo_root" by walking up from a loaded module's __file__
    rather than using pytest's own tmp_path, then writes a synthetic
    fixture there, would otherwise silently corrupt the live repository;
    this happened for real once, leaking specs/components/zz-lint-broken-
    fixture/ into the committed tree). gen/ contains a copy per
    already-built dependency (never the component under test itself,
    never an unbuilt one), for the same reason. The component's own
    gen/<slug>/, verification/, and .hotdocs/ are fresh, empty, real
    directories -- so the candidate writes into a clean space with
    nothing left over from any prior attempt."""
    slug = _slug(component_id)
    sandbox = Path(tempfile.mkdtemp(prefix=f"bootstrap_{slug}_"))

    shutil.copytree(REAL_REPO / "specs", sandbox / "specs")
    shutil.copytree(REAL_REPO / "pipeline", sandbox / "pipeline", ignore=shutil.ignore_patterns("__pycache__"))
    (sandbox / "gen").mkdir()
    (sandbox / "verification").mkdir()
    (sandbox / ".hotdocs").mkdir()

    # cache-manager/llm-endpoint are infrastructure every real generate()/
    # author_test() call needs internally, regardless of the target
    # component's own depends_on -- not listed there since they are not
    # dependencies of the SPEC, only of the generation/authoring machinery
    # itself.
    # spec-bundle-assembler is needed by verifier_orchestrator.verify() itself
    # whenever ANY criterion is kind: generated-test (to build each
    # CriterionBundle for test_author), regardless of the target's own
    # depends_on -- found only once a target with zero spec-level dependency
    # on it (decision-drift-detector) first had a generated-test criterion.
    needed = set(_depends_on_slugs(component_id)) | {"cache-manager", "llm-endpoint", "spec-bundle-assembler"}
    for dep_slug in sorted(needed):
        real_dep_dir = REAL_REPO / "gen" / dep_slug
        if real_dep_dir.is_dir() and not (sandbox / "gen" / dep_slug).exists():
            shutil.copytree(real_dep_dir, sandbox / "gen" / dep_slug, ignore=shutil.ignore_patterns("__pycache__"))
        # A missing dependency here means it is sealed (reached via
        # pipeline/, already copied above) or genuinely not yet built --
        # the latter is a prerequisite-ordering error the caller must fix,
        # not something this driver papers over.

    return sandbox


def _swap_in(component_id: str, sandbox: Path) -> None:
    """The ONLY place real gen/<slug>/ or verification/<slug>/generated-test/
    and .../compiled/ are ever touched -- and only ever reached after a full
    verification pass. Deletes the prior asset entirely, then copies the
    verified sandbox result in -- never an incremental overlay, so a
    candidate that changed shape (flat module <-> package) can never leave a
    stale sibling behind."""
    slug = _slug(component_id)

    real_gen_dir = REAL_REPO / "gen" / slug
    if real_gen_dir.exists():
        shutil.rmtree(real_gen_dir)
    shutil.copytree(sandbox / "gen" / slug, real_gen_dir, ignore=shutil.ignore_patterns("__pycache__"))

    # Every other verification/<slug>/ directory in this corpus carries a
    # conftest.py that puts gen/<slug>/ on sys.path, so `pytest
    # verification/<slug>` works standalone -- found missing for two
    # components in a row (spec-bundle-assembler, provenance-tracker) only
    # via a full corpus pytest sweep, never caught by this driver's own
    # sandboxed verify() step, which sets up its own sys.path programmatically.
    conftest_path = REAL_REPO / "verification" / slug / "conftest.py"
    if not conftest_path.exists():
        module_name = slug.replace("-", "_")
        conftest_path.parent.mkdir(parents=True, exist_ok=True)
        conftest_path.write_text(
            "import sys\n"
            "from pathlib import Path\n\n"
            "REPO_ROOT = Path(__file__).resolve().parents[2]\n"
            f'sys.path.insert(0, str(REPO_ROOT / "gen" / "{slug}"))\n'
            f"import {module_name}  # noqa: E402,F401\n"
        )

    for sub in ("generated-test", "compiled"):
        real_dir = REAL_REPO / "verification" / slug / sub
        sandbox_dir = sandbox / "verification" / slug / sub
        if real_dir.exists():
            shutil.rmtree(real_dir)
        if sandbox_dir.exists():
            shutil.copytree(sandbox_dir, real_dir, ignore=shutil.ignore_patterns("__pycache__"))


def run(component_id: str, model: str, seed: int, retry_feedback: list[str] | None, keep_sandbox: bool) -> int:
    sandbox = _build_sandbox(component_id)
    print(f"sandbox: {sandbox}")

    bundle = spec_bundle_assembler.assemble(component_id, repo_root=sandbox, mode="cold")
    print(f"spec_bundle_hash: {bundle.spec_bundle_hash}")

    result = generator.generate(bundle, model, retry_feedback, repo_root=sandbox, llm_backend=None)
    print(f"generate: cache_hit={result.cache_hit} model_call_error={result.model_call_error} refused={result.refused}")
    print(f"files: {list(result.files.keys())}")

    if result.model_call_error or result.refused:
        print("FAIL: generation itself did not produce a candidate -- nothing to verify, nothing swapped.")
        print(f"Sandbox kept at {sandbox} for inspection.")
        return 1

    def test_author_closure(crit_bundle):
        return test_author.author_test(crit_bundle, model, seed=seed, repo_root=sandbox, llm_backend=None)

    report = verifier_orchestrator.verify(component_id, repo_root=sandbox, judge=None, test_author=test_author_closure)
    print(f"verify: overall={report.overall} interface_drift={report.interface_drift} mutation_score={report.mutation_score}")
    for entry in report.criteria:
        print(f"  {entry}")
    print(f"requirement_results: {report.requirement_results}")

    license_result = license_scanner.scan(component_id, repo_root=sandbox)
    print(f"license_scan: blocked={_get(license_result, 'blocked')} similarity_score={_get(license_result, 'similarity_score')}")

    secret_result = secret_scanner.scan(sandbox)
    print(f"secret_scan: flagged={_get(secret_result, 'flagged')} (informational at this gate; blocking handled elsewhere)")

    passed = report.overall == "pass" and not _get(license_result, 'blocked')
    if not passed:
        print(f"FAIL: not swapped in -- real gen/{_slug(component_id)}/ and verification/ left untouched.")
        print(f"Sandbox kept at {sandbox} for inspection.")
        return 1

    _swap_in(component_id, sandbox)
    print(f"PASS: swapped into real gen/{_slug(component_id)}/ and verification/{_slug(component_id)}/.")
    if not keep_sandbox:
        shutil.rmtree(sandbox, ignore_errors=True)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--retry-feedback", default=None, help="comma-separated R-ids")
    parser.add_argument("--keep-sandbox", action="store_true", help="never delete the sandbox, pass or fail")
    args = parser.parse_args(argv)

    retry_feedback = args.retry_feedback.split(",") if args.retry_feedback else None
    return run(args.component_id, args.model, args.seed, retry_feedback, args.keep_sandbox)


if __name__ == "__main__":
    sys.exit(main())
