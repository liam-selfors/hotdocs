# hotdocs-criterion: sha256:82543183eabc30fdcbbc606c36aa77bbeae2686e881bff0704c931d19bc4c1fc
import shutil
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
MODULE = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FENCE = "```"

GENERATED_CRITERION_TEXT = (
    "Given the widget module\n"
    "When double_it is called with 2 and with 3\n"
    "Then it returns 4 and 6\n"
)
GENERATED_REQUIREMENT_TEXT = (
    "**R-WIDGET-001** — `double_it(x)` MUST return `2 * x`."
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    + FENCE + "\n"
    "double_it(x: int) -> int\n"
    + FENCE + "\n"
)

GENERATED_TEST_SOURCE = (
    "import widget\n"
    "\n"
    "\n"
    "def test_double_it():\n"
    "    assert widget.double_it(2) == 4\n"
    "    assert widget.double_it(3) == 6\n"
)


def acceptance(ac_id, r_id, kind, steps):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + r_id + "\n"
        "Kind: " + kind + "\n"
        "\n"
        + FENCE + "gherkin\n"
        + steps
        + FENCE + "\n"
    )


def build_fixture(repo_root, log_path):
    # Glossary
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a test term.\n")

    # Product capability the unsealed fixture realizes
    write(
        repo_root / "specs" / "product" / "widgets.md",
        "---\n"
        "id: P-WIDGETS\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widgets\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets double numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Doubling.\n"
        "\n"
        "### CS-WIDGETS-001\n"
        "\n"
        "Covers: P-WIDGETS\n"
        "Kind: compiled\n"
        "\n"
        + FENCE + "gherkin\n"
        "Given a n is 2\n"
        "When double_it is invoked with [n]\n"
        "Then value equals 4\n"
        + FENCE + "\n",
    )

    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGETS]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget doubles a number.\n"
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
    write(comp / "requirements" / "R-WIDGET-001.md", "# R-WIDGET-001\n\n" + GENERATED_REQUIREMENT_TEXT + "\n")
    write(
        comp / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\n**R-WIDGET-002** — The widget documentation MUST be clear.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        acceptance("AC-WIDGET-001", "R-WIDGET-001", "generated-test", GENERATED_CRITERION_TEXT),
    )
    write(
        comp / "acceptance" / "AC-WIDGET-002.md",
        acceptance(
            "AC-WIDGET-002",
            "R-WIDGET-002",
            "llm-judge",
            "Given the widget documentation\n"
            "When a reviewer reads it\n"
            "Then it is clear\n",
        ),
    )
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's real code: one mutation site (x * 2), killed by the test
    write(
        repo_root / "gen" / SLUG / (MODULE + ".py"),
        "def double_it(x: int) -> int:\n"
        "    return x * 2\n",
    )

    # spec-bundle-assembler stand-in
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "CRITERION_TEXTS = " + repr({
            "AC-WIDGET-001": GENERATED_CRITERION_TEXT,
            "AC-WIDGET-002": "Given the widget documentation\nWhen a reviewer reads it\nThen it is clear\n",
        }) + "\n"
        "REQUIREMENT_TEXTS = " + repr({
            "AC-WIDGET-001": GENERATED_REQUIREMENT_TEXT,
            "AC-WIDGET-002": "**R-WIDGET-002** — The widget documentation MUST be clear.",
        }) + "\n"
        "COVERS = " + repr({"AC-WIDGET-001": "R-WIDGET-001", "AC-WIDGET-002": "R-WIDGET-002"}) + "\n"
        "INTERFACE = " + repr(INTERFACE_TEXT) + "\n"
        "LOG = " + repr(str(log_path.parent / "assembler.log")) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': COVERS.get(criterion_id, ''),\n"
        "        'criterion_text': CRITERION_TEXTS.get(criterion_id, ''),\n"
        "        'requirement_text': REQUIREMENT_TEXTS.get(criterion_id, ''),\n"
        "        'interface': INTERFACE,\n"
        "        'glossary': '# Glossary',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n",
    )

    # Supply the real criterion compiler in repo_root, never relying on the tool-root fallback
    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]
    live_compiler = live / "pipeline" / "criterion-compiler"
    if live_compiler.is_dir():
        shutil.copytree(
            live_compiler,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__"),
        )


def make_test_author(log_path):
    def test_author(bundle):
        criterion_id = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id", None)
        if criterion_id is None:
            try:
                criterion_id = bundle["criterion_id"]
            except Exception:
                criterion_id = "?"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": GENERATED_TEST_SOURCE,
            },
            "model_call_error": None,
        }

    return test_author


def test_skipped_llm_judge_alone_does_not_fail_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "test_author.log"
    build_fixture(repo_root, log_path)

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=make_test_author(log_path)
    )

    criteria = field(report, "criteria")
    by_id = {c["id"]: c for c in criteria}

    # Preconditions of the Given clause
    assert log_path.is_file(), "test_author stand-in was never called"
    assert "AC-WIDGET-001" in log_path.read_text(encoding="utf-8")
    assert by_id["AC-WIDGET-001"]["kind"] == "generated-test"
    assert by_id["AC-WIDGET-001"]["result"] == "pass", by_id["AC-WIDGET-001"]
    for c in criteria:
        if c["kind"] in ("compiled", "generated-test"):
            assert c["result"] == "pass", c
    assert by_id["AC-WIDGET-002"]["kind"] == "llm-judge"
    assert by_id["AC-WIDGET-002"]["result"] == "skipped", by_id["AC-WIDGET-002"]
    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 1.0
    assert field(report, "interface_drift") is False

    # Then: overall verdict is pass — a skipped finding alone never causes fail
    assert field(report, "overall") == "pass"