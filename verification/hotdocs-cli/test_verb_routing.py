"""Hand suite: every verb whose component implements cli-conventions.md
treats an unknown argument as a usage error when reached through the real
dispatcher -- exit 2, a `usage error:` first line on stderr, no traceback
(`D299`, `D302`).

Each route runs in its own process against this tree's own components,
from an empty project directory, so the tool-root fallback is exercised.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VERB_TABLE = REPO_ROOT / "specs" / "components" / "hotdocs-cli" / "interface" / "data" / "VerbTable.md"
CONVENTIONS = "specs/architecture/cli-conventions.md"


def _rows():
    rows = []
    for line in VERB_TABLE.read_text(encoding="utf-8").splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not cells[1].startswith(("gen/", "pipeline/")):
            continue
        words, directory = cells[0], cells[1]
        if words == "init":
            continue
        library = REPO_ROOT / "specs" / "components" / Path(directory).name / "interface" / "library.md"
        implements = [l for l in library.read_text(encoding="utf-8").splitlines()
                      if l.startswith("Implements:")] if library.is_file() else []
        if any(CONVENTIONS in l for l in implements):
            rows.append(words)
    return rows


ROWS = _rows()


def test_some_route_implements_the_conventions():
    assert ROWS, f"no VerbTable row's component implements {CONVENTIONS}"


@pytest.mark.parametrize("words", ROWS)
def test_unknown_argument_is_a_usage_error(words, tmp_path):
    argv = words.split() + ["--hotdocs-smoke-unknown"]
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import hotdocs_cli; "
        "sys.exit(hotdocs_cli.main(sys.argv[4:], tool_root=sys.argv[2], cwd=sys.argv[3]))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(REPO_ROOT / "gen" / "hotdocs-cli"), str(REPO_ROOT), str(tmp_path), *argv],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    first = proc.stderr.splitlines()[0] if proc.stderr else ""
    assert re.match(r"usage error: ", first), proc.stderr
    assert "Traceback" not in proc.stderr
