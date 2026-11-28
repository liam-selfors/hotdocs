# hotdocs-criterion: sha256:85d5d30a04476cbc958167f2ccfe4709ac6c2c75dfec09a9d3eef9f4f35ac519
"""AC-VERIFY-007: verify produces exactly one VerificationReport containing
per-criterion results, mutation_score, interface_drift and overall."""

import shutil
from pathlib import Path

import verifier_orchestrator


SLUG = "widget-check"
COMPONENT_ID = "comp-widget-check"
MODULE = "widget_check"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ASSEMBLER_SOURCE = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    covers = 'R-' + criterion_id[3:]\n"
    "    base = Path(repo_root) / 'specs' / 'components' / 'widget-check'\n"
    "    acc = base / 'acceptance' / (criterion_id + '.md')\n"
    "    req = base / 'requirements' / (covers + '.md')\n"
    "    lib = base / 'interface' / 'library.md'\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': covers,\n"
    "        'criterion_text': acc.read_text(encoding='utf-8') if acc.is_file() else '',\n"
    "        'requirement_text': req.read_text(encoding='utf-8') if req.is_file() else '',\n"
    "        'interface': lib.read_text(encoding='utf-8') if lib.is_file() else '',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SOURCE = (
    "class ProbeReport:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
    "    return ProbeReport()\n"
)

GENERATED_TEST_SOURCE = (
    "def test_widget_check_passes():\n"
    "    assert 1 + 1 == 2\n"
)


def build_fixture(root):
    comp = root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget Check\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "# Widget Check\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component for verification tests.\n",
    )
    write(
        root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "# Widget\n"
        "\n"
        "A fixture capability.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n\nThis component exposes no functions.\n",
    )
    write(
        comp / "requirements" / "R-WIDG-001.md",
        "# R-WIDG-001\n\n**R-WIDG-001** — This component MUST behave.\n",
    )
    write(
        comp / "requirements" / "R-WIDG-002.md",
        "# R-WIDG-002\n\n**R-WIDG-002** — This component MUST be clear.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDG-001.md",
        "# AC-WIDG-001\n"
        "\n"
        "Covers: R-WIDG-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is checked\n"
        "Then the check passes\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDG-002.md",
        "# AC-WIDG-002\n"
        "\n"
        "Covers: R-WIDG-002\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget spec\n"
        "When it is read\n"
        "Then it is clear\n"
        "```\n",
    )
    write(root / "gen" / SLUG / (MODULE + ".py"), "")
    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)

    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]
    compiler_src = live / "pipeline" / "criterion-compiler"
    if compiler_src.is_dir():
        shutil.copytree(
            compiler_src,
            root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__"),
        )


def test_verify_produces_one_structured_report(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    build_fixture(root)
    author_log = tmp_path / "author.log"
    judge_log = tmp_path / "judge.log"

    def author(bundle):
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": "AC-WIDG-001",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v-test",
            "cache_hit": False,
            "file": {
                "path": "verification/widget-check/generated-test/test_ac_widg_001.py",
                "content": GENERATED_TEST_SOURCE,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    def judge(bundle):
        with open(judge_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {"result": "pass", "rationale": "clear enough"}

    report = verifier_orchestrator.verify(
        COMPONENT_ID, root, judge=judge, test_author=author
    )

    # Exactly one report: a single object, not a list or collection of reports.
    assert report is not None
    assert not isinstance(report, (list, tuple, set))
    assert field(report, "component_id") == COMPONENT_ID

    # Per-criterion results: one entry per acceptance criterion.
    criteria = field(report, "criteria")
    assert isinstance(criteria, list)
    ids = sorted(c["id"] for c in criteria)
    assert ids == ["AC-WIDG-001", "AC-WIDG-002"]
    for c in criteria:
        assert c["result"] in ("pass", "fail", "skipped")
    by_id = {c["id"]: c for c in criteria}
    gen_c = by_id["AC-WIDG-001"]
    assert gen_c["kind"] == "generated-test"
    assert gen_c["covers"] == "R-WIDG-001"
    assert gen_c["result"] == "pass"
    assert gen_c["test_authoring"]["model"] == "fake-model"
    judge_c = by_id["AC-WIDG-002"]
    assert judge_c["kind"] == "llm-judge"
    assert judge_c["covers"] == "R-WIDG-002"
    assert judge_c["result"] == "pass"
    assert author_log.is_file()
    assert judge_log.is_file()

    # mutation_score
    score = field(report, "mutation_score")
    assert score is None or (isinstance(score, (int, float)) and 0.0 <= score <= 1.0)

    # interface_drift
    assert isinstance(field(report, "interface_drift"), bool)

    # overall
    assert field(report, "overall") in ("pass", "fail")

    # Declared assets (the implicit python asset first).
    assets = field(report, "assets")
    assert isinstance(assets, list)
    assert assets and assets[0]["kind"] == "python"

    # The JSON form carries the same structure.
    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    for key in ("component_id", "criteria", "mutation_score", "interface_drift", "overall", "assets"):
        assert key in as_dict
    assert as_dict["overall"] == field(report, "overall")
    assert as_dict["interface_drift"] == field(report, "interface_drift")
    assert as_dict["mutation_score"] == score
    assert sorted(c["id"] for c in as_dict["criteria"]) == ids