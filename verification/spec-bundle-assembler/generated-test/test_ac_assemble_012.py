# hotdocs-criterion: sha256:2aa977f6fe2793585384726dc2cbe59325804527964eb88cda672a6c0ba4a82d
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


PURPOSE_TEXT = "Foo doubles a number, as the amber heron purpose phrase says."
SCOPE_TEXT = "Foo handles integers only, within the cobalt lantern scope phrase."
RATIONALE_TEXT = "Doubling was chosen because of the quixotic walrus rationale phrase."
OPEN_QUESTIONS_TEXT = "- Whether to triple instead, the velvet glacier question phrase."
CHANGE_LOG_TEXT = "- Initial version, the saffron marmot changelog phrase."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
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
        + PURPOSE_TEXT + "\n"
        "\n"
        "## Scope\n"
        "\n"
        + SCOPE_TEXT + "\n"
        "\n"
        "## Rationale\n"
        "\n"
        + RATIONALE_TEXT + "\n"
        "\n"
        "## Open questions\n"
        "\n"
        + OPEN_QUESTIONS_TEXT + "\n"
        "\n"
        "## Change log\n"
        "\n"
        + CHANGE_LOG_TEXT + "\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    write(
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
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    return load_module(path, "spec_linter")


def test_ac_assemble_012_cold_spec_excludes_rationale_open_questions_change_log(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    spec_text = field(bundle, "spec")
    assert isinstance(spec_text, str)

    assert PURPOSE_TEXT in spec_text
    assert SCOPE_TEXT in spec_text

    assert "quixotic walrus" not in spec_text
    assert "velvet glacier" not in spec_text
    assert "saffron marmot" not in spec_text
    assert "## Rationale" not in spec_text
    assert "## Open questions" not in spec_text
    assert "## Change log" not in spec_text