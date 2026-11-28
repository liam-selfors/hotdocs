# hotdocs-criterion: sha256:89b78f6b1f6cf26844bf76aa397f660c3e055bc6b431ade40cbe44ea2bf14ab2
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import impact_analyzer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_spec_linter():
    gen = next(p for p in Path(impact_analyzer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def git(repo, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=hotdocs-test",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
        ]
        + list(args),
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


SECTIONS = [
    "Purpose",
    "Scope",
    "Definitions",
    "Behavior",
    "Interfaces",
    "Acceptance criteria",
    "Open questions",
    "Change log",
]


def library_text(signature):
    return "# Library\n\n```\n" + signature + "\n```\n"


def write_component(repo, slug, depends_on=None):
    upper = slug.upper()
    title = slug.title()
    root = repo / "specs" / "components" / slug
    lines = [
        "---",
        "id: comp-" + slug,
        "title: " + title,
        "status: draft",
        "owners: [test-team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
    ]
    if depends_on is not None:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    for section in SECTIONS:
        lines.append("")
        lines.append("## " + section)
        lines.append("")
        lines.append("Fixture text for " + section.lower() + ".")
    write(root / "component.md", "\n".join(lines) + "\n")

    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    write(
        root / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\nThe component MUST return its input unchanged.\n",
    )
    write(
        root / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\n"
        + "Covers: " + req_id + "\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\nGiven 1\nWhen it runs\nThen it returns 1\n```\n",
    )
    write(
        root / "constraints.md",
        "# Constraints\n\n- The component MUST finish within 1 second.\n",
    )
    write(root / "interface" / "library.md", library_text("run(x: int) -> int"))


def build_repo(repo, dangling):
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test component.\n",
    )
    write_component(repo, "foo")
    write_component(repo, "bar", depends_on=["comp-missing"] if dangling else None)

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "A")
    git(repo, "switch", "-q", "-c", "feature")

    # Changed state: comp-foo's interface signature changes in the working tree.
    write(
        repo / "specs" / "components" / "foo" / "interface" / "library.md",
        library_text("run(x: int, y: int) -> int"),
    )


def test_ac_impact_007_dangling_reference_elsewhere_fails_closed(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo, dangling=True)

    # The fixture really is not lint-clean, and only because of comp-bar's
    # dangling reference, which is unrelated to the changed id comp-foo.
    spec_linter = load_spec_linter()
    report = spec_linter.lint(None, repo)
    assert report.hard_failures > 0

    capsys.readouterr()
    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    captured = capsys.readouterr()

    assert code == 1, "stdout=" + repr(captured.out) + " stderr=" + repr(captured.err)
    data = json.loads(captured.out)
    assert field(data, "precondition_error") is not None
    assert field(data, "impacted") == []


def test_ac_impact_007_control_clean_corpus_is_not_a_precondition_error(tmp_path, capsys):
    repo = tmp_path
    build_repo(repo, dangling=False)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo).hard_failures == 0

    capsys.readouterr()
    code = impact_analyzer.main(
        ["--changed", "comp-foo", "--repo-root", str(repo), "--format=json"]
    )
    captured = capsys.readouterr()

    assert code == 0, "stdout=" + repr(captured.out) + " stderr=" + repr(captured.err)
    data = json.loads(captured.out)
    assert field(data, "precondition_error") is None