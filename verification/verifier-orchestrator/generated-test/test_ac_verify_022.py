import verifier_orchestrator

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GENERATED_TEST = (
    "import widget\n"
    "\n"
    "\n"
    "def test_triple_values():\n"
    "    assert widget.triple(0) == 0\n"
    "    assert widget.triple(1) == 3\n"
    "    assert widget.triple(2) == 6\n"
    "    assert widget.triple(3) == 9\n"
    "    assert widget.triple(7) == 21\n"
    "    assert widget.triple(-4) == -12\n"
    "    assert type(widget.triple(2)) is int\n"
)

GENERATED_TEST_REL = "verification/widget/generated-test/test_ac_widget_001.py"


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    _write(
        repo_root / "specs" / "product" / "widget-capability.md",
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
        "The system can triple a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: tripling integers.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a number 2\n"
        "When it is tripled\n"
        "Then the result is 6\n"
        "```\n",
    )

    comp = repo_root / "specs" / "components" / "widget"
    _write(
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
        "Widget triples a number.\n",
    )
    _write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `triple(x)` MUST return `3 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When triple(x) is called\n"
        "Then it returns 6\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ntriple(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's real (unsealed) code: one function, no strings or
    # docstrings, so no equivalent mutants.
    gen_dir = repo_root / "gen" / "widget"
    _write(
        gen_dir / "widget.py",
        "def triple(x):\n"
        "    return x * 3\n",
    )

    # A hand conftest above the generated tests that would import the
    # ORIGINAL module first if it were ever loaded during a mutant run.
    _write(
        repo_root / "verification" / "widget" / "conftest.py",
        "import sys\n"
        "sys.path.insert(0, " + repr(str(gen_dir.resolve())) + ")\n"
        "import widget  # noqa: E402,F401\n",
    )

    # The cached generated test (Criterion test filename).
    _write(repo_root / GENERATED_TEST_REL, GENERATED_TEST)


def _test_author(bundle):
    # Fallback in case the implementation re-authors rather than using the
    # cached file: returns the same test, TestAuthoringResult-shaped.
    return {
        "component_id": "comp-widget",
        "criterion_id": "AC-WIDGET-001",
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": GENERATED_TEST_REL, "content": GENERATED_TEST},
        "model_call_error": None,
    }


def test_ac_verify_022_conftest_cannot_shield_mutants(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify(
        "comp-widget", repo_root, test_author=_test_author
    )

    score = field(report, "mutation_score")
    assert score is not None
    assert float(score) == 1.0