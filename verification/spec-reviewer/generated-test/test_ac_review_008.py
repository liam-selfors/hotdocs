# hotdocs-criterion: sha256:b62104a15d247f74990f9bbe9ec7c723791abbd271439843dc708ecc49a3375b
import importlib.util
import sys
from pathlib import Path

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_spec_linter():
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def assert_lint_clean(repo_root):
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root, assets_line=None):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    frontmatter = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
    )
    if assets_line is not None:
        frontmatter = frontmatter + assets_line + "\n"
    frontmatter = frontmatter + "---\n"
    write(
        comp / "component.md",
        frontmatter
        + "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
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
    return comp


ASSETS_OK = "assets: [javascript:static/app.js, javascript:static/b.js]"
ASSETS_BROKEN = "assets: [javascript:static/app.js, broken]"
EXPECTED_MESSAGE = (
    "`static/app.js` has no interface file "
    "specs/components/foo/interface/assets/app.js.md"
)


def build_first_corpus(repo_root, assets_line=ASSETS_OK):
    comp = build_corpus(repo_root, assets_line)
    write(comp / "interface" / "assets" / "b.js.md", "# Asset b.js\n")
    return comp


def test_missing_asset_interface_reported(tmp_path):
    repo_root = tmp_path / "repo"
    build_first_corpus(repo_root)
    assert_lint_clean(repo_root)

    report = spec_reviewer.check(["AC-FOO-001"], repo_root)
    findings = field(report, "findings")
    assert len(findings) == 1
    f = findings[0]
    assert field(f, "criterion_id") == "comp-foo"
    assert field(f, "kind") == "asset_interface_missing"
    assert field(f, "token") == "static/app.js"
    assert field(f, "message") == EXPECTED_MESSAGE


def test_all_asset_interfaces_present_no_findings(tmp_path):
    repo_root = tmp_path / "repo"
    comp = build_first_corpus(repo_root)
    write(comp / "interface" / "assets" / "app.js.md", "# Asset app.js\n")

    report = spec_reviewer.check(["comp-foo"], repo_root)
    assert list(field(report, "findings")) == []


def test_asset_finding_present_on_lint_failure_return(tmp_path):
    repo_root = tmp_path / "repo"
    build_first_corpus(repo_root, ASSETS_BROKEN)

    report = spec_reviewer.check(["comp-foo"], repo_root)
    lint_findings = field(report, "lint_findings")
    assert any(field(lf, "severity") == "fail" for lf in lint_findings)
    assert list(field(report, "criteria_checked")) == []
    findings = field(report, "findings")
    assert len(findings) == 1
    assert field(findings[0], "kind") == "asset_interface_missing"
    assert field(findings[0], "token") == "static/app.js"


def test_no_assets_line_no_findings(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, None)
    assert_lint_clean(repo_root)

    report = spec_reviewer.check(["comp-foo"], repo_root)
    assert list(field(report, "findings")) == []