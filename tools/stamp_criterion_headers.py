"""Stamps the `# hotdocs-criterion` header (R-VERIFY-019, D320) onto
committed generated tests written before the header existed (D328).

For each named component (default: every unsealed one) and each of its
`generated-test` criteria whose committed test file has no header line,
this:

1. assembles the criterion's `CriterionBundle` with the real
   `spec-bundle-assembler`;
2. requires git to show the test file last committed no earlier than its
   criterion file and its covered requirement file, so the test was
   written against the text it is stamped with;
3. prepends `# hotdocs-criterion: sha256:<hex>` of
   `criterion_text + "\\n" + requirement_text`.

A file that fails step 2, or has uncommitted changes, is left alone and
listed: its criterion needs a freshly authored test. Model-free. Usage:

    python tools/stamp_criterion_headers.py [--dry-run] [comp-<slug> ...]
"""
import hashlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HEADER = re.compile(r"^# hotdocs-criterion: sha256:[0-9a-f]{64}$")


def _assembler():
    path = REPO / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py"
    spec = importlib.util.spec_from_file_location("spec_bundle_assembler", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_bundle_assembler"] = module
    spec.loader.exec_module(module)
    return module


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key)


def _front(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("---", 2)[1] if text.startswith("---") else ""


def _sealed(slug: str) -> bool:
    md = REPO / "specs" / "components" / slug / "component.md"
    return any(line.strip() == "sealed: true" for line in _front(md).splitlines())


def _committed_at(path: Path) -> int | None:
    rel = path.relative_to(REPO).as_posix()
    if subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=REPO,
                      capture_output=True, text=True).stdout.strip():
        return None
    out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", rel], cwd=REPO,
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out else None


def _criteria(slug: str):
    """(criterion_id, covered requirement id) for each generated-test criterion."""
    for md in sorted((REPO / "specs" / "components" / slug / "acceptance").glob("AC-*.md")):
        text = md.read_text(encoding="utf-8")
        kind = re.search(r"^Kind:\s*(\S+)", text, re.M)
        covers = re.search(r"^Covers:\s*(\S+)", text, re.M)
        if kind and covers and kind.group(1) == "generated-test":
            yield md.stem, covers.group(1), md


def stamp(slug: str, sba, dry_run: bool) -> tuple[int, list[str]]:
    stamped, refused = 0, []
    comp_dir = REPO / "specs" / "components" / slug
    for cid, rid, ac_path in _criteria(slug):
        test = REPO / "verification" / slug / "generated-test" / f"test_{cid.lower().replace('-', '_')}.py"
        if not test.is_file():
            continue
        lines = test.read_text(encoding="utf-8").split("\n")
        if lines and HEADER.match(lines[0]):
            continue
        req_path = comp_dir / "requirements" / f"{rid}.md"
        t_test, t_ac, t_req = _committed_at(test), _committed_at(ac_path), _committed_at(req_path)
        if None in (t_test, t_ac, t_req) or t_test < max(t_ac, t_req):
            refused.append(cid)
            continue
        bundle = sba.assemble_criterion(f"comp-{slug}", cid, REPO)
        digest = hashlib.sha256(
            (_get(bundle, "criterion_text") + "\n" + _get(bundle, "requirement_text")).encode("utf-8")
        ).hexdigest()
        if not dry_run:
            test.write_text(f"# hotdocs-criterion: sha256:{digest}\n" + "\n".join(lines), encoding="utf-8")
        stamped += 1
    return stamped, refused


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    names = [a for a in argv if a != "--dry-run"]
    slugs = [n.removeprefix("comp-") for n in names] or sorted(
        p.name for p in (REPO / "specs" / "components").iterdir()
        if p.is_dir() and not _sealed(p.name))
    sba = _assembler()
    any_refused = False
    for slug in slugs:
        stamped, refused = stamp(slug, sba, dry_run)
        any_refused = any_refused or bool(refused)
        note = f", needs a fresh test: {refused}" if refused else ""
        print(f"comp-{slug}: {'would stamp' if dry_run else 'stamped'} {stamped}{note}")
    return 1 if any_refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
