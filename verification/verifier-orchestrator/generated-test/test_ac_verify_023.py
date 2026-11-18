# hotdocs-criterion: sha256:cb7f16467bb9804a167106355e6f3c7c0e5a8ddd09bffe92e75f13dd6eb5f715
import hashlib
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

CRITERION_TEXT = (
    "Given x = 2\n"
    "When make_widget(x) is called\n"
    "Then it returns 4"
)
REQUIREMENT_TEXT = "**R-WIDGET-001** — `make_widget(x)` MUST return `2 * x`."

TEST_BODY_PASS = (
    "import widget\n"
    "\n"
    "\n"
    "def test_make_widget_doubles():\n"
    "    assert widget.make_widget(2) == 4\n"
)

TEST_BODY_FAIL = (
    "import widget\n"
    "\n"
    "\n"
    "def test_make_widget_wrong():\n"
    "    assert widget.make_widget(2) == 5\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def correct_header():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest + "\n"


def zero_header():
    return "# hotdocs-criterion: sha256:" + ("0" * 64) + "\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, cached_content):
    repo_root = Path(repo_root)

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )

    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets double numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When make_widget(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )

    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
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
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n\n" + REQUIREMENT_TEXT + "\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + CRITERION_TEXT + "\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nmake_widget(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / SLUG / "widget.py",
        "def make_widget(x):\n    return 2 * x\n",
    )

    assembler_src = (
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': " + repr("# Library\n\n```\nmake_widget(x: int) -> int\n```") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )

    if cached_content is not None:
        write(
            repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py",
            cached_content,
        )


def make_stand_in(log_path):
    log_path = Path(log_path)

    def stand_in(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": correct_header() + TEST_BODY_PASS,
            },
        }

    return stand_in


def call_count(log_path):
    log_path = Path(log_path)
    if not log_path.exists():
        return 0
    return len([ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()])


def find_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def test_zero_hash_header_is_stale_and_reauthored(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, zero_header() + TEST_BODY_PASS)
    log = tmp_path / "calls.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_stand_in(log)
    )
    assert call_count(log) == 1
    assert field(find_criterion(report), "result") == "pass"


def test_missing_header_is_stale_and_reauthored(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, TEST_BODY_PASS)
    log = tmp_path / "calls.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_stand_in(log)
    )
    assert call_count(log) == 1
    assert field(find_criterion(report), "result") == "pass"


def test_correct_header_is_cache_hit_no_authoring(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, correct_header() + TEST_BODY_PASS)
    log = tmp_path / "calls.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_stand_in(log)
    )
    assert call_count(log) == 0
    assert field(find_criterion(report), "result") == "pass"


def test_correct_header_failing_test_is_implementation_failure(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, correct_header() + TEST_BODY_FAIL)
    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)
    crit = find_criterion(report)
    assert field(crit, "result") == "fail"
    assert field(crit, "failure_origin") == "implementation"