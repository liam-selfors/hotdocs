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
import copy
import dataclasses
import hashlib
import json
import re
import shutil
import subprocess
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
    """Reads the one `depends_on: [comp-a, comp-b]` frontmatter line directly:
    the only shape it ever takes in this corpus (SPEC_GUIDELINES.md) is a flat
    bracketed list on one line, so no YAML parser is needed."""
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


def _sealed_source_path(component_id: str) -> str | None:
    """The `source_path` of a `sealed: true` component, else None."""
    text = (REAL_REPO / "specs" / "components" / _slug(component_id) / "component.md").read_text(encoding="utf-8")
    front = text.split("\n---", 1)[0]
    if not re.search(r"^sealed:\s*true\s*$", front, re.M):
        return None
    m = re.search(r"^source_path:\s*(\S+)\s*$", front, re.M)
    return m.group(1).rstrip("/") if m else None


def _unseal_in_sandbox(component_id: str, sandbox: Path) -> None:
    """--sealed-install: inside the sandbox only, mark the component
    unsealed (drop `source_path`) so `generator` writes it to
    gen/<slug>/ and `verifier-orchestrator` runs its generated tests and
    mutation testing. The real repo's spec keeps `sealed: true`."""
    comp_md = sandbox / "specs" / "components" / _slug(component_id) / "component.md"
    text = comp_md.read_text(encoding="utf-8")
    head, sep, rest = text.partition("\n---")
    head = re.sub(r"^sealed:\s*true\s*$", "sealed: false", head, flags=re.M)
    head = re.sub(r"^source_path:.*\n?", "", head, flags=re.M)
    comp_md.write_text(head + sep + rest, encoding="utf-8")


def _hand_suite_files(slug: str) -> list[Path]:
    vdir = REAL_REPO / "verification" / slug
    return sorted(p for p in vdir.glob("test_*.py") if p.is_file()) if vdir.is_dir() else []


# How other modules name each component's module when they load it.
_ALIASES = {
    "spec-linter": ["spec_linter", "linter"],
    "graph-query-engine": ["graph_query_engine", "gqe"],
    "cache-manager": ["cache_manager"],
    "llm-endpoint": ["llm_endpoint", "endpoint"],
    "generator": ["generator"],
    "criterion-compiler": ["criterion_compiler", "compiler", "criterion_compiler_mod"],
    "spec-bundle-assembler": ["spec_bundle_assembler", "sba", "assembler"],
}


# Reviewed false positives: a generic local name (`module`, `mod`) that one
# file rebinds to several different components' modules.
_NOT_CONSUMER_NAMES = {
    "llm-endpoint": {"ParsedCriterion", "author_test", "compile_criterion", "main"},
    "criterion-compiler": {"author_test", "complete"},
    "test-author": {"ParsedCriterion", "compile_criterion", "complete"},
    # The bootstrap's own timeout adjustment, read with a getattr fallback.
    "verifier-orchestrator": {"DEFAULT_TEST_TIMEOUT"},
    # A local list named `assembler` that caches the loaded module (D339).
    "spec-bundle-assembler": {"append"},
}


def _names_used_in(text: str, slug: str) -> list[str]:
    """Every `<alias>.<name>` in one file's text for component `slug`, with
    aliases found as `_consumer_names` describes."""
    module_name = slug.replace("-", "_")
    aliases = set(_ALIASES.get(slug, [module_name]))
    assign = re.compile(r"^\s*(\w+)\s*(?:,\s*\w+\s*)?=(?!=)(.*)$", re.M)
    for lhs, rhs in assign.findall(text):
        loads = re.search(r"_load\w*\(|import_module\(|module_from_spec\(|exec_module\(", rhs)
        names_it = re.search(r"[\"']%s[\"'/]|[\"']%s[\"']|_load_%s\b" % (re.escape(slug), re.escape(module_name), re.escape(module_name)), rhs)
        if loads and names_it:
            aliases.add(lhs)
    pattern = re.compile(r"(?<![\w.])(?:%s)\.([A-Za-z_]\w*)" % "|".join(map(re.escape, sorted(aliases))))
    return [n for n in pattern.findall(text)
            if n not in ("py", "md") and not n.startswith("__") and n not in _NOT_CONSUMER_NAMES.get(slug, ())]


