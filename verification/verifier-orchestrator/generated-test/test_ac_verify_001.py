import json
from pathlib import Path

import pytest

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_COMPILER_TEMPLATE = '''import json
from dataclasses import dataclass, field
from pathlib import Path

GATE_VERSION = "criterion-compiler@1.0.0"
_LOG_PATH = __LOG_PATH__
_MODULE = __MODULE__


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _source():
    return (
        "import " + _MODULE + "\\n"
        "\\n"
        "\\n"
        "def test_compiled_criterion():\\n"
        "    result = " + _MODULE + ".triple(3)\\n"
        "    assert result == 9\\n"
    )


@dataclass
class ParsedCriterion:
    criterion_id: str
    covers: str
    kind: str
    gherkin: str
    file: str


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


def compile_criterion(criterion, surface=None):
    _log({"fn": "compile_criterion", "criterion_id": _get(criterion, "criterion_id")})
    return {"status": "compiled", "source": _source()}


def _criteria(repo_root, slug):
    acc = Path(repo_root) / "specs" / "components" / slug / "acceptance"
    found = []
    if acc.is_dir():
        for p in sorted(acc.glob("AC-*.md")):
            text = p.read_text(encoding="utf-8")
            covers = None
            kind = None
            for line in text.splitlines():
                s = line.strip()
                if covers is None and s.startswith("Covers:"):
                    covers = s[len("Covers:"):].strip()
                elif covers is not None and kind is None and s.startswith("Kind:"):
                    kind = s[len("Kind:"):].strip()
            found.append((p.stem, covers, kind))
    return found


def compile(component_id, repo_root, target="pytest", out_dir=None):
    repo_root = Path(repo_root)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    if out_dir is not None:
        out = Path(out_dir)
    else:
        out = repo_root / "verification" / slug / "compiled"
    out.mkdir(parents=True, exist_ok=True)
    outputs = []
    compiled_ids = []
    skipped = 0
    for cid, covers, kind in _criteria(repo_root, slug):
        if kind != "compiled":
            skipped += 1
            continue
        dest = out / ("test_" + cid.lower().replace("-", "_") + ".py")
        dest.write_text(_source(), encoding="utf-8")
        try:
            rel = str(dest.resolve().relative_to(repo_root.resolve()))
        except ValueError:
            rel = str(dest.resolve())
        outputs.append({
            "criterion_id": cid,
            "covers": covers,
            "status": "compiled",
            "file": rel,
        })
        compiled_ids.append(cid)
    _log({"fn": "compile", "component_id": component_id, "criteria": compiled_ids})
    return CompileReport(
        outputs=outputs,
        gate_version=GATE_VERSION,
        summary={
            "compiled": len(compiled_ids),
            "errors": 0,
            "skipped_non_compiled_kind": skipped,
        },
    )
'''


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path, slug, impl_expr):
    upper = slug.upper()
    comp_id = "comp-" + slug
    r_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    module = slug.replace("-", "_")

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Tripling** — multiplying a number by three.\n",
    )

    write(
        repo_root / "specs" / "product" / "tripling.md",
        "---\n"
        "id: P-TRIPLE\n"
        "title: Tripling\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Tripling\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Users can triple a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: tripling integers.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-TRIPLE-001\n"
        "\n"
        "Covers: P-TRIPLE\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a number\n"
        "When it is tripled\n"
        "Then the result is three times the number\n"
        "```\n",
    )

    comp_dir = repo_root / "specs" / "components" / slug
    write(
        comp_dir / "component.md",
        "---\n"
        "id: " + comp_id + "\n"
        "title: Tripler\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-TRIPLE]\n"
        "---\n"
        "\n"
        "# Tripler\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Tripler triples a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: tripling integers.\n"
        "- Out of scope: everything else.\n"
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
        "- Initial draft.\n",
    )
    write(
        comp_dir / "requirements" / (r_id + ".md"),
        "# " + r_id + "\n\n**" + r_id + "** — `triple(x)` MUST return `3 * x`.\n",
    )
    write(
        comp_dir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + r_id + "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a n is 3\n"
        "When triple is invoked with [n]\n"
        "Then result equals 9\n"
        "```\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\ntriple(x: int) -> int\n```\n",
    )
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's real generated code: flat module, no __init__.py.
    write(
        repo_root / "gen" / slug / (module + ".py"),
        "def triple(x: int) -> int:\n    return " + impl_expr + "\n",
    )

    # Mock criterion-compiler planted where verify loads it from.
    fake = (
        FAKE_COMPILER_TEMPLATE
        .replace("__LOG_PATH__", repr(str(log_path)))
        .replace("__MODULE__", repr(module))
    )
    write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", fake)

    return comp_id, ac_id


def read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.parametrize(
    "slug, impl_expr, expected",
    [
        ("tripler", "3 * x", "pass"),
        ("triplebug", "3 * x + 1", "fail"),
    ],
)
def test_compiled_criterion_dispatched_to_compiler_and_result_reported(
    tmp_path, slug, impl_expr, expected
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "compiler_invocations.log"

    comp_id, ac_id = build_fixture(repo_root, log_path, slug, impl_expr)

    report = verifier_orchestrator.verify(comp_id, repo_root)

    # The mock compiler was invoked for that criterion.
    records = read_log(log_path)
    assert records, "mock criterion-compiler was never invoked"
    invoked_for_criterion = any(
        (rec.get("fn") == "compile_criterion" and rec.get("criterion_id") == ac_id)
        or (
            rec.get("fn") == "compile"
            and rec.get("component_id") in (comp_id, slug)
            and ac_id in (rec.get("criteria") or [])
        )
        for rec in records
    )
    assert invoked_for_criterion, records

    # Its pass/fail result appears in the report under that criterion's id.
    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == ac_id]
    assert len(entries) == 1, criteria
    assert field(entries[0], "result") == expected