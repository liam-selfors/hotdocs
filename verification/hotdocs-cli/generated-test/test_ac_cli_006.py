import json
import os
import sys
from pathlib import Path

import hotdocs_cli


def _write_fake_component(root: Path, rel_dir: str, module: str, code: int, log_root: Path) -> Path:
    target_dir = root / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_root / "calls.log"
    source = (
        "import json\n"
        "\n"
        f"_LOG = {str(log_path)!r}\n"
        "\n"
        "def main(argv):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(argv) + '\\n')\n"
        f"    return {code}\n"
    )
    path = target_dir / f"{module}.py"
    path.write_text(source, encoding="utf-8")
    return path


def _drop_cached(name: str):
    # Avoid a stale module object from a previous project being reused by name.
    for key in list(sys.modules):
        if key == name or key.endswith("." + name):
            mod = sys.modules.get(key)
            f = getattr(mod, "__file__", None) or ""
            if "spec-linter" in f or "spec_linter" in f:
                sys.modules.pop(key, None)


def _call(argv, project: Path, tool_root: Path):
    outputs = []
    _drop_cached("spec_linter")
    return hotdocs_cli.main(
        argv,
        tool_root=tool_root,
        input_fn=lambda *a, **k: "",
        output_fn=lambda *a, **k: outputs.append(a),
        env=dict(os.environ),
        cwd=project,
    )


def test_routed_verb_exit_codes_zero_then_seven(tmp_path):
    empty_tool_root = tmp_path / "tool_root_empty"
    empty_tool_root.mkdir()

    project_zero = tmp_path / "project_zero"
    project_zero.mkdir()
    _write_fake_component(project_zero, "gen/spec-linter", "spec_linter", 0, project_zero)

    project_seven = tmp_path / "project_seven"
    project_seven.mkdir()
    _write_fake_component(project_seven, "gen/spec-linter", "spec_linter", 7, project_seven)

    code_zero = _call(["lint"], project_zero, empty_tool_root)
    code_seven = _call(["lint"], project_seven, empty_tool_root)

    assert code_zero == 0
    assert code_seven == 7


def test_unknown_verb_version_and_missing_component_exit_codes(tmp_path):
    empty_tool_root = tmp_path / "tool_root_empty"
    empty_tool_root.mkdir()

    project = tmp_path / "project"
    project.mkdir()

    code_unknown = _call(["frobnicate"], project, empty_tool_root)
    code_version = _call(["--version"], project, empty_tool_root)
    code_missing = _call(["lint"], project, empty_tool_root)

    assert code_unknown == 2
    assert code_version == 0
    assert code_missing == 2