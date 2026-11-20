# hotdocs-criterion: sha256:6857595a0d0ca4a1cf6df39828d4cd109de0ea9d7c34e8159ccdec38b96bfe93
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import impact_analyzer


VAR_ID = "VAR-CACHE-STORE-URL"
COMP_ID = "comp-cache-manager"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=hotdocs-test",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo, slug, extra_frontmatter_lines=()):
    upper = slug.upper()
    title = slug.title()
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
    write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        + "Covers: R-" + upper + "-001\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given 1\n"
        + "When it runs\n"
        + "Then it returns 1\n"
        + "```\n",
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
        + "id: " + VAR_ID + "\n"
        + "title: Cache store URL\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "---\n"
        + "\n"
        + "# " + VAR_ID + "\n"
        + "\n"
        + "- **name**: " + VAR_ID + "\n"
        + "- **required**: required\n"
        + "- **type**: url\n"
        + "- **description**: " + description + "\n"
        + "- **sensitivity**: non-secret\n"
        + "- **example**: `https://cache.example.com/`\n"
    )


def load_spec_linter():
    gen = next(
        p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen"
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


def build_repo(repo):
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test component.\n",
    )
    write(repo / "specs" / "vars" / (VAR_ID + ".md"), var_text("Where the cache store lives."))
    write_component(repo, "cache", ["uses_var: [" + VAR_ID + "]"])
    # Rename directory/id to the criterion's component id: comp-cache-manager
    # needs a one-word-free slug "cache-manager"; build it directly instead.
    import shutil
    shutil.rmtree(repo / "specs" / "components" / "cache")


def build_cache_manager(repo):
    slug = "cache-manager"
    upper = "CACHE-MANAGER"
    title = "Cache Manager"
    base = repo / "specs" / "components" / slug
    lines = [
        "---",
        "id: " + COMP_ID,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/cachemanager/",
        "uses_var: [" + VAR_ID + "]",
        "---",
        "",
        "# " + title,
    ]
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
    write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        + "Covers: R-" + upper + "-001\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given 1\n"
        + "When it runs\n"
        + "Then it returns 1\n"
        + "```\n",
    )
    write(
        base / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(
        base / "interface" / "library.md",
        "# Library\n\n```\nrun(x: int) -> int\n```\n",
    )


def make_fixture(tmp_path):
    repo = tmp_path
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test component.\n",
    )
    write(repo / "specs" / "vars" / (VAR_ID + ".md"), var_text("Where the cache store lives."))
    build_cache_manager(repo)

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # The changed state: the var declaration differs from commit A.
    write(
        repo / "specs" / "vars" / (VAR_ID + ".md"),
        var_text("The URL of the shared cache store service."),
    )

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0
    return repo


def find_entries(impacted, component_id):
    return [e for e in impacted if field(e, "component_id") == component_id]


def test_changed_var_includes_uses_var_component_library(tmp_path):
    repo = make_fixture(tmp_path)

    report = impact_analyzer.compute_blast_radius([VAR_ID], repo)

    assert field(report, "precondition_error") is None
    impacted = field(report, "impacted")
    entries = find_entries(impacted, COMP_ID)
    assert len(entries) == 1
    entry = entries[0]
    assert field(entry, "reason") == "transitive-var"
    assert field(entry, "via") == VAR_ID
    assert field(entry, "guarantee_ids") is None

    as_dict = report.to_dict()
    dict_entries = [e for e in as_dict["impacted"] if e["component_id"] == COMP_ID]
    assert len(dict_entries) == 1
    assert dict_entries[0]["reason"] == "transitive-var"
    assert dict_entries[0]["via"] == VAR_ID
    assert "guarantee_ids" not in dict_entries[0]
    assert as_dict["precondition_error"] is None


def test_changed_var_includes_uses_var_component_cli_json(tmp_path, capsys):
    repo = make_fixture(tmp_path)
    capsys.readouterr()

    code = impact_analyzer.main(
        ["--changed", VAR_ID, "--repo-root", str(repo), "--format=json"]
    )
    out = capsys.readouterr().out

    assert code == 0
    data = json.loads(out)
    assert data["precondition_error"] is None
    entries = [e for e in data["impacted"] if e["component_id"] == COMP_ID]
    assert len(entries) == 1
    assert entries[0]["reason"] == "transitive-var"
    assert entries[0]["via"] == VAR_ID


def test_changed_var_includes_uses_var_component_cli_text(tmp_path, capsys):
    repo = make_fixture(tmp_path)
    capsys.readouterr()

    code = impact_analyzer.main(["--changed", VAR_ID, "--repo-root=" + str(repo)])
    out = capsys.readouterr().out

    assert code == 0
    lines = out.splitlines()
    assert COMP_ID + "\ttransitive-var\tvia " + VAR_ID in lines