#!/usr/bin/env python3
"""build_dist.py — build the hotdocs sdist and wheel for PyPI.

HAND-AUTHORED REPO TOOL (D358). The installed tool needs, beside its entry
point, the tool root the components read by path: `gen/`, `pipeline/`,
`examples/` and `requirements.txt`, in their checkout layout, so "the parent
of the nearest `gen` directory" still finds it. It also holds `pyproject.toml`,
which the components read the tool version from, and the guides a project
gets no copy of: `QUICKSTART.md`, `AUTHORING.md` and `agent-skills/` (D360),
with the reference documents those guides cite (D367).
This stages a package

    hotdocs/__init__.py      version
    hotdocs/__main__.py      `python -m hotdocs`
    hotdocs/_entry.py        tools/hotdocs_entry.py, unchanged
    hotdocs/_tool/...        the tool root

lists every staged file explicitly as package data (so dotfiles such as
`.provenance.json` ship too), and runs `python -m build` in the stage. The
version is `pyproject.toml`'s, the one place it is set; the dependencies are
`requirements.txt`'s exact pins.

    python tools/build_dist.py [--out=<dir>] [--python=<interpreter with build>]

Prints the paths of the sdist and wheel it wrote (default `dist/`).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Documents the shipped guides name, at their checkout paths (D367). Reading
# matter only: no component reads the tool root's `specs/`.
REFERENCE_DOCS = ("SPEC_GUIDELINES.md",
                  "specs/architecture/asset-kinds.md",
                  "specs/architecture/asset-kind-python.md",
                  "specs/architecture/asset-kind-javascript.md",
                  "specs/architecture/step-phrase-grammar.md",
                  "specs/architecture/cli-conventions.md",
                  "specs/architecture/spec-frontmatter.md",
                  "specs/architecture/spec-layout.md",
                  "specs/architecture/acceptance-criteria.md",
                  "specs/architecture/size-caps.md",
                  "specs/architecture/glossary-and-citations.md",
                  "specs/architecture/test-drivers.md",
                  "specs/architecture/test-driver-browser.md")
TOOL_PARTS = ("gen", "pipeline", "examples", "requirements.txt",
              "pyproject.toml", "QUICKSTART.md", "AUTHORING.md", "agent-skills",
              *REFERENCE_DOCS)
SKIP_DIRS = {"__pycache__", ".hotdocs", ".pytest_cache"}
DOCS = ("README.md", "QUICKSTART.md", "AUTHORING.md", "LICENSE")


def _copy_tree(src: Path, dest: Path) -> None:
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if any(part in SKIP_DIRS for part in rel.parts) or path.suffix == ".pyc":
            continue
        if path.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest / rel)


def _toml_list(items: list[str]) -> str:
    return "[\n" + "".join(f'    "{i}",\n' for i in items) + "]"


def stage(stage_dir: Path) -> Path:
    meta = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = meta["version"]
    pkg = stage_dir / "hotdocs"
    tool = pkg / "_tool"
    for part in TOOL_PARTS:
        _copy_tree(REPO / part, tool / part)
    shutil.copy2(REPO / "tools" / "hotdocs_entry.py", pkg / "_entry.py")
    (pkg / "__init__.py").write_text(f'"""hotdocs: spec-driven agentic development."""\n\n__version__ = "{version}"\n',
                                     encoding="utf-8")
    (pkg / "__main__.py").write_text("import sys\n\nfrom hotdocs._entry import main\n\nsys.exit(main())\n",
                                     encoding="utf-8")
    for doc in DOCS:
        shutil.copy2(REPO / doc, stage_dir / doc)
    data = sorted(str(p.relative_to(pkg)) for p in tool.rglob("*") if p.is_file())
    deps = [line.strip() for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]
    (stage_dir / "pyproject.toml").write_text(f'''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hotdocs"
version = "{version}"
description = "{meta["description"]}"
readme = "README.md"
license = {{text = "Apache-2.0"}}
requires-python = "{meta["requires-python"]}"
classifiers = {_toml_list(meta.get("classifiers", []))}
dependencies = {_toml_list(deps)}

[project.scripts]
hotdocs = "hotdocs._entry:main"

[tool.setuptools]
packages = ["hotdocs"]
include-package-data = false

[tool.setuptools.package-data]
hotdocs = {_toml_list(data)}
''', encoding="utf-8")
    # The sdist carries the same files: setuptools adds package data it was
    # told about, and the MANIFEST lists the docs and the tool root by name.
    (stage_dir / "MANIFEST.in").write_text(
        "".join(f"include {d}\n" for d in DOCS) + "".join(f"include hotdocs/{d}\n" for d in data),
        encoding="utf-8")
    return stage_dir


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the hotdocs sdist and wheel.")
    parser.add_argument("--out", default=str(REPO / "dist"))
    parser.add_argument("--python", default=sys.executable, help="an interpreter with `build` installed")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    with tempfile.TemporaryDirectory(prefix="hotdocs_dist_") as tmp:
        stage_dir = stage(Path(tmp))
        proc = subprocess.run([args.python, "-m", "build", "--sdist", "--wheel", "--outdir", str(out), str(stage_dir)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stdout[-3000:] + proc.stderr[-3000:], file=sys.stderr)
            return 1
    built = sorted(p for p in out.glob("hotdocs-*") if p.suffix in (".whl", ".gz"))
    for p in built:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
