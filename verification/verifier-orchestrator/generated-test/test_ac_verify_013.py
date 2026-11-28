# hotdocs-criterion: sha256:9a1ff7509968ff9ec4f18f8dd6260d512ea93a4eef94de3ecf7089fd35247fc1
import shutil
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
MODULE = "widget_maker"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"
CAPABILITY_ID = "P-WIDGET"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_real_compiler(repo_root):
    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]
    source = live / "pipeline" / "criterion-compiler"
    target = repo_root / "pipeline" / "criterion-compiler"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / SLUG

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** - a thing with a foo.\n",
    )

    write(
        repo_root / "specs" / "product" / (CAPABILITY_ID + ".md"),
        "---\n"
        + "id: " + CAPABILITY_ID + "\n"
        + "title: Widget capability\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# Widget capability\n"
        + "\n"
        + "Makes widgets.\n",
    )

    write(
        comp_dir / "component.md",
        "---\n"
        + "id: " + COMPONENT_ID + "\n"
        + "title: Widget maker\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "depends_on: []\n"
        + "realizes: [" + CAPABILITY_ID + "]\n"
        + "---\n"
        + "\n"
        + "# Widget maker\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Makes a widget whose foo is 5.\n",
    )

    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        comp_dir / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n"
        + "\n"
        + "**" + REQUIREMENT_ID + "** - `make_widget(x)` MUST return a widget "
        + "whose `foo` attribute is `5`.\n",
    )

    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        + "\n"
        + "```\n"
        + "make_widget(x) -> Widget\n"
        + "```\n"
        + "\n"
        + "Returns an object with attribute `foo`.\n",
    )

    write(
        comp_dir / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        + "\n"
        + "Covers: " + REQUIREMENT_ID + "\n"
        + "Kind: compiled\n"
        + "\n"
        + "```gherkin\n"
        + "Given a seed is 1\n"
        + "When make_widget is invoked with [seed]\n"
        + "Then foo equals 5\n"
        + "```\n",
    )

    write(
        repo_root / "gen" / SLUG / (MODULE + ".py"),
        "class Widget:\n"
        + "    def __init__(self, foo):\n"
        + "        self.foo = foo\n"
        + "\n"
        + "\n"
        + "def make_widget(x):\n"
        + "    return Widget(3)\n",
    )

    copy_real_compiler(repo_root)


def test_failed_compiled_criterion_carries_expected_and_actual(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    criterion = matching[0]

    assert field(criterion, "kind") == "compiled", criterion
    assert field(criterion, "result") == "fail", criterion

    detail = field(criterion, "failure_detail")
    assert detail is not None, criterion

    message = field(detail, "message")
    assert isinstance(message, str) and message.strip(), detail

    expected = field(detail, "expected")
    actual = field(detail, "actual")

    assert expected == 5, detail
    assert type(expected) is int, detail
    assert actual == 3, detail
    assert type(actual) is int, detail