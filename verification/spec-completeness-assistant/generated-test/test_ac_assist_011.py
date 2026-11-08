import importlib.util
import shutil
import sys

import spec_completeness_assistant as _real_module


def _load_copy(module_path, module_name="spec_completeness_assistant"):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


SPEC_LINTER_STUB = """
def lint(paths, repo_root, strict=False, judge=None):
    return {
        "findings": [],
        "summary": {"hard_failures": 0, "warnings": 0, "skipped": 0},
    }
"""

IMPACT_ANALYZER_STUB_TOOL_ROOT = """
def compute_blast_radius(changed_ids, repo_root):
    return {
        "impacted": [
            {"component_id": "comp-tool", "reason": "direct", "via": None}
        ],
        "precondition_error": None,
    }
"""

IMPACT_ANALYZER_STUB_REPO_ROOT = """
def compute_blast_radius(changed_ids, repo_root):
    return {
        "impacted": [
            {"component_id": "comp-mine", "reason": "direct", "via": None}
        ],
        "precondition_error": None,
    }
"""

SPEC_BUNDLE_ASSEMBLER_STUB = """
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:fake",
        "spec": "",
        "interface": "",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": {} if mode == "hint" else None,
    }
"""


def _setup_tool_root(tool_root):
    module_target = (
        tool_root
        / "gen"
        / "spec-completeness-assistant"
        / "spec_completeness_assistant.py"
    )
    module_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_real_module.__file__, module_target)

    _write(tool_root / "gen" / "spec-linter" / "spec_linter.py", SPEC_LINTER_STUB)
    _write(
        tool_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        IMPACT_ANALYZER_STUB_TOOL_ROOT,
    )
    _write(
        tool_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        SPEC_BUNDLE_ASSEMBLER_STUB,
    )

    return module_target


def test_dependency_resolved_from_tool_root_when_repo_root_lacks_gen(tmp_path):
    tool_root = tmp_path / "tool_root"
    repo_root = tmp_path / "repo_root"
    repo_root.mkdir()

    module_target = _setup_tool_root(tool_root)

    module = _load_copy(module_target)

    report = module.assist(["R-FOO-001"], repo_root)

    blast_radius = _get(report, "predicted_blast_radius")
    assert blast_radius == ["comp-tool"]


def test_dependency_resolved_from_repo_root_when_present(tmp_path):
    tool_root = tmp_path / "tool_root"
    repo_root = tmp_path / "repo_root"
    repo_root.mkdir()

    module_target = _setup_tool_root(tool_root)

    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        IMPACT_ANALYZER_STUB_REPO_ROOT,
    )

    module = _load_copy(module_target)

    report = module.assist(["R-FOO-001"], repo_root)

    blast_radius = _get(report, "predicted_blast_radius")
    assert blast_radius == ["comp-mine"]