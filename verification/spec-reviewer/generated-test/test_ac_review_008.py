# hotdocs-criterion: sha256:a0c29afe1b7caf1af51626e6e693796c4964e6b69e924912213ea5688984fd3b
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root, assets_line=None, asset_files=()):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")

    comp = specs / "components" / "foo"
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
        frontmatter + "\n# Foo\n\n## Purpose\n\nFoo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
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
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    for name in asset_files:
        write(
            comp / "interface" / "assets" / (name + ".md"),
            "# Asset " + name + "\n",
        )
    return repo_root


ASSETS_OK = "assets: [javascript:static/app.js, javascript:static/b.js]"
ASSETS_BROKEN = "assets: [javascript:static/app.js, broken]"


def test_missing_asset_interface_reported_for_criterion_target(tmp_path):
    repo_root = build_corpus(tmp_path / "repo", ASSETS_OK, ["b.js"])
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    report = spec_reviewer.check(["AC-FOO-001"], repo_root)
    findings = list(field(report, "findings"))
    assert len(findings) == 1
    f = findings[0]
    assert field(f, "criterion_id") == "comp-foo"
    assert field(f, "kind") == "asset_interface_missing"
    assert field(f, "token") == "static/app.js"
    assert field(f, "message") == (
        "`static/app.js` has no interface file "
        "specs/components/foo/interface/assets/app.js.md"
    )


def test_all_asset_interfaces_present_gives_no_findings(tmp_path):
    repo_root = build_corpus(tmp_path / "repo", ASSETS_OK, ["b.js", "app.js"])
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    report = spec_reviewer.check(["comp-foo"], repo_root)
    assert list(field(report, "findings")) == []


def test_asset_findings_reported_on_lint_failure_early_return(tmp_path):
    repo_root = build_corpus(tmp_path / "repo", ASSETS_BROKEN, ["b.js"])

    report = spec_reviewer.check(["comp-foo"], repo_root)

    lint_findings = list(field(report, "lint_findings"))
    assert any(field(lf, "severity") == "fail" for lf in lint_findings)
    assert list(field(report, "criteria_checked")) == []

    findings = list(field(report, "findings"))
    assert len(findings) == 1
    f = findings[0]
    assert field(f, "kind") == "asset_interface_missing"
    assert field(f, "token") == "static/app.js"


def test_no_assets_line_gives_no_findings(tmp_path):
    repo_root = build_corpus(tmp_path / "repo", None, [])
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    report = spec_reviewer.check(["comp-foo"], repo_root)
    assert list(field(report, "findings")) == []