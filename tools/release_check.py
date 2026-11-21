#!/usr/bin/env python3
"""release_check.py — prove a built hotdocs wheel works before it is published.

HAND-AUTHORED REPO TOOL (D358), in `verify_push.py`'s spirit: no CI, run by
hand before every upload. It

1. builds the sdist and wheel with `tools/build_dist.py` into a temporary
   directory, using an interpreter that has `build` and `twine`;
2. runs `twine check` on both;
3. installs the wheel into a fresh virtual environment, then makes the
   installed `hotdocs` package read-only, since an installed tool must never
   write to its own tool root;
4. in a new git project, runs the fresh-project check with the installed
   command: `hotdocs init --example`, `lint`, `spec check`, `generate
   comp-slugify` (single mode, and agentic mode with `--agentic`), and
   `verify` after each generation; plus `python -m hotdocs` with no
   arguments.

    python tools/release_check.py --python=<interpreter with build and twine>
        [--provider=claude-cli] [--agentic] [--keep]

Exits 0 only when every step passes. `--keep` leaves the work directory
(the wheel, the environment and the project) for inspection; its path is
printed either way. Model calls use the configured provider and cost tokens.
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(label: str, cmd: list[str], cwd: Path, expect_out: str | None = None, env=None) -> bool:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)
    out = proc.stdout + proc.stderr
    ok = proc.returncode == 0 and (expect_out is None or expect_out in out)
    print(f"{'ok  ' if ok else 'FAIL'} {label}")
    if not ok:
        print("     " + "\n     ".join(out.strip().splitlines()[-15:]))
    return ok


def _set_writable(root: Path, writable: bool) -> None:
    for path in [root, *root.rglob("*")]:
        mode = path.stat().st_mode
        bits = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
        os.chmod(path, (mode | stat.S_IWUSR) if writable else (mode & ~bits))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check a built hotdocs wheel before publishing it.")
    parser.add_argument("--python", required=True, help="an interpreter with `build` and `twine` installed")
    parser.add_argument("--provider", default="claude-cli")
    parser.add_argument("--agentic", action="store_true")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)

    work = Path(tempfile.mkdtemp(prefix="hotdocs_release_"))
    print(f"work directory: {work}")
    dist, venv, project = work / "dist", work / "venv", work / "project"
    results = []
    results.append(_run("build sdist and wheel", [sys.executable, str(REPO / "tools" / "build_dist.py"),
                                                   f"--out={dist}", f"--python={args.python}"], REPO))
    wheels = sorted(dist.glob("hotdocs-*.whl"))
    if not results[-1] or not wheels:
        return 1
    results.append(_run("twine check", [args.python, "-m", "twine", "check", *map(str, dist.iterdir())], REPO,
                        expect_out="PASSED"))
    results.append(_run("fresh environment", [sys.executable, "-m", "venv", str(venv)], work))
    pip, py, hd = venv / "bin" / "pip", venv / "bin" / "python", venv / "bin" / "hotdocs"
    results.append(_run("install the wheel", [str(pip), "install", "-q", str(wheels[-1])], work))
    pkg = Path(subprocess.run([str(py), "-c", "import hotdocs, pathlib; print(pathlib.Path(hotdocs.__file__).parent)"],
                              capture_output=True, text=True).stdout.strip())
    if not pkg.is_dir():
        print("FAIL the installed package was not found")
        return 1
    # pip writes bytecode at install time; anything new after this point
    # would be the tool writing into its own tool root.
    before = {p for p in pkg.rglob("*")}
    _set_writable(pkg, False)
    try:
        project.mkdir()
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], cwd=project, check=True)
        results.append(_run("python -m hotdocs lists the verbs", [str(py), "-m", "hotdocs"], project, expect_out="lint"))
        results.append(_run("hotdocs init --example", [str(hd), "init", "--example", f"--provider={args.provider}",
                                                       "--auth", "login", "--yes"], project))
        subprocess.run([*git, "add", "-A"], cwd=project, check=True)
        subprocess.run([*git, "commit", "-q", "-m", "init --example"], cwd=project, check=True)
        results.append(_run("hotdocs lint", [str(hd), "lint"], project))
        results.append(_run("hotdocs spec check", [str(hd), "spec", "check", "comp-slugify", "--no-model"], project))
        results.append(_run("hotdocs generate (single)", [str(hd), "generate", "comp-slugify", "--mode=single"], project))
        results.append(_run("hotdocs verify", [str(hd), "verify"], project, expect_out="ready"))
        if args.agentic:
            subprocess.run([*git, "add", "-A"], cwd=project, check=True)
            subprocess.run([*git, "commit", "-q", "-m", "single"], cwd=project, check=True)
            for part in ("gen/slugify", "verification/slugify"):
                subprocess.run(["rm", "-rf", str(project / part)], check=True)
            results.append(_run("hotdocs generate (agentic)", [str(hd), "generate", "comp-slugify", "--mode=agentic"],
                                project))
            results.append(_run("hotdocs verify after agentic", [str(hd), "verify"], project, expect_out="ready"))
        stray = sorted(set(pkg.rglob("*")) - before)
        print(f"{'ok  ' if not stray else 'FAIL'} nothing was written into the installed package"
              + (f": {', '.join(str(p.relative_to(pkg)) for p in stray[:5])}" if stray else ""))
        results.append(not stray)
    finally:
        _set_writable(pkg, True)
        if not args.keep:
            subprocess.run(["rm", "-rf", str(work)])
    passed = all(results)
    print(f"release check: {'PASS' if passed else 'FAIL'} ({sum(results)}/{len(results)} steps)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
