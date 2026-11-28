# hotdocs-criterion: sha256:ba064960ba2fb635c2ddd719d73429c87fa9190c0a69ff763c9fe252945255c1
import importlib.util
import sys
from pathlib import Path

import verifier_orchestrator


FENCE = "`" * 3


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def library_text(bare_line):
    return (
        "# Library\n"
        "\n"
        + FENCE + "\n"
        + bare_line + "\n"
        + FENCE + "\n"
        "\n"
        + FENCE + "python\n"
        "class Helper:\n"
        "    def __init__(self, name):\n"
        "        pass\n"
        "build(x)\n"
        + FENCE + "\n"
    )


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-001',\n"
        "        'criterion_text': 'Given the interface\\nWhen it is read\\nThen it is clear',\n"
        "        'requirement_text': 'R-FOO-001: run MUST return its first argument.',\n"
        "        'interface': 'run(a, b)',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo runs things.\n",
    )
    write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "---\n"
        "\n"
        "# P-FOO\n"
        "\n"
        "Foo can run things.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `run` MUST return its first argument.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: llm-judge\n"
        "\n"
        + FENCE + "gherkin\n"
        "Given the interface\n"
        "When it is read\n"
        "Then it is clear\n"
        + FENCE + "\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        library_text("run(a, b)"),
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\nNothing.\n")
    write(repo_root / "gen" / "foo" / "foo.py", "def run(a, b):\n    return a\n")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )


def judge(bundle):
    return {"result": "pass", "rationale": "clear"}


def test_interface_drift_bare_block_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-foo", repo_root, judge=judge)
    assert field(report, "interface_drift") is False

    write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        library_text("run(a, b, c)"),
    )

    report2 = verifier_orchestrator.verify("comp-foo", repo_root, judge=judge)
    assert field(report2, "interface_drift") is True
    assert field(report2, "overall") == "fail"