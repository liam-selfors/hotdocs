# hotdocs-criterion: sha256:28a28a52450b45cf17b67d5fedb72a2d80312e367dff5c4ea1190482a116b5bd
import time
from pathlib import Path

import verifier_orchestrator


SLUG = "loopy"
COMPONENT_ID = "comp-loopy"
CRITERION_ID = "AC-LOOPY-001"
REQUIREMENT_ID = "R-LOOPY-001"

CRITERION_TEXT = (
    "# AC-LOOPY-001\n"
    "\n"
    "Covers: R-LOOPY-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a number x\n"
    "When count_up is called with x\n"
    "Then it returns x for a nonnegative x and 0 otherwise\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-LOOPY-001\n"
    "\n"
    "**R-LOOPY-001** — `count_up(x)` MUST return `x` for a nonnegative "
    "integer `x` and `0` for a negative one.\n"
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "count_up(x: int) -> int\n"
    "```\n"
)

GLOSSARY_TEXT = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test term.\n"
)

CANDIDATE_SOURCE = (
    "def count_up(x):\n"
    "    i = 0\n"
    "    while i < x:\n"
    "        i = i + 1\n"
    "    return i\n"
)

GENERATED_TEST_SOURCE = (
    "import loopy\n"
    "\n"
    "\n"
    "def test_count_up_counts_to_x():\n"
    "    assert loopy.count_up(0) == 0\n"
    "    assert loopy.count_up(3) == 3\n"
    "    assert loopy.count_up(5) == 5\n"
    "    assert loopy.count_up(-2) == 0\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)
    write(
        repo_root / "specs" / "product" / "loopy.md",
        "---\n"
        "id: P-LOOPY\n"
        "title: Loopy\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Loopy\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Counting up.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Counting.\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-loopy\n"
        "title: Loopy\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-LOOPY]\n"
        "---\n"
        "\n"
        "# Loopy\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Loopy counts up to a number.\n",
    )
    write(comp / "requirements" / (REQUIREMENT_ID + ".md"), REQUIREMENT_TEXT)
    write(comp / "acceptance" / (CRITERION_ID + ".md"), CRITERION_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / SLUG / "loopy.py", CANDIDATE_SOURCE)

    assembler_source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr(INTERFACE_TEXT) + ",\n"
        "        'glossary': " + repr(GLOSSARY_TEXT) + ",\n"
        "        'dependency_interfaces': dict(),\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/loopy/generated-test/test_ac_loopy_001.py",
                "content": GENERATED_TEST_SOURCE,
            },
            "model_call_error": None,
        }

    return test_author


def test_non_terminating_mutant_is_killed_within_ten_seconds(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "test_author_calls.log"

    start = time.monotonic()
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_test_author(log_path)
    )
    elapsed = time.monotonic() - start

    assert elapsed < 10.0, "verify took " + repr(elapsed) + " seconds"

    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("called") >= 1

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1
    assert field(matching[0], "result") == "pass"

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    # Every mutant of count_up, including the one whose loop never
    # terminates, must count as killed: a timed-out mutant is killed.
    assert score == 1.0