def _provided(module_name: str, code_dir: Path, names) -> set[str] | None:
    """The subset of `names` the module at `code_dir` provides, as an
    attribute or a package submodule; None when it does not import."""
    proc = subprocess.run(
        [sys.executable, "-c",
         f"import json, sys, {module_name} as m; "
         "import importlib\n"
         "def has(n):\n"
         "    if hasattr(m, n): return True\n"
         "    try: importlib.import_module(m.__name__ + '.' + n); return True\n"
         "    except Exception: return False\n"
         "print(json.dumps([n for n in sys.argv[1:] if has(n)]))", *sorted(names)],
        cwd=code_dir, env={**__import__("os").environ, "PYTHONPATH": str(code_dir)},
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    return set(__import__("json").loads(proc.stdout.strip().splitlines()[-1]))


def _dependency_surface_ok(component_id: str, code_dir: Path) -> bool:
    """The reverse of _consumer_surface_ok: every `<dep>.<name>` the
    candidate uses must exist in that dependency's real code (D288)."""
    ok = True
    texts = [p.read_text(encoding="utf-8", errors="replace")
             for p in code_dir.rglob("*.py") if "__pycache__" not in p.parts]
    for dep in _direct_depends_on_slugs(component_id):
        used = sorted({n for t in texts for n in _names_used_in(t, dep)})
        if not used:
            continue
        source = _sealed_source_path("comp-" + dep)
        dep_dir = REAL_REPO / (source.rstrip("/") if source else f"gen/{dep}")
        have = _provided(dep.replace("-", "_"), dep_dir, used)
        if have is None:
            continue
        for name in used:
            if name not in have:
                print(f"dependency surface: {dep} has no {name}, which the candidate uses")
                ok = False
    if ok:
        print("dependency surface: ok")
    return ok


def _consumer_names(slug: str) -> dict[str, list[str]]:
    """Every `<alias>.<name>` other real gen/ modules and tools/ reference,
    mapped to where; the surface a swapped-in candidate must keep. An alias
    is a usual name (`_ALIASES`) or, within one file, any variable assigned
    on a line that names the component (`x = _load(..., "llm_endpoint")`)."""
    module_name = slug.replace("-", "_")
    static = _ALIASES.get(slug, [module_name])
    assign = re.compile(r"^\s*(\w+)\s*(?:,\s*\w+\s*)?=(?!=)(.*)$", re.M)
    found: dict[str, list[str]] = {}
    files = [p for p in (REAL_REPO / "gen").glob("*/**/*.py") if p.parts[len(REAL_REPO.parts) + 1] != slug]
    files += list((REAL_REPO / "tools").glob("*.py"))
    for path in files:
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        aliases = set(static)
        for lhs, rhs in assign.findall(text):
            loads = re.search(r"_load\w*\(|import_module\(|module_from_spec\(|exec_module\(", rhs)
            names_it = re.search(r"[\"']%s[\"'/]|[\"']%s[\"']|_load_%s\b" % (re.escape(slug), re.escape(module_name), re.escape(module_name)), rhs)
            if loads and names_it:
                aliases.add(lhs)
        pattern = re.compile(r"(?<![\w.])(?:%s)\.([A-Za-z_]\w*)" % "|".join(map(re.escape, sorted(aliases))))
        for name in pattern.findall(text):
            if name in ("py", "md") or name.startswith("__") or name in _NOT_CONSUMER_NAMES.get(slug, ()):
                continue
            found.setdefault(name, []).append(str(path.relative_to(REAL_REPO)))
    return found


def _consumer_surface_ok(component_id: str, code_dir: Path) -> bool:
    slug = _slug(component_id)
    module_name = slug.replace("-", "_")
    wanted = _consumer_names(slug)
    # hasattr, not dir(): a module-level __getattr__ (PEP 562) may supply a
    # name lazily, e.g. spec-linter re-exporting corpus-loader's load_corpus.
    proc = subprocess.run(
        [sys.executable, "-c",
         f"import json, sys, {module_name} as m; "
         "import importlib\n"
         "def has(n):\n"
         "    if hasattr(m, n): return True\n"
         "    try: importlib.import_module(m.__name__ + '.' + n); return True\n"  # a package's submodule, e.g. corpus_graph_builder.cli
         "    except Exception: return False\n"
         "print(json.dumps([n for n in sys.argv[1:] if has(n)]))", *sorted(wanted)],
        cwd=code_dir, env={**__import__("os").environ, "PYTHONPATH": str(code_dir)},
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"consumer surface: candidate does not import:\n{proc.stderr[-2000:]}")
        return False
    have = set(__import__("json").loads(proc.stdout.strip().splitlines()[-1]))
    missing = {n: sorted(set(w)) for n, w in wanted.items() if n not in have}
    if missing:
        for n, where in sorted(missing.items()):
            print(f"consumer surface: missing {n} (used in {', '.join(where[:3])})")
        return False
    print("consumer surface: ok")
    return True


def _run_hand_suite(component_id: str, sandbox: Path, code_rel: str) -> bool:
    """Runs the component's hand-maintained suite (verification/<slug>/
    test_*.py and its conftest.py) against the candidate, in a full copy
    of the real repo whose `code_rel` directory is replaced by the
    candidate -- exactly the tree a swap would produce, before any swap."""
    slug = _slug(component_id)
    files = _hand_suite_files(slug)
    if not files:
        print("hand suite: none")
        return True
    root = Path(tempfile.mkdtemp(prefix=f"handsuite_{slug}_"))
    ignore = shutil.ignore_patterns("__pycache__", ".git", ".venv", ".hotdocs")
    for part in ("specs", "pipeline", "gen", "tools", "examples"):
        if (REAL_REPO / part).is_dir():
            shutil.copytree(REAL_REPO / part, root / part, ignore=ignore)
    for f in ("requirements.txt", "pyproject.toml", "hotdocs.toml", "SPEC_GUIDELINES.md",
              ".secret-allowlist.json", ".gitignore"):
        if (REAL_REPO / f).is_file():
            shutil.copy2(REAL_REPO / f, root / f)
    shutil.rmtree(root / code_rel, ignore_errors=True)
    shutil.copytree(sandbox / "gen" / slug, root / code_rel, ignore=shutil.ignore_patterns("__pycache__"))
    vdir = root / "verification" / slug
    vdir.mkdir(parents=True)
    for p in (REAL_REPO / "verification" / slug).iterdir():
        if p.is_file() and p.suffix == ".py":
            shutil.copy2(p, vdir / p.name)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "."],
        cwd=vdir, env={**__import__("os").environ, "PYTHONPATH": str(root / code_rel)},
        capture_output=True, text=True,
    )
    tail = "\n".join(proc.stdout.strip().splitlines()[-15:])
    print(f"hand suite ({len(files)} files) exit={proc.returncode}:\n{tail}")
    if proc.returncode == 0:
        shutil.rmtree(root, ignore_errors=True)
    else:
        print(f"hand-suite tree kept at {root}")
    return proc.returncode == 0


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
    shutil.copy2(REAL_REPO / "SPEC_GUIDELINES.md", sandbox / "SPEC_GUIDELINES.md")  # R-ASSEMBLE-014
    # The sealed secret allowlist (D294; its hash lives in specs/decisions/,
    # copied above), so the sandbox's secret scan matches the real repo's.
    if (REAL_REPO / ".secret-allowlist.json").is_file():
        shutil.copy2(REAL_REPO / ".secret-allowlist.json", sandbox / ".secret-allowlist.json")
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
    infra = {"cache-manager", "llm-endpoint", "spec-bundle-assembler"}
    needed = set(_depends_on_slugs(component_id)) | infra
    # Asset-kind adapters are found by path, never through depends_on
    # (D343, D344): every component has the implicit python asset, and
    # code under test inside the sandbox resolves its tool root to the
    # sandbox itself, so each committed gen/kind-*/ must be there too.
    needed |= {d.name for d in (REAL_REPO / "gen").glob("kind-*") if d.is_dir()}
    for infra_slug in infra:
        # the machinery's own dependencies: an in-sandbox copy of the
        # assembler resolves its tool root to the sandbox itself (D213)
        needed |= set(_depends_on_slugs(f"comp-{infra_slug}"))
    # Never the target itself: its old code beside the candidate would be
    # tested instead of the candidate whenever their shapes differ (an old
    # flat module shadows a new package). While the target is absent, the
    # machinery loads the real repo's copy through the tool-root fallback
    # (D199); once the candidate is written, it uses the candidate.
    # ...unless the machinery itself needs it (spec-linter, graph-query-
    # engine) to assemble the bundle; run() then clears it right before
    # generation, so the candidate is still never tested beside old code.
    infra_deps = set()
    for infra_slug in infra:
        infra_deps |= set(_depends_on_slugs(f"comp-{infra_slug}"))
    if slug not in infra_deps:
        needed.discard(slug)
    for dep_slug in sorted(needed):
        real_dep_dir = REAL_REPO / "gen" / dep_slug
        if real_dep_dir.is_dir() and not (sandbox / "gen" / dep_slug).exists():
            shutil.copytree(real_dep_dir, sandbox / "gen" / dep_slug, ignore=shutil.ignore_patterns("__pycache__"))
        # A missing dependency here means it is sealed (reached via
        # pipeline/, already copied above) or genuinely not yet built --
        # the latter is a prerequisite-ordering error the caller must fix,
        # not something this driver papers over.

    return sandbox


