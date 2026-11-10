import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _get(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


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


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D13.md",
        "---\n"
        "id: D13\n"
        "title: Test decision\n"
        "status: ratified\n"
        "owners: [team-a]\n"
        "last_ratified_commit: abc1234\n"
        "---\n"
        "\n"
        "# D13\n"
        "\n"
        "Some decision text.\n",
    )

    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/bar/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Caches results.\n"
        "\n"
        "## Rationale\n"
        "\n"
        "This design follows D13.\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "requirements" / "R-BAR-001.md",
        "# R-BAR-001\n"
        "\n"
        "**R-BAR-001** — `bar()` MUST return cached results.\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "acceptance" / "AC-BAR-001.md",
        "# AC-BAR-001\n"
        "\n"
        "Covers: R-BAR-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a call to bar()\n"
        "When bar() is invoked\n"
        "Then it returns cached results\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "bar() -> dict\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )

    _write(
        repo_root / "specs" / "components" / "baz" / "component.md",
        "---\n"
        "id: comp-baz\n"
        "title: Baz\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/baz/\n"
        "depends_on: [comp-bar]\n"
        "---\n"
        "\n"
        "# Baz\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Baz uses bar's cache.\n",
    )
    _write(
        repo_root / "specs" / "components" / "baz" / "requirements" / "R-BAZ-001.md",
        "# R-BAZ-001\n"
        "\n"
        "**R-BAZ-001** — `baz()` MUST use bar's cached results.\n",
    )
    _write(
        repo_root / "specs" / "components" / "baz" / "acceptance" / "AC-BAZ-001.md",
        "# AC-BAZ-001\n"
        "\n"
        "Covers: R-BAZ-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a call to baz()\n"
        "When baz() is invoked\n"
        "Then it uses bar's cached results\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "components" / "baz" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "baz() -> dict\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "components" / "baz" / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def test_dependency_context_is_purpose_only_no_rationale_leak(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-baz", repo_root, mode="cold")

    dependency_context = _get(bundle, "dependency_context")
    assert dependency_context == {"comp-bar": "Caches results."}

    parts = []
    for field in ("component_id", "spec_bundle_hash", "spec", "interface", "constraints", "glossary"):
        value = _get(bundle, field)
        if isinstance(value, str):
            parts.append(value)
    for field in ("dependency_interfaces", "dependency_context", "dependency_usage", "vars"):
        value = _get(bundle, field)
        if isinstance(value, dict):
            for v in value.values():
                if isinstance(v, str):
                    parts.append(v)
    hint_code = _get(bundle, "hint_code")
    if isinstance(hint_code, dict):
        for v in hint_code.values():
            if isinstance(v, str):
                parts.append(v)
    elif isinstance(hint_code, str):
        parts.append(hint_code)

    full_text = "\n".join(parts)
    assert "D13" not in full_text
    assert "This design follows" not in full_text
    assert "Rationale" not in full_text