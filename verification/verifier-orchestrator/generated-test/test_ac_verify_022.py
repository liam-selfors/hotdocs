import verifier_orchestrator

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Bump** \u2014 a test term.\n"
)

PRODUCT = (
    "---\n"
    "id: P-BAR\n"
    "title: Bar capability\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Bar capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Bar bumps a number by one.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: bumping a number.\n"
    "- Out of scope: everything else.\n"
)

COMPONENT = (
    "---\n"
    "id: comp-bar\n"
    "title: Bar\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-BAR]\n"
    "---\n"
    "\n"
    "# Bar\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Bar bumps a number by one.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: bumping a number.\n"
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
    "- Initial draft.\n"
)

REQUIREMENT = (
    "# R-BAR-001\n"
    "\n"
    "**R-BAR-001** \u2014 `bump(x)` MUST return `x + 1`.\n"
)

ACCEPTANCE = (
    "# AC-BAR-001\n"
    "\n"
    "Covers: R-BAR-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When bump(x) is called\n"
    "Then it returns 3\n"
    "```\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "```\n"
    "bump(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "None.\n"
)

GEN_MODULE = (
    "def bump(x):\n"
    "    return x + 1\n"
)

GENERATED_TEST = (
    "import sys\n"
    "\n"
    "sys.path.insert(0, \"gen/bar\")\n"
    "\n"
    "import bar\n"
    "\n"
    "\n"
    "def test_bump_increments():\n"
    "    assert bar.bump(2) == 3\n"
    "    assert bar.bump(10) == 11\n"
    "    assert bar.bump(-1) == 0\n"
    "    assert bar.bump(0) == 1\n"
    "    assert type(bar.bump(2)) is int\n"
)

TEST_REL_PATH = "verification/bar/generated-test/test_ac_bar_001.py"


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root: Path):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    write(repo_root / "specs" / "product" / "P-BAR.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "bar"
    write(comp / "component.md", COMPONENT)
    write(comp / "requirements" / "R-BAR-001.md", REQUIREMENT)
    write(comp / "acceptance" / "AC-BAR-001.md", ACCEPTANCE)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "constraints.md", CONSTRAINTS)

    gen_dir = (repo_root / "gen" / "bar").resolve()
    write(gen_dir / "bar.py", GEN_MODULE)

    # Hand-written conftest above the generated tests: puts the ABSOLUTE
    # path of the original gen/bar/ first on sys.path and imports the
    # original module. If it ran during a mutant's test run, the test
    # would exercise the unmutated original and every mutant would survive.
    conftest = (
        "import sys\n"
        "\n"
        "sys.path.insert(0, " + repr(str(gen_dir)) + ")\n"
        "\n"
        "import bar  # noqa: F401\n"
    )
    write(repo_root / "verification" / "bar" / "conftest.py", conftest)

    # The cached generated test for AC-BAR-001.
    write(repo_root / TEST_REL_PATH, GENERATED_TEST)


def test_hand_conftest_cannot_rescue_mutants_mutation_score_is_one(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    def test_author(bundle):
        # Only used if the orchestrator decides to (re)author; returns the
        # very same test content, in TestAuthoringResult's shape.
        return {
            "component_id": "comp-bar",
            "criterion_id": "AC-BAR-001",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": TEST_REL_PATH, "content": GENERATED_TEST},
            "model_call_error": None,
        }

    report = verifier_orchestrator.verify(
        "comp-bar", repo_root, judge=None, test_author=test_author
    )

    try:
        detail = report.to_dict()
    except Exception:  # pragma: no cover - diagnostic only
        detail = report

    score = field(report, "mutation_score")
    assert score is not None, f"mutation_score is null: {detail!r}"
    assert float(score) == 1.0, f"expected mutation_score 1.0, got {score!r}: {detail!r}"