def _swap_in(component_id: str, sandbox: Path, code_rel: str | None = None) -> None:
    """The ONLY place real gen/<slug>/ or verification/<slug>/generated-test/
    and .../compiled/ are ever touched -- and only ever reached after a full
    verification pass. Deletes the prior asset entirely, then copies the
    verified sandbox result in -- never an incremental overlay, so a
    candidate that changed shape (flat module <-> package) can never leave a
    stale sibling behind."""
    slug = _slug(component_id)

    real_gen_dir = REAL_REPO / (code_rel or f"gen/{slug}")
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


def _load_real(slug: str, rel: str | None = None):
    """A fresh load of a real-repo component module (never a cached
    import), so a component swapped in earlier in this run is the one used."""
    import importlib.util
    module_name = slug.replace("-", "_")
    base = REAL_REPO / (rel or f"gen/{slug}")
    path = base / f"{module_name}.py"
    if not path.is_file():
        path = base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_provenance(component_id: str, bundle, result, report, license_result, secret_result) -> bool:
    """Writes the provenance manifest `hotdocs generate` would have written
    for this exact generation (component-gate-runner's R-GATE-006 inputs),
    then confirms provenance-checker reads it back as a hit. Writes nothing
    if the real repo's current spec_bundle_hash is not the one this
    candidate was generated from."""
    pc = _load_real("provenance-checker")
    pw = _load_real("provenance-writer")
    key = pc.current_provenance_key(component_id, REAL_REPO)
    current_hash = _get(key, "spec_bundle_hash")
    if current_hash != _get(bundle, "spec_bundle_hash"):
        print(f"provenance: NOT written -- spec_bundle_hash changed during the run ({current_hash})")
        return False
    gate_versions = _get(key, "gate_versions")
    # D313: the key names the generator that produced the code. Until the
    # provenance-checker that computes it lands, record the version of the
    # generator this run actually used.
    if "generator" not in gate_versions and hasattr(generator, "PROMPT_VERSION"):
        gate_versions = {**gate_versions, "generator": f"{generator.GATE_VERSION}+{generator.PROMPT_VERSION}"}
    pw.write_provenance(component_id, {
        "component_id": component_id,
        "generation_result": result,
        "verification_report": report,
        "license_scan_result": license_result,
        "secret_scan_result": secret_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": gate_versions,
    }, REAL_REPO)
    hit = _get(pc.check_provenance(component_id, current_hash, gate_versions, REAL_REPO), "hit")
    print(f"provenance: written, check hit={hit}")
    return bool(hit)


