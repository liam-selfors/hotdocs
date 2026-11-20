#!/usr/bin/env python3
"""restamp_headers.py — give committed generated tests the criterion header
the running verifier expects, when their criterion bundle is unchanged.

HAND-AUTHORED REPO TOOL. `D341` changed the header from a hash of the
criterion and requirement text to a hash of the whole criterion bundle
view. A test whose bundle view (criterion, requirement, interface with its
Implements documents, glossary, test spec) is the same now as at the
commit that last touched it is still current, so only its header line is
rewritten; a test whose view changed is left alone, and the verifier
authors it again. Prints, per component, how many were restamped and which
were left stale.

    python tools/restamp_headers.py [comp-<slug> ...]   # default: all
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap_component as bc  # noqa: E402

REPO = bc.REAL_REPO


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True)


def restamp(component_id: str, snapshots: dict) -> tuple[list[str], list[str]]:
    slug = bc._slug(component_id)
    tests_dir = REPO / "verification" / slug / "generated-test"
    by_name = {"test_" + p.stem.lower().replace("-", "_") + ".py": p.stem
               for p in (REPO / "specs" / "components" / slug / "acceptance").glob("AC-*.md")}
    done, stale = [], []
    for test in sorted(tests_dir.glob("test_*.py")):
        criterion_id = by_name.get(test.name)
        if not criterion_id:
            continue
        commit = _git("log", "-1", "--format=%H", "--", str(test)).stdout.decode().strip()
        if not commit:
            continue
        if commit not in snapshots:
            snap = Path(tempfile.mkdtemp(prefix="restamp_snapshot_"))
            archive = _git("archive", commit, "specs", "SPEC_GUIDELINES.md").stdout
            subprocess.run(["tar", "-x", "-C", str(snap)], input=archive, check=True)
            snapshots[commit] = snap
        then = bc._bundle_view(component_id, criterion_id, snapshots[commit])
        if then is None or then != bc._bundle_view(component_id, criterion_id, REPO):
            stale.append(criterion_id)
            continue
        current = bc.spec_bundle_assembler.assemble_criterion(component_id, criterion_id, REPO)
        header = bc._criterion_header(current)
        lines = test.read_text(encoding="utf-8").split("\n")
        if lines and lines[0] == header:
            continue
        if lines and lines[0].startswith("# hotdocs-criterion:"):
            lines = lines[1:]
        test.write_text(header + "\n" + "\n".join(lines), encoding="utf-8")
        done.append(criterion_id)
    return done, stale


def main(argv: list[str]) -> int:
    ids = argv or sorted("comp-" + p.name for p in (REPO / "specs" / "components").iterdir()
                         if (p / "component.md").is_file())
    snapshots: dict = {}
    try:
        for cid in ids:
            done, stale = restamp(cid, snapshots)
            if done or stale:
                print(f"{cid}: restamped {len(done)}; stale {len(stale)}{': ' + ', '.join(stale) if stale else ''}")
    finally:
        for snap in snapshots.values():
            shutil.rmtree(snap, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
