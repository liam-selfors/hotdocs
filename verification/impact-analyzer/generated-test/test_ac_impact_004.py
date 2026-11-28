# hotdocs-criterion: sha256:ed1857541f16b92056a93cab4ce7615ea5173c80c057e64fd02ac6839d82ab99
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import impact_analyzer


VAR_ID = "VAR-CACHE-STORE-URL"
COMPONENT_ID = "comp-cache-manager"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=hotdocs-test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
        ]
        + list(args),
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_component(repo, slug, extra_frontmatter_lines=()):
    upper = slug.upper()
    title = "-".join(part.capitalize() for part in slug.split("-"))
    base = repo / "specs" / "components" / slug
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
    ]
    lines.extend(extra_frontmatter_lines)
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    for section in [
        "Purpose",
        "Scope",
        "Definitions",
        "Behavior",
        "Interfaces",
        "Acceptance criteria",
        "Open questions",
        "Change log",
    ]:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Fixture text for " + section.lower() + ".")
    write(base / "component.md", "\n".join(lines) + "\n")

    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        base / "acceptance" / (ac_id + ".md"),
        "# "
        + ac_id
        + "\n\nCovers: "
        + req_id
        + "\nKind: generated-test\n\n```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n",
    )
    write(
        base / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n\n```\nrun(x: int) -> int\n```\n",
    )


def var_text(description):
    return (
        "---\n"
        "id: " + VAR_ID + "\n"
        "title: Cache Store URL\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# " + VAR_ID + "\n"
        "\n"
        + description
        + "\n"
    )


def build_repo(repo):
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test component.\n",
    )
    write_component(repo, "cache-manager", ["uses_var: [" + VAR_ID + "]"])
    var_path = repo / "specs" / "vars" / (VAR_ID + ".md")
    write(var_path, var_text("The URL of the cache store."))

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Changed state: edit the var declaration in the working tree.
    write(var_path, var_text("The URL of the shared cache store service."))


def assert_lint_clean(repo_root):
    gen = next(
        p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec_linter = load_module(path, "spec_linter")
    report = spec_linter.lint(None, repo_root)
    assert report.hard_failures == 0, [
        (f.rule_id, f.file, f.message) for f in report.findings if f.severity == "fail"
    ]


def test_ac_impact_004_changed_var_includes_uses_var_component(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo)
    assert_lint_clean(repo)

    capsys.readouterr()
    code = impact_analyzer.main(
        ["--changed", VAR_ID, "--repo-root", str(repo), "--format=json"]
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err

    report = json.loads(captured.out)
    assert field(report, "precondition_error") is None

    impacted = field(report, "impacted")
    matches = [e for e in impacted if field(e, "component_id") == COMPONENT_ID]
    assert len(matches) == 1, impacted
    entry = matches[0]
    assert field(entry, "reason") == "transitive-var"
    assert field(entry, "via") == VAR_ID