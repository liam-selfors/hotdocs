# hotdocs-criterion: sha256:d0050b780a8b488b795e651f297b9d94a7fcb865b2b613649f7938af60c12c75
import importlib.util
import sys
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-abacus"
SLUG = "abacus"
MODULE = "abacus"
CRITERION_ID = "AC-ABACUS-001"
REQUIREMENT_ID = "R-ABACUS-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPILER_BODY = r'''
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "criterion-compiler@1.0.0"


@dataclass
class ParsedCriterion:
    criterion_id: str = ""
    covers: str = ""
    kind: str = "compiled"
    gherkin: str = ""
    file: str = ""


@dataclass
class InterfaceSurface:
    functions: dict = field(default_factory=dict)
    types: dict = field(default_factory=dict)
    module_name: str = ""


@dataclass
class CompileReport:
    outputs: list
    gate_version: str
    summary: dict


def _log(line):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _source():
    return (
        "import abacus\n"
        "\n"
        "\n"
        "def test_ac_abacus_001():\n"
        "    assert abacus.tally(2) == " + repr(EXPECTED) + "\n"
    )


def compile(component_id, repo_root, target="pytest", out_dir=None):
    repo_root = Path(repo_root)
    if component_id.startswith("comp-"):
        slug = component_id[len("comp-"):]
    else:
        slug = component_id
    acc = repo_root / "specs" / "components" / slug / "acceptance"
    if out_dir is not None:
        out = Path(out_dir)
        if not out.is_absolute():
            out = repo_root / out
    else:
        out = repo_root / "verification" / slug / "compiled"
    outputs = []
    skipped = 0
    for path in sorted(acc.glob("AC-*.md")):
        text = path.read_text(encoding="utf-8")
        if "Kind: compiled" not in text:
            skipped += 1
            continue
        cid = path.stem
        covers = ""
        for line in text.splitlines():
            if line.startswith("Covers:"):
                covers = line.split(":", 1)[1].strip()
                break
        _log("compile " + cid)
        out.mkdir(parents=True, exist_ok=True)
        target_file = out / ("test_" + cid.lower().replace("-", "_") + ".py")
        target_file.write_text(_source(), encoding="utf-8")
        try:
            rel = str(target_file.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            rel = str(target_file.resolve())
        outputs.append({
            "criterion_id": cid,
            "covers": covers,
            "status": "compiled",
            "file": rel,
        })
    return CompileReport(
        outputs=outputs,
        gate_version=GATE_VERSION,
        summary={
            "compiled": len(outputs),
            "errors": 0,
            "skipped_non_compiled_kind": skipped,
        },
    )


def compile_criterion(criterion, surface=None):
    if isinstance(criterion, dict):
        cid = criterion.get("criterion_id", "")
    else:
        cid = getattr(criterion, "criterion_id", "")
    _log("compile_criterion " + str(cid))
    return {"status": "compiled", "source": _source()}
'''


ASSEMBLER_BODY = r'''
def assemble_criterion(component_id, criterion_id, repo_root):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-ABACUS-001",
        "criterion_text": "Given a n is 2\nWhen tally is invoked with [n]\nThen value equals 4",
        "requirement_text": "**R-ABACUS-001** — `tally(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\ntally(x: int) -> int\n```",
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "dependency_interfaces": {},
    }
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path, expected_value):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "P-ABACUS.md",
        "---\n"
        "id: P-ABACUS\n"
        "title: Abacus capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Abacus capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubling numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-ABACUS-001\n"
        "\n"
        "Covers: P-ABACUS\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a n is 2\n"
        "When tally is invoked with [n]\n"
        "Then value equals 4\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-abacus\n"
        "title: Abacus\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-ABACUS]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Abacus\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Abacus doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial.\n",
    )
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# R-ABACUS-001\n\n**R-ABACUS-001** — `tally(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# AC-ABACUS-001\n"
        "\n"
        "Covers: R-ABACUS-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a n is 2\n"
        "When tally is invoked with [n]\n"
        "Then value equals 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ntally(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / SLUG / (MODULE + ".py"),
        "def tally(x):\n    return 2 * x\n",
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_BODY,
    )
    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "EXPECTED = " + repr(expected_value) + "\n"
        + COMPILER_BODY,
    )


@pytest.mark.parametrize(
    "expected_value, expected_result",
    [(4, "pass"), (5, "fail")],
)
def test_compiled_criterion_dispatched_to_compiler_and_reported(
    tmp_path, expected_value, expected_result
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "compiler_calls.log"
    build_fixture(repo_root, log_path, expected_value)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    # The mock compiler was invoked for that criterion.
    assert log_path.is_file(), "mock criterion-compiler was never invoked"
    calls = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert any(CRITERION_ID in line for line in calls), calls

    # Its pass/fail result appears in the report under the criterion's id.
    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]
    assert field(entry, "result") == expected_result, entry