def _write_sealed_provenance(component_id: str) -> bool:
    """The sealed path component-gate-runner takes: verify in the real repo
    (verifier-orchestrator runs the hand-maintained characterization suite
    at source_path), write the sealed manifest, check it reads back."""
    pc = _load_real("provenance-checker")
    pw = _load_real("provenance-writer")
    vo = _load_real("verifier-orchestrator")
    sealed_key = pc.current_sealed_key(component_id, REAL_REPO)
    report = vo.verify(component_id, REAL_REPO, judge=None, test_author=None)
    print(f"sealed verify (real repo): overall={_get(report, 'overall')}")
    pw.write_sealed_provenance(component_id, {
        "component_id": component_id,
        "owners": _get(sealed_key, "owners"),
        "source_path": _get(sealed_key, "source_path"),
        "source_hash": _get(sealed_key, "source_hash"),
        "verifier_version": _get(sealed_key, "verifier_version"),
        "verification_report": report,
    }, REAL_REPO)
    check = pc.check_sealed_provenance(component_id, REAL_REPO)
    print(f"sealed provenance: written, check={check}")
    return _get(report, "overall") == "pass"


CARRY_FILE = "carry.json"


def _test_author_hash() -> str:
    """Hash of the real test-author code: a test written by other code is
    never carried over."""
    digest = hashlib.sha256()
    for path in sorted((REAL_REPO / "gen" / "test-author").rglob("*.py")):
        if "__pycache__" not in path.parts:
            digest.update(path.relative_to(REAL_REPO).as_posix().encode() + b"\0" + path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _record_carry(component_id: str, sandbox: Path, bundle, report) -> None:
    """Note in a failed seed's sandbox which generated tests passed, so the
    next seed reuses them instead of authoring them again. Tests are written
    from the spec alone, so one that passed stays valid while the spec bundle
    and test-author are unchanged. A failed mutation baseline cannot be
    pinned on one test, so then nothing is carried."""
    if getattr(report, "mutation_error", None):
        return
    # A score under the bar is carried too: each passing test still checks
    # its criterion, the next seed's code brings different mutants, and
    # survivors come from criteria that leave behaviour unpinned, which
    # authoring the same criteria again does not change.
    passed = [_get(e, "id") for e in report.criteria
              if _get(e, "kind") == "generated-test" and _get(e, "result") == "pass"]
    (sandbox / CARRY_FILE).write_text(json.dumps({
        "component_id": component_id,
        "spec_bundle_hash": _get(bundle, "spec_bundle_hash"),
        "test_author": _test_author_hash(),
        "passed": passed,
    }, indent=2))


def _carry_tests(component_id: str, sandbox: Path, bundle) -> None:
    """Copy into a fresh sandbox the passing generated tests of the newest
    earlier seed of this component whose spec bundle and test-author match;
    verify reuses each one whose header is current (R-VERIFY-019)."""
    slug = _slug(component_id)
    want = (_get(bundle, "spec_bundle_hash"), _test_author_hash())
    earlier = sorted(Path(tempfile.gettempdir()).glob(f"bootstrap_{slug}_*/{CARRY_FILE}"),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    for carry_path in earlier:
        if carry_path.parent == sandbox:
            continue
        try:
            carry = json.loads(carry_path.read_text())
        except (OSError, ValueError):
            continue
        if carry.get("component_id") != component_id or (carry.get("spec_bundle_hash"), carry.get("test_author")) != want:
            continue
        src_dir = carry_path.parent / "verification" / slug / "generated-test"
        dest_dir = sandbox / "verification" / slug / "generated-test"
        dest_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        for cid in carry.get("passed", []):
            name = "test_" + cid.lower().replace("-", "_") + ".py"  # verify's naming
            if (src_dir / name).is_file():
                shutil.copy2(src_dir / name, dest_dir / name)
                copied.append(cid)
        print(f"carried {len(copied)} passing test(s) from {carry_path.parent.name}: {', '.join(copied)}")
        return
    _reuse_committed(component_id, sandbox)


_BUNDLE_FIELDS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")


def _criterion_header(bundle) -> str:
    """The header line the real verifier expects (R-VERIFY-019): the
    whole-bundle hash from verifier-orchestrator@3.3.0 on (D341), the
    criterion-and-requirement hash before."""
    version = str(getattr(verifier_orchestrator, "GATE_VERSION", ""))
    major_minor = tuple(int(x) for x in re.findall(r"@(\d+)\.(\d+)", version)[0]) if "@" in version else (0, 0)
    if major_minor >= (3, 3):
        text = json.dumps({k: _get(bundle, k) or "" for k in _BUNDLE_FIELDS},
                          sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    else:
        text = _get(bundle, "criterion_text") + "\n" + _get(bundle, "requirement_text")
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bundle_view(component_id: str, criterion_id: str, root: Path) -> str | None:
    try:
        b = spec_bundle_assembler.assemble_criterion(component_id, criterion_id, root)
    except Exception:
        return None
    return json.dumps({k: _get(b, k) for k in _BUNDLE_FIELDS}, sort_keys=True, default=str)


def _reuse_committed(component_id: str, sandbox: Path) -> None:
    """With no earlier seed to carry from, start from the committed generated
    tests whose criterion, covered requirement, interface (with its
    Implements: documents) and glossary are what they were when the test was
    last committed. A dependency's interface may have changed (a version
    string, a reworded paragraph): a test whose fakes no longer fit fails,
    and the next seed authors that one test again."""
    slug = _slug(component_id)
    real_dir = REAL_REPO / "verification" / slug / "generated-test"
    dest_dir = sandbox / "verification" / slug / "generated-test"
    by_name = {"test_" + p.stem.lower().replace("-", "_") + ".py": p.stem
               for p in (REAL_REPO / "specs" / "components" / slug / "acceptance").glob("AC-*.md")}
    snapshots: dict[str, Path] = {}
    reused = []
    for test in sorted(real_dir.glob("test_*.py")):
        criterion_id = by_name.get(test.name)
        git = lambda *a: subprocess.run(["git", *a], cwd=REAL_REPO, capture_output=True)
        if not criterion_id or git("diff", "--quiet", "HEAD", "--", str(test)).returncode != 0:
            continue
        commit = git("log", "-1", "--format=%H", "--", str(test)).stdout.decode().strip()
        if not commit:
            continue
        if commit not in snapshots:
            snap = Path(tempfile.mkdtemp(prefix="bootstrap_snapshot_"))
            archive = git("archive", commit, "specs", "SPEC_GUIDELINES.md").stdout
            subprocess.run(["tar", "-x", "-C", str(snap)], input=archive, check=True)
            snapshots[commit] = snap
        then = _bundle_view(component_id, criterion_id, snapshots[commit])
        if then is not None and then == _bundle_view(component_id, criterion_id, REAL_REPO):
            dest_dir.mkdir(parents=True, exist_ok=True)
            # Stamp the header the running verifier expects: the bundle is
            # unchanged since this test was committed, so it is current.
            lines = test.read_text(encoding="utf-8").split("\n")
            if lines and lines[0].startswith("# hotdocs-criterion:"):
                lines = lines[1:]
            current = spec_bundle_assembler.assemble_criterion(component_id, criterion_id, REAL_REPO)
            (dest_dir / test.name).write_text(_criterion_header(current) + "\n" + "\n".join(lines), encoding="utf-8")
            reused.append(criterion_id)
    for snap in snapshots.values():
        shutil.rmtree(snap, ignore_errors=True)
    print(f"reused {len(reused)} committed test(s) whose criterion bundle is unchanged: {', '.join(reused)}")


def run(component_id: str, model: str, seed: int, retry_feedback: list[str] | None, keep_sandbox: bool,
        hand_suite: bool = False, sealed_install: bool = False, resume: Path | None = None) -> int:
    code_rel = None
    if sealed_install:
        code_rel = _sealed_source_path(component_id)
        if not code_rel:
            print("FAIL: --sealed-install needs a sealed: true component with a source_path.")
            return 2
    if resume is not None:
        # A kept sandbox from an earlier run of the same component, model
        # and seed: generation and test authoring hit that run's caches, so
        # what lands (and what provenance records) is that run's work.
        sandbox = Path(resume)
    else:
        sandbox = _build_sandbox(component_id)
        if sealed_install:
            _unseal_in_sandbox(component_id, sandbox)
    print(f"sandbox: {sandbox}")

    bundle = spec_bundle_assembler.assemble(component_id, repo_root=sandbox, mode="cold")
    print(f"spec_bundle_hash: {_get(bundle, 'spec_bundle_hash')}")
    if resume is None:
        _carry_tests(component_id, sandbox, bundle)

    # Never generate beside the target's old code (see _build_sandbox).
    shutil.rmtree(sandbox / "gen" / _slug(component_id), ignore_errors=True)
    result = generator.generate(bundle, model, retry_feedback, repo_root=sandbox, llm_backend=None)
    # Forget every module this process loaded from the sandbox before the
    # candidate existed (e.g. the old graph-query-engine that spec-linter
    # imported by name), so later loads see the candidate, not stale code.
    sandbox_real = str(sandbox.resolve())
    for name, mod in list(sys.modules.items()):
        mod_file = getattr(mod, "__file__", None)
        if mod_file and str(Path(mod_file).resolve()).startswith(sandbox_real):
            del sys.modules[name]
    print(f"generate: cache_hit={_get(result, 'cache_hit')} model_call_error={_get(result, 'model_call_error')} refused={_get(result, 'refused')}")
    print(f"files: {list((_get(result, 'files') or {}).keys())}")

    if _get(result, "model_call_error") or _get(result, "refused"):
        print("FAIL: generation itself did not produce a candidate -- nothing to verify, nothing swapped.")
        print(f"Sandbox kept at {sandbox} for inspection.")
        return 1

    # Cheap and decisive, so before the long verification: a candidate
    # that lacks names its consumers use (or does not import) is rejected.
    if not _consumer_surface_ok(component_id, sandbox / "gen" / _slug(component_id)):
        print("FAIL: the candidate lacks names other components use -- nothing swapped.")
        print(f"Sandbox kept at {sandbox} for inspection.")
        return 1
    if not _dependency_surface_ok(component_id, sandbox / "gen" / _slug(component_id)):
        print("FAIL: the candidate uses names its dependencies lack -- nothing swapped.")
        print(f"Sandbox kept at {sandbox} for inspection.")
        return 1

    # A test-author that predates D341 ignores CriterionBundle.testing, so
    # until test-author itself is regenerated its authors would never see a
    # component's testing.md. Hand it over inside the interface text, which
    # every test-author shows, with a heading saying what it is.
    author_reads_testing = "testing" in Path(test_author.__file__).read_text(encoding="utf-8")

    def test_author_closure(crit_bundle):
        testing = _get(crit_bundle, "testing") or ""
        if testing and not author_reads_testing:
            extra = "\n\n## Test spec (testing.md: test mechanics only)\n\n" + testing
            if isinstance(crit_bundle, dict):
                crit_bundle = {**crit_bundle, "interface": (crit_bundle.get("interface") or "") + extra}
            elif dataclasses.is_dataclass(crit_bundle):
                crit_bundle = dataclasses.replace(crit_bundle, interface=(crit_bundle.interface or "") + extra)
            else:
                crit_bundle = copy.copy(crit_bundle)
                crit_bundle.interface = (getattr(crit_bundle, "interface", "") or "") + extra
        return test_author.author_test(crit_bundle, model, seed=seed, repo_root=sandbox, llm_backend=None)

    # A verifier-orchestrator candidate's own tests call verify(), which runs
    # mutation testing, so a single test can take 20 s. The verifier doing
    # the checking is the previous one, whose 10 s limit on unmutated runs
    # predates D276 (300 s) and also made its mutation baseline time out,
    # scoring every mutant killed. Apply D276's limit while it checks its
    # successor; DEFAULT_TEST_TIMEOUT is read at call time.
    saved_timeout = getattr(verifier_orchestrator, "DEFAULT_TEST_TIMEOUT", None)
    if component_id == "comp-verifier-orchestrator" and saved_timeout is not None:
        verifier_orchestrator.DEFAULT_TEST_TIMEOUT = max(saved_timeout, 300.0)
    try:
        report = verifier_orchestrator.verify(component_id, repo_root=sandbox, judge=None, test_author=test_author_closure)
    finally:
        if saved_timeout is not None:
            verifier_orchestrator.DEFAULT_TEST_TIMEOUT = saved_timeout
    print(f"verify: overall={report.overall} interface_drift={report.interface_drift} mutation_score={report.mutation_score} mutation_error={getattr(report, 'mutation_error', None)}")
    for entry in report.criteria:
        print(f"  {entry}")
    print(f"requirement_results: {report.requirement_results}")

    license_result = license_scanner.scan(component_id, repo_root=sandbox)
    print(f"license_scan: blocked={_get(license_result, 'blocked')} similarity_score={_get(license_result, 'similarity_score')}")

    secret_result = secret_scanner.scan(sandbox)
    print(f"secret_scan: flagged={_get(secret_result, 'flagged')} (informational at this gate; blocking handled elsewhere)")

    passed = report.overall == "pass" and not _get(license_result, 'blocked')
    _record_carry(component_id, sandbox, bundle, report)
    if not passed:
        print(f"FAIL: not swapped in -- real gen/{_slug(component_id)}/ and verification/ left untouched.")
        print(f"Sandbox kept at {sandbox} for inspection.")
        return 1

    if (hand_suite or sealed_install) and not _run_hand_suite(component_id, sandbox, code_rel or f"gen/{_slug(component_id)}"):
        print("FAIL: the hand-maintained suite fails against the candidate -- nothing swapped.")
        print(f"Sandbox kept at {sandbox} for inspection.")
        return 1

    # Since D305 generate() never caches; a candidate is cached only once
    # it has passed, so a --resume-sandbox run still hits it.
    if hasattr(generator, "commit_cache"):
        generator.commit_cache(result, repo_root=sandbox)
    _swap_in(component_id, sandbox, code_rel)
    if sealed_install:
        provenance_ok = _write_sealed_provenance(component_id)
    else:
        provenance_ok = _write_provenance(component_id, bundle, result, report, license_result, secret_result)
    if not provenance_ok:
        print("PROVENANCE MISS: swapped in, but its provenance does not check -- fix before committing.")
    print(f"PASS: swapped into real {code_rel or 'gen/' + _slug(component_id)}/ and verification/{_slug(component_id)}/.")
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
    parser.add_argument("--hand-suite", action="store_true",
                        help="also require verification/<slug>/test_*.py (hand-maintained) to pass against the candidate before swapping")
    parser.add_argument("--resume-sandbox", default=None,
                        help="rerun the full pipeline in a kept sandbox (same component, model and seed); "
                             "generation and test authoring come from its caches")
    parser.add_argument("--sealed-install", action="store_true",
                        help="for a sealed component: generate it unsealed in the sandbox, require its hand-maintained "
                             "characterization suite too, and install the result at its source_path")
    args = parser.parse_args(argv)

    retry_feedback = args.retry_feedback.split(",") if args.retry_feedback else None
    return run(args.component_id, args.model, args.seed, retry_feedback, args.keep_sandbox,
               hand_suite=args.hand_suite, sealed_install=args.sealed_install,
               resume=Path(args.resume_sandbox) if args.resume_sandbox else None)


if __name__ == "__main__":
    sys.exit(main())
