# hotdocs-criterion: sha256:08c76b981f5921b00f87ad4ebba57486663607b25ca2c38742598ceef32e8ca0
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def bundle_field(value, name):
    if isinstance(value, dict):
        return value[name]
    if hasattr(value, name):
        return getattr(value, name)
    return value[name]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, assembler_log):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "foo.md",
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
    comp = repo_root / "specs" / "components" / "foo"
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
        comp / "requirements" / "R-FOO-003.md",
        "# R-FOO-003\n\n**R-FOO-003** — `bar_double(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-003b.md",
        "# AC-FOO-003b\n"
        "\n"
        "Covers: R-FOO-003\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When bar_double(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nbar_double(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # Component code: empty module, so the mutation run has no sites.
    write(repo_root / "gen" / "foo" / "foo.py", "")

    # Stand-in spec-bundle-assembler.
    assembler_src = (
        "LOG = " + repr(str(assembler_log)) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(criterion_id + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-FOO-003") + ",\n"
        "        'criterion_text': " + repr("Given x = 2\nWhen bar_double(x) is called\nThen it returns 4") + ",\n"
        "        'requirement_text': " + repr("**R-FOO-003** — `bar_double(x)` MUST return `2 * x`.") + ",\n"
        "        'interface': " + repr("# Library\n\n```\nbar_double(x: int) -> int\n```") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Foo** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )

    # Supply the real criterion compiler in repo_root (never rely on fallback).
    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]
    src_compiler = live / "pipeline" / "criterion-compiler"
    if src_compiler.is_dir():
        shutil.copytree(
            src_compiler,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__"),
        )


def make_test_author(author_log):
    def test_author_stand_in(bundle):
        criterion_id = bundle_field(bundle, "criterion_id")
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        return {
            "component_id": "comp-foo",
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_003b.py",
                "content": "def test_ok():\n    assert True\n",
            },
        }

    return test_author_stand_in


def test_criterion_id_with_letter_suffix_passed_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"

    build_fixture(repo_root, assembler_log)

    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, test_author=make_test_author(author_log)
    )

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert ids == ["AC-FOO-003b"]

    assert assembler_log.is_file(), "assemble_criterion was never called"
    assembled = [l for l in assembler_log.read_text(encoding="utf-8").splitlines() if l]
    assert assembled, "assemble_criterion was never called"
    assert all(a == "AC-FOO-003b" for a in assembled), assembled

    assert author_log.is_file(), "test_author was never called"
    authored = [l for l in author_log.read_text(encoding="utf-8").splitlines() if l]
    assert authored == ["AC-FOO-003b"]