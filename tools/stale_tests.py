"""Read-only: which committed generated tests a re-verification would find
stale, before a wave runs into them.

HAND-AUTHORED REPO TOOL. A committed test is current exactly when its first
line is `# hotdocs-criterion: sha256:<hex>` for its criterion's bundle as it
is now (`specs/architecture/test-reuse.md`, "The criterion header"). An edit
to a criterion, its requirement, the component's interface (with its
`Implements:` documents), `testing.md`, or the glossary changes that hash,
so every test it reaches must be authored again. `rerecord_provenance.py`
without `--author-tests` then fails every such criterion with "test
authoring failed: none: no test author"; run it, or a wave's second pass,
with `--author-tests=<model>:<seed>` for the components listed here.

    python tools/stale_tests.py [comp-<slug> ...]   # default: every unsealed one

Prints one line per component with stale or missing tests and exits 1 when
there are any, else prints nothing and exits 0.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stamp_criterion_headers import REPO, _assembler, _criteria, _get, _sealed  # noqa: E402

FIELDS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")


def header(bundle) -> str:
    payload = json.dumps({k: _get(bundle, k) or "" for k in FIELDS},
                         sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stale(slug: str, sba) -> tuple[list[str], list[str]]:
    """(stale criterion ids, criterion ids with no committed test)."""
    out, missing = [], []
    for cid, _rid, _path in _criteria(slug):
        test = REPO / "verification" / slug / "generated-test" / f"test_{cid.lower().replace('-', '_')}.py"
        if not test.is_file():
            missing.append(cid)
            continue
        first = test.read_text(encoding="utf-8").split("\n", 1)[0]
        if first != header(sba.assemble_criterion(f"comp-{slug}", cid, REPO)):
            out.append(cid)
    return out, missing


def main(argv: list[str]) -> int:
    slugs = [a.removeprefix("comp-") for a in argv] or [
        p.name for p in sorted((REPO / "specs" / "components").iterdir())
        if (p / "component.md").is_file() and not _sealed(p.name)]
    sba = _assembler()
    found = False
    for slug in slugs:
        try:
            out, missing = stale(slug, sba)
        except Exception as exc:  # a bundle that cannot be built is reported, not raised
            print(f"comp-{slug}: cannot build a bundle: {exc}")
            found = True
            continue
        if out or missing:
            found = True
            parts = [f"{len(out)} stale ({', '.join(out)})" if out else "",
                     f"{len(missing)} missing ({', '.join(missing)})" if missing else ""]
            print(f"comp-{slug}: " + "; ".join(p for p in parts if p))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
