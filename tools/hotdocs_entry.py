#!/usr/bin/env python3
"""hotdocs_entry.py — the console entry point behind the `hotdocs` command.

HAND-AUTHORED REPO TOOL, not a spec-driven component (SPEC_GUIDELINES.md
§1's `tools/` entry). It does one thing: load the `hotdocs-cli`
component's module by path from this repository's `gen/hotdocs-cli/` and
hand it `argv`, passing this repository as the `tool_root` that
`hotdocs init` vendors from. Needs an editable install
(`pip install -e <repo>`), since the components are data in this tree.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
_MODULE_PATH = TOOL_ROOT / "gen" / "hotdocs-cli" / "hotdocs_cli.py"


def main(argv: list[str] | None = None) -> int:
    if not _MODULE_PATH.is_file():
        print(
            f"hotdocs: the hotdocs-cli component is missing from this tool "
            f"checkout ({_MODULE_PATH}). Use an editable install of a complete "
            f"checkout: `pip install -e <path to the hotdocs repository>`.",
            file=sys.stderr,
        )
        return 2
    spec = importlib.util.spec_from_file_location("hotdocs_cli", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["hotdocs_cli"] = module
    spec.loader.exec_module(module)
    return int(module.main(sys.argv[1:] if argv is None else argv, tool_root=TOOL_ROOT) or 0)


if __name__ == "__main__":
    sys.exit(main())
