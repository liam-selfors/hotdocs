#!/usr/bin/env python3
"""reverify_current.py — re-verify a component's committed code, with a test
author, without generating new code.

HAND-AUTHORED REPO TOOL. For a component whose code is current (its spec
bundle is the one its manifest records) but which cannot simply be
re-recorded because some cached tests must be authored again (a test the
probe now rejects, `D341`): builds a bootstrap sandbox, puts the committed
`gen/<slug>/` and `verification/<slug>/` in it, and runs the bootstrap
tool's `--resume-sandbox --reuse-candidate` path, so verification authors
only the tests that are stale or faulty and the committed code lands with
fresh provenance.

    python tools/reverify_current.py comp-<slug> --model=<model> [--hand-suite]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bootstrap_component as bc  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--hand-suite", action="store_true")
    args = parser.parse_args(argv)
    slug = bc._slug(args.component_id)
    manifest = bc.REAL_REPO / "gen" / slug / ".provenance.json"
    recorded = json.loads(manifest.read_text())["spec_bundle_hash"]
    current = bc._get(bc.spec_bundle_assembler.assemble(args.component_id, repo_root=bc.REAL_REPO, mode="cold"),
                      "spec_bundle_hash")
    if recorded != current:
        print(f"FAIL: {args.component_id}'s code was generated from {recorded}, the spec bundle is now {current}: "
              "it must be regenerated, not re-verified.")
        return 2
    sandbox = bc._build_sandbox(args.component_id)
    for part in ("gen", "verification"):
        src = bc.REAL_REPO / part / slug
        dest = sandbox / part / slug
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"sandbox {sandbox} holds the committed code and tests")
    return bc.run(args.component_id, args.model, 1, None, keep_sandbox=False, hand_suite=args.hand_suite,
                  resume=sandbox, reuse_candidate=True, candidate_bundle_hash=current)


if __name__ == "__main__":
    sys.exit(main())
