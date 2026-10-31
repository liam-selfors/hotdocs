"""AC-ASSIST-002: predicted_blast_radius lists exactly the components
reported by a faked impact-analyzer for the draft change."""
import tempfile
import shutil
import textwrap
from pathlib import Path

import spec_completeness_assistant


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_ac_assist_002_predicted_blast_radius_lists_impacted_components():
    repo_root = Path(tempfile.mkdtemp())
    try:
        invocations_file = repo_root / "invocations.log"
        invocations_literal = repr(str(invocations_file))

        # Fake spec-linter: gen/spec-linter/spec_linter.py
        _write(
            repo_root / "gen" / "spec-linter" / "spec_linter.py",
            textwrap.dedent(
                f"""
                INVOCATIONS_FILE = {invocations_literal}

                def lint(paths, repo_root, strict=False, judge=None):
                    with open(INVOCATIONS_FILE, "a") as f:
                        f.write("lint\\n")
                    return {{
                        "findings": [],
                        "summary": {{"hard_failures": 0, "warnings": 0, "skipped": 0}},
                    }}
                """
            ),
        )

        # Fake impact-analyzer: gen/impact-analyzer/impact_analyzer.py
        _write(
            repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
            textwrap.dedent(
                f"""
                INVOCATIONS_FILE = {invocations_literal}

                def compute_blast_radius(changed_ids, repo_root):
                    with open(INVOCATIONS_FILE, "a") as f:
                        f.write("compute_blast_radius:" + ",".join(changed_ids) + "\\n")
                    return {{
                        "impacted": [
                            {{"component_id": "comp-alpha", "reason": "direct", "via": None}},
                            {{"component_id": "comp-beta", "reason": "direct", "via": None}},
                        ],
                        "precondition_error": None,
                    }}
                """
            ),
        )

        # Fake spec-bundle-assembler: gen/spec-bundle-assembler/spec_bundle_assembler.py
        _write(
            repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
            textwrap.dedent(
                f"""
                INVOCATIONS_FILE = {invocations_literal}

                def assemble(component_id, repo_root, mode="cold"):
                    with open(INVOCATIONS_FILE, "a") as f:
                        f.write("assemble:" + component_id + ":" + mode + "\\n")
                    return {{
                        "component_id": component_id,
                        "spec_bundle_hash": "sha256:fake",
                        "spec": "fake spec body",
                        "interface": "fake interface body",
                        "constraints": "fake constraints body",
                        "dependency_interfaces": {{}},
                        "dependency_context": {{}},
                        "dependency_usage": {{}},
                        "vars": {{}},
                        "glossary": "fake glossary body",
                        "hint_code": ({{"placeholder.py": "# fake"}} if mode == "hint" else None),
                    }}

                def assemble_criterion(component_id, criterion_id, repo_root):
                    with open(INVOCATIONS_FILE, "a") as f:
                        f.write("assemble_criterion:" + component_id + ":" + criterion_id + "\\n")
                    return {{
                        "component_id": component_id,
                        "criterion_id": criterion_id,
                        "covers": "R-FAKE-001",
                        "criterion_text": "fake criterion text",
                        "requirement_text": "fake requirement text",
                        "interface": "fake interface body",
                        "glossary": "fake glossary body",
                    }}
                """
            ),
        )

        # Fake generator: gen/generator/generator.py
        _write(
            repo_root / "gen" / "generator" / "generator.py",
            textwrap.dedent(
                f"""
                INVOCATIONS_FILE = {invocations_literal}

                def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
                    with open(INVOCATIONS_FILE, "a") as f:
                        f.write("generate\\n")
                    component_id = bundle.get("component_id") if isinstance(bundle, dict) else getattr(bundle, "component_id", None)
                    return {{
                        "component_id": component_id,
                        "spec_bundle_hash": "sha256:fake",
                        "model": model,
                        "prompt_version": "v1",
                        "cache_hit": False,
                        "files": {{"fake_module.py": "# fake generated content"}},
                        "model_call_error": None,
                        "refused": None,
                        "retry_feedback": retry_feedback,
                    }}
                """
            ),
        )

        report = spec_completeness_assistant.assist(["comp-alpha"], repo_root)

        predicted_blast_radius = _get(report, "predicted_blast_radius")
        assert predicted_blast_radius is not None
        assert sorted(predicted_blast_radius) == ["comp-alpha", "comp-beta"]

        assert invocations_file.exists()
        lines = [
            line.strip()
            for line in invocations_file.read_text().splitlines()
            if line.strip()
        ]

        assert any(line.startswith("compute_blast_radius") for line in lines)

        assemble_calls = {line for line in lines if line.startswith("assemble:")}
        assert assemble_calls == {
            "assemble:comp-alpha:hint",
            "assemble:comp-beta:hint",
        }
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)