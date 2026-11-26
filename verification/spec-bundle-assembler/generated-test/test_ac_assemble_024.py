# hotdocs-criterion: sha256:f83decd65e11129349e538b11e6f7c2c4d670dc60068fe464fcc339961659b4b
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import spec_bundle_assembler


def component_files(slug, depends_on="[]", extra_frontmatter="", purpose="Foo doubles a number."):
    """The files of one fixture component, keyed by path under repo_root."""
    upper = slug.upper()
    base = f"specs/components/{slug}/"
    return {
        base + "component.md": (
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            f"depends_on: {depends_on}\n"
            + extra_frontmatter +
            "---\n"
            "\n"
            f"# {slug.capitalize()}\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"{purpose}\n"
        ),
        base + f"requirements/R-{upper}-001.md": (
            f"# R-{upper}-001\n"
            "\n"
            f"**R-{upper}-001** — `foo(x)` MUST return `2 * x`.\n"
        ),
        base + f"acceptance/AC-{upper}-001.md": (
            f"# AC-{upper}-001\n"
            "\n"
            f"Covers: R-{upper}-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
            "```\n"
        ),
        base + "interface/library.md": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        base + "constraints.md": "# Constraints\n\nNone.\n",
    }


def write_fixture(repo_root, files):
    files = {"specs/glossary.md": "# Glossary\n\n- **Foo** — a test term.\n", **files}
    for rel, text in files.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _gen_dir():
    return next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")


def _assert_lints_clean(repo_root):
    gen = _gen_dir()
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in (report["findings"] if isinstance(report, dict) else report.findings)
    ]


SPEC_BUNDLE_FIELDS = [
    "component_id",
    "spec_bundle_hash",
    "spec",
    "interface",
    "constraints",
    "dependency_interfaces",
    "dependency_context",
    "dependency_usage",
    "vars",
    "glossary",
    "hint_code",
    "spec_bundle_parts",
]


def test_driver_guidance_appended_to_testing_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fixture(repo_root, component_files("foo", extra_frontmatter="drivers: [fake]\n"))
    adapter = repo_root / "gen" / "driver-fake" / "driver_fake.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(
        "def guidance():\n"
        "    return {'test_author': " + repr("  Fake driver text.  ") + "}\n",
        encoding="utf-8",
    )

    _assert_lints_clean(repo_root)

    cb = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    testing = field(cb, "testing")
    assert testing.endswith("\n## Test driver: fake\n\nFake driver text."), repr(testing)

    sb = spec_bundle_assembler.assemble("comp-foo", repo_root)
    for name in SPEC_BUNDLE_FIELDS:
        value = field(sb, name)
        text = json.dumps(value, default=str, ensure_ascii=False) if not isinstance(value, str) else value
        assert "Fake driver text." not in text, name


def test_unknown_driver_raises_precondition_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    tool_root = _gen_dir().parent
    if (tool_root / "gen" / "driver-nodrv").exists():
        pytest.skip("tool root unexpectedly has gen/driver-nodrv/")

    files = {}
    files.update(component_files(
        "foo",
        depends_on="[comp-driver-nodrv]",
        extra_frontmatter="drivers: [nodrv]\n",
    ))
    files.update(component_files("driver-nodrv"))
    files["specs/architecture/test-driver-nodrv.md"] = (
        "---\n"
        "id: arch-test-driver-nodrv\n"
        "title: Test driver nodrv\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Test driver nodrv\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Any text.\n"
    )
    write_fixture(repo_root, files)

    assert not (repo_root / "gen" / "driver-nodrv").exists()

    _assert_lints_clean(repo_root)

    with pytest.raises(Exception) as excinfo:
        spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    exc = excinfo.value
    assert "PreconditionFailure" in [c.__name__ for c in type(exc).__mro__], type(exc)
    assert "unknown test driver: nodrv" in str(exc), str(exc)