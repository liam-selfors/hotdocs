# hotdocs-criterion: sha256:89b65bad9f3e45cf253595727e43f86d4c8dfa5f495c7ebdffcb553a3d076b6b
import json
import shutil
from pathlib import Path

import verifier_orchestrator


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]


def build_fixture(root, passing):
    root = Path(root)
    write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    write(
        root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo Capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Foo Capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubling numbers.\n",
    )
    comp = root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `double(x)` MUST return a `Doubled` whose `value` is `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a number is 2\n"
        "When double is invoked with {\"x\": number}\n"
        "Then value equals 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> Doubled\n```\n",
    )
    write(
        comp / "interface" / "data" / "Doubled.md",
        "# `Doubled`\n\n```json\n{\"value\": 4}\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    factor_expr = "2 * x" if passing else "2 * x + 1"
    write(
        root / "gen" / "foo" / "foo.py",
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class Doubled:\n"
        "    value: int\n"
        "\n"
        "\n"
        "def double(x):\n"
        "    return Doubled(value=" + factor_expr + ")\n",
    )

    criterion_text = (
        "Given a number is 2\n"
        "When double is invoked with {\"x\": number}\n"
        "Then value equals 4"
    )
    requirement_text = (
        "**R-FOO-001** \u2014 `double(x)` MUST return a `Doubled` whose `value` is `2 * x`."
    )
    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-001',\n"
        "        'criterion_text': " + repr(criterion_text) + ",\n"
        "        'requirement_text': " + repr(requirement_text) + ",\n"
        "        'interface': " + repr("double(x: int) -> Doubled") + ",\n"
        "        'glossary': " + repr("- **Foo** - a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n",
    )

    src = live_root() / "pipeline" / "criterion-compiler"
    shutil.copytree(
        src,
        root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return root


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_passing_component_json_and_text(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", passing=True)

    capsys.readouterr()
    code = verifier_orchestrator.main(
        ["comp-foo", "--repo-root=" + str(root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    report = json.loads(out)
    assert report["overall"] == "pass"

    code = verifier_orchestrator.main(
        ["comp-foo", "--repo-root", str(root), "--format", "text"]
    )
    out = capsys.readouterr().out
    assert code == 0
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines[0] == "comp-foo: pass"
    criterion_lines = lines[1:]
    assert criterion_lines
    for line in criterion_lines:
        assert line[:1].isspace()
    assert any(line.strip() == "AC-FOO-001: pass" for line in criterion_lines)


def test_failing_component_returns_1(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", passing=False)
    code = verifier_orchestrator.main(["comp-foo", "--repo-root=" + str(root)])
    assert code == 1


def test_usage_errors_return_2(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", passing=True)
    cases = [
        [],
        ["comp-foo", "--repo-root=" + str(root), "--format=bogus"],
        ["comp-foo", "--repo-root=" + str(root), "--bogus"],
        ["comp-foo", "--repo-root"],
        ["comp-nope", "--repo-root=" + str(root)],
    ]
    for argv in cases:
        capsys.readouterr()
        code = verifier_orchestrator.main(argv)
        err = capsys.readouterr().err
        assert code == 2, argv
        assert "hotdocs verify-component" in err, argv