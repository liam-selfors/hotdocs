import spec_bundle_assembler

import importlib.util
import sys
from pathlib import Path


PURPOSE_TOKEN = "kumquatpurposesentinel"
SCOPE_TOKEN = "marmaladescopesentinel"
RATIONALE_TOKEN = "zeppelinrationalesentinel"
OPEN_Q_TOKEN = "quagmireopenquestionsentinel"
CHANGELOG_TOKEN = "xylophonechangelogsentinel"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )

    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Foo doubles a number. {PURPOSE_TOKEN}\n"
        "\n"
        "## Scope\n"
        "\n"
        f"Foo handles integer inputs only. {SCOPE_TOKEN}\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"Doubling was chosen because it is simple. {RATIONALE_TOKEN}\n"
        "\n"
        "## Open questions\n"
        "\n"
        f"Whether foo should ever triple a number. {OPEN_Q_TOKEN}\n"
        "\n"
        "## Change log\n"
        "\n"
        f"Initial version written. {CHANGELOG_TOKEN}\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")


def test_ac_assemble_012_target_component_md_excludes_rationale_open_questions_change_log(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    spec_text = field(bundle, "spec")
    assert isinstance(spec_text, str)

    # Purpose and Scope text are included.
    assert PURPOSE_TOKEN in spec_text
    assert SCOPE_TOKEN in spec_text

    # Rationale, Open questions, and Change log text are excluded.
    assert RATIONALE_TOKEN not in spec_text
    assert OPEN_Q_TOKEN not in spec_text
    assert CHANGELOG_TOKEN not in spec_text