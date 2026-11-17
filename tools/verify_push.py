#!/usr/bin/env python3
"""verify_push.py — the verification every commit passes before it is pushed.

HAND-AUTHORED REPO TOOL, not a spec-driven component (SPEC_GUIDELINES.md
§1's `tools/` entry). For each commit it makes a throwaway worktree of
exactly that commit, so uncommitted changes never colour the result, and
runs, with the commit's own `hotdocs`:

1. `hotdocs lint`: the corpus has no hard failure;
2. `hotdocs verify`: every component and capability has current, passing
   provenance (read-only, no model call);
3. a check that verify left the worktree unchanged.

Usage:

    python tools/verify_push.py [<commit> ...]   # default: HEAD
    python tools/verify_push.py --install-hook   # make it this clone's pre-push hook

As a pre-push hook it verifies every commit a push would send as a branch
tip and refuses the push on any failure. The hook runs its own copy of
this file (`.git/hooks/verify_push.py`), so it works on every branch;
`--install-hook` again refreshes that copy. Dependencies come from
`$HOTDOCS_PYTHON`, else the clone's `.venv/bin/python`, else the Python
running this file.

Exit codes: 0 every commit passed, 1 a commit failed, 2 usage error.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ZERO = "0" * 40


def _git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _common_dir() -> Path:
    return Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir"))


def _python() -> str:
    if os.environ.get("HOTDOCS_PYTHON"):
        return os.environ["HOTDOCS_PYTHON"]
    venv = _common_dir().parent / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def _step(name: str, args: list[str], cwd: Path) -> tuple[bool, str]:
    started = time.monotonic()
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    output = (done.stdout + done.stderr).strip()
    print(f"  {name}: {'ok' if done.returncode == 0 else 'FAILED'} ({time.monotonic() - started:.0f}s)", flush=True)
    return done.returncode == 0, output


def verify(commit: str) -> bool:
    sha = _git("rev-parse", "--verify", f"{commit}^{{commit}}")
    print(f"verifying {sha[:12]} ({commit})", flush=True)
    tree = Path(tempfile.mkdtemp(prefix="verify_push_")) / "tree"
    _git("worktree", "add", "--detach", "--quiet", str(tree), sha)
    try:
        entry = [_python(), str(tree / "tools" / "hotdocs_entry.py")]
        for name, args in (("hotdocs lint", entry + ["lint"]), ("hotdocs verify", entry + ["verify"])):
            ok, output = _step(name, args, tree)
            if not ok:
                tail = [line for line in output.splitlines() if " fail " in line or not line.startswith("specs/")]
                print("\n".join("    " + line for line in tail[-25:]), flush=True)
                return False
        changed = _git("status", "--porcelain", cwd=tree)
        if changed:
            print("  hotdocs verify changed the tree:\n" + "\n".join("    " + line for line in changed.splitlines()), flush=True)
            return False
        return True
    finally:
        _git("worktree", "remove", "--force", str(tree))
        shutil.rmtree(tree.parent, ignore_errors=True)


def install_hook() -> int:
    hooks = _common_dir() / "hooks"
    hooks.mkdir(exist_ok=True)
    shutil.copyfile(__file__, hooks / "verify_push.py")
    hook = hooks / "pre-push"
    hook.write_text(
        "#!/bin/sh\n"
        "# Installed by tools/verify_push.py --install-hook: every pushed branch tip\n"
        "# must pass lint and hotdocs verify. Refresh with --install-hook.\n"
        'exec python3 "$(dirname "$0")/verify_push.py" --hook "$@"\n',
        encoding="utf-8",
    )
    hook.chmod(0o755)
    print(f"installed {hook}")
    return 0


def hook_commits(stdin) -> list[str]:
    """The pushed tips from git's pre-push input, one
    `<local ref> <local sha> <remote ref> <remote sha>` line per ref;
    a deletion (local sha all zeros) and a tag push send nothing to check."""
    commits = []
    for line in stdin:
        parts = line.split()
        if len(parts) == 4 and parts[1] != ZERO and parts[0].startswith("refs/heads/") and parts[1] not in commits:
            commits.append(parts[1])
    return commits


def main(argv: list[str]) -> int:
    if argv == ["--install-hook"]:
        return install_hook()
    if argv[:1] == ["--hook"]:
        commits = hook_commits(sys.stdin)
    elif any(arg.startswith("-") for arg in argv):
        print(__doc__.strip().split("\n\n")[2], file=sys.stderr)
        return 2
    else:
        commits = argv or ["HEAD"]
    failed = [commit for commit in commits if not verify(commit)]
    if failed:
        print(f"verification failed for {', '.join(c[:12] for c in failed)}: not pushing.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
