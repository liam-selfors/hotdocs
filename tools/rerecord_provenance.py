"""Re-records a generated component's provenance manifest without
regenerating it (D297).

For each named component (default: every unsealed one) this:

1. requires the manifest's `spec_bundle_hash` to equal the bundle's
   current hash, so the spec and its dependencies are what the code was
   generated from;
2. re-verifies the code in `gen/<slug>/` with `verifier-orchestrator`, in
   the real repo, against the component's committed generated tests
   (no model call; an `llm-judge` criterion reports `skipped`);
3. re-runs the license and secret scans;
4. writes a new manifest through `provenance-writer`, carrying the
   original generation's model, prompt version and retry feedback, and
   the code as it is on disk;
5. confirms `provenance-checker` reads it back as a hit.

It writes nothing for a component whose hash changed or whose fresh
verification does not pass. Usage:

    python tools/rerecord_provenance.py [comp-<slug> ...]

With `--author-tests=<model>:<seed>`, step 2 passes the real
`test-author`, so a criterion with no committed test, or a stale one
(`R-VERIFY-019`), gets one written for the unchanged code, as new
criteria for a weak suite need (D329); if verification still fails, the
committed tests are put back as they were.
"""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(slug: str):
    module_name = slug.replace("-", "_")
    base = REPO / "gen" / slug
    flat = base / f"{module_name}.py"
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name, path,
        submodule_search_locations=None if flat.is_file() else [str(path.parent)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _sealed(slug: str) -> bool:
    text = (REPO / "specs" / "components" / slug / "component.md").read_text(encoding="utf-8")
    front = text.split("\n---", 1)[0]
    return any(line.strip() == "sealed: true" for line in front.splitlines())


def _code_files(slug: str) -> dict:
    base = REPO / "gen" / slug
    files = {}
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base)
        if not path.is_file() or "__pycache__" in rel.parts or any(p.startswith(".") for p in rel.parts):
            continue
        files[rel.as_posix()] = path.read_text(encoding="utf-8")
    return files


def _carry_test_authoring(slug: str, manifest: dict, report) -> None:
    """A fresh verification reuses the committed generated tests, so it
    records no `test_authoring`; carry the original record for each
    criterion whose test file git shows unchanged since the manifest was
    committed, since that record still describes the test in use."""
    import subprocess
    old = {c["id"]: c.get("test_authoring")
           for c in manifest.get("verification_report", {}).get("criteria", [])}
    test_dir = REPO / "verification" / slug / "generated-test"
    for criterion in _get(report, "criteria", []):
        record = old.get(criterion["id"])
        if not record or "test_authoring" in criterion:
            continue
        test_file = test_dir / ("test_" + criterion["id"].lower().replace("-", "_") + ".py")
        changed = subprocess.run(
            ["git", "status", "--porcelain", "--", str(test_file)],
            cwd=REPO, capture_output=True, text=True,
        ).stdout.strip()
        if test_file.is_file() and not changed:
            criterion["test_authoring"] = record


def rerecord(component_id: str, pc, pw, vo, lic, sec, author=None) -> bool:
    slug = component_id.removeprefix("comp-")
    manifest_path = REPO / "gen" / slug / ".provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    key = pc.current_provenance_key(component_id, REPO)
    current_hash = _get(key, "spec_bundle_hash")
    if current_hash != manifest.get("spec_bundle_hash"):
        print(f"{component_id}: SKIPPED -- spec_bundle_hash changed since generation; regenerate it")
        return False
    tests_dir = REPO / "verification" / slug / "generated-test"
    backup = None
    if author is not None:
        backup = Path(tempfile.mkdtemp(prefix=f"rerecord_{slug}_")) / "generated-test"
        shutil.copytree(tests_dir, backup)
    report = vo.verify(component_id, REPO, judge=None, test_author=author)
    if _get(report, "overall") != "pass" and backup is not None:
        shutil.rmtree(tests_dir)
        shutil.copytree(backup, tests_dir)
    if _get(report, "overall") != "pass":
        failing = [c["id"] for c in _get(report, "criteria", []) if c.get("result") != "pass"]
        print(f"{component_id}: SKIPPED -- fresh verification is {_get(report, 'overall')} "
              f"(mutation {_get(report, 'mutation_score')}, not passing: {failing})")
        return False
    _carry_test_authoring(slug, manifest, report)
    license_result = lic.scan(component_id, repo_root=REPO)
    secret_result = sec.scan(REPO)
    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": current_hash,
        "model": manifest["model_pin"],
        "prompt_version": manifest["prompt_version"],
        "cache_hit": True,
        "files": _code_files(slug),
        "model_call_error": None,
        "refused": None,
        "retry_feedback": manifest.get("retry_feedback"),
    }
    gate_versions = _get(key, "gate_versions")
    pw.write_provenance(component_id, {
        "component_id": component_id,
        "generation_result": generation_result,
        "verification_report": report,
        "license_scan_result": license_result,
        "secret_scan_result": secret_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": gate_versions,
    }, REPO)
    hit = _get(pc.check_provenance(component_id, current_hash, gate_versions, REPO), "hit")
    print(f"{component_id}: rerecorded, mutation {_get(report, 'mutation_score')}, "
          f"secret_scan flagged={_get(secret_result, 'flagged')}, check hit={hit}", flush=True)
    return bool(hit)


def main(argv) -> int:
    pc = _load("provenance-checker")
    pw = _load("provenance-writer")
    vo = _load("verifier-orchestrator")
    lic = _load("license-scanner")
    sec = _load("secret-scanner")
    author = None
    for arg in [a for a in argv if a.startswith("--author-tests=")]:
        argv = [a for a in argv if a != arg]
        model, _, seed = arg.split("=", 1)[1].rpartition(":")
        ta = _load("test-author")
        author = lambda bundle: ta.author_test(bundle, model, seed=int(seed), repo_root=REPO, llm_backend=None)
    ids = argv or ["comp-" + p.name for p in sorted((REPO / "specs" / "components").iterdir())
                   if p.is_dir() and not _sealed(p.name)]
    ok = True
    for component_id in ids:
        ok = rerecord(component_id, pc, pw, vo, lic, sec, author) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
