# hotdocs-criterion: sha256:76467ef39113220410ec91334d8b74a79337d16d9271e2ebf1fa3d61c6ff3807
import json
import re
import shutil
from pathlib import Path

import verifier_orchestrator


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]


def copy_compiler(root):
    src = live_root() / "pipeline" / "criterion-compiler"
    dst = root / "pipeline" / "criterion-compiler"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def build_fixture(root, expected):
    comp = root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes things.\n",
    )
    write(
        root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# P-FOO\n"
        "\n"
        "Foo makes things.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** - `make_thing(n)` MUST return an object whose `value` is `n + 1`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_thing(n)\n"
        "```\n"
        "\n"
        "Returns an object with attribute `value`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a seed is 2\n"
        "When make_thing is invoked with [seed]\n"
        "Then value equals " + str(expected) + "\n"
        "```\n",
    )
    write(
        root / "specs" / "glossary.md",
        "# Glossary\n\nNothing.\n",
    )
    write(
        root / "gen" / "foo" / "foo.py",
        "import types\n"
        "\n"
        "\n"
        "def make_thing(n):\n"
        "    return types.SimpleNamespace(value=n + 1)\n",
    )
    copy_compiler(root)
    return root


def assert_usage(err):
    assert "hotdocs verify-component" in err
    assert re.search(r"hotdocs verify(?!-component)", err) is None


def test_passing_component_json_and_text(tmp_path, capsys, monkeypatch):
    root = build_fixture(tmp_path / "repo", 3)
    monkeypatch.chdir(root)

    code = verifier_orchestrator.main(
        ["comp-foo", "--repo-root=" + str(root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    doc = json.loads(out)
    assert doc["overall"] == "pass"

    code = verifier_orchestrator.main(
        ["comp-foo", "--repo-root", str(root), "--format", "text"]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines[0] == "comp-foo: pass"
    rest = lines[1:]
    assert rest, out
    for line in rest:
        assert line[:1].isspace(), line
    assert "AC-FOO-001: pass" in [line.strip() for line in rest]


def test_failing_component_returns_1(tmp_path, capsys, monkeypatch):
    root = build_fixture(tmp_path / "repo", 4)
    monkeypatch.chdir(root)
    code = verifier_orchestrator.main(["comp-foo", "--repo-root=" + str(root)])
    capsys.readouterr()
    assert code == 1


def test_usage_errors_return_2(tmp_path, capsys, monkeypatch):
    root = build_fixture(tmp_path / "repo", 3)
    monkeypatch.chdir(root)
    cases = [
        [],
        ["comp-foo", "--repo-root=" + str(root), "--format=bogus"],
        ["comp-foo", "--repo-root=" + str(root), "--hotdocs-smoke-unknown"],
        ["comp-foo", "--repo-root"],
        ["comp-nope", "--repo-root=" + str(root)],
    ]
    for argv in cases:
        code = verifier_orchestrator.main(argv)
        captured = capsys.readouterr()
        assert code == 2, (argv, captured.out, captured.err)
        assert_usage(captured.err)