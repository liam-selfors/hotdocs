# hotdocs-criterion: sha256:77f15251012fb6cc629fce728f42c220357e593be54c44dd256e45f09d0610b1
import importlib.util
import sys
from pathlib import Path

import spec_reviewer


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

COMPONENT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

REQUIREMENT = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"

CRITERION = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY = "# Library\n\n```\nfoo(x: int) -> int\n```\n"

CONSTRAINTS = "# Constraints\n\nNone.\n"


def build_corpus(repo_root):
    specs = repo_root / "specs"
    specs.mkdir(parents=True)
    (specs / "glossary.md").write_text(GLOSSARY, encoding="utf-8")
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT, encoding="utf-8")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(CRITERION, encoding="utf-8")
    (comp / "interface" / "library.md").write_text(LIBRARY, encoding="utf-8")
    (comp / "constraints.md").write_text(CONSTRAINTS, encoding="utf-8")


def write_fake_assembler(repo_root, log_path):
    base = repo_root / "gen" / "spec-bundle-assembler"
    base.mkdir(parents=True)
    source = (
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode=" + repr("cold") + "):\n"
        "    _log('assemble ' + str(component_id))\n"
        "    raise Exception(" + repr("unknown asset kind: css") + ")\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion ' + str(component_id) + ' ' + str(criterion_id))\n"
        "    raise Exception(" + repr("unknown asset kind: css") + ")\n"
    )
    (base / "spec_bundle_assembler.py").write_text(source, encoding="utf-8")


def lint_clean(repo_root):
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec_linter = load_module(path, "spec_linter")
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def test_ac_review_011_bundle_unavailable(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    log_path = tmp_path / "assembler_calls.log"
    write_fake_assembler(repo_root, log_path)

    lint_clean(repo_root)

    report = spec_reviewer.check(["comp-foo"], repo_root)

    log_lines = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert any(line.startswith("assemble_criterion ") and "AC-FOO-001" in line for line in log_lines)

    findings = list(field(report, "findings"))
    assert len(findings) == 1
    finding = findings[0]
    assert field(finding, "criterion_id") == "AC-FOO-001"
    assert field(finding, "kind") == "bundle_unavailable"
    assert field(finding, "token") == ""
    assert field(finding, "message") == (
        "AC-FOO-001: its bundle cannot be built: unknown asset kind: css"
    )

    writable = dict(field(report, "writable"))
    assert writable == {"AC-FOO-001": None}

    rc = spec_reviewer.main(["comp-foo", "--repo-root", str(repo_root)])
    assert rc == 1