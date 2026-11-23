# hotdocs-criterion: sha256:e9d71f3791790c357579b1ce6ee87f6c07677ef1da637fc878cbaafee318101b
import importlib.util
import sys
from pathlib import Path

import capability_scenario_verifier
import citation_checker
import corpus_graph_builder
import corpus_loader
import criterion_compiler
import docs_site_renderer
import llm_endpoint
import size_checker
import spec_completeness_assistant
import spec_linter
import spec_reviewer
import test_author
import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_real_spec_linter():
    gen = next(
        p
        for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    return load_module(path, "spec_linter")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this fixture corpus.\n"
        "\n"
        "- **Widget** — a thing that `foo` returns.\n",
    )
    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo returns widgets.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- `R-FOO-001` — `foo()` returns one widget.\n"
        "- `R-FOO-002` — `bar()` returns two widgets.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "`foo()` MUST return `1`.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "`bar()` MUST return `2`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo() -> int\n"
        "bar() -> int\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo is called\n"
        "Then it returns 1\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When bar is called\n"
        "Then it returns 2\n"
        "```\n",
    )
    return comp


def write_downstream_fakes(repo_root, log_path):
    impact_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('compute_blast_radius\\n')\n"
        "    return {'impacted': [{'component_id': 'comp-foo'}], 'precondition_error': None}\n"
    )
    write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_src)
    reviewer_src = (
        "class _Report:\n"
        "    def to_dict(self):\n"
        "        return {'targets': [], 'criteria_checked': [], 'findings': [], 'gaps': [],\n"
        "                'writable': {}, 'lint_findings': [], 'proposals': [], 'degraded': True}\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check\\n')\n"
        "    return _Report()\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('glossary_judge\\n')\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )
    write(repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py", reviewer_src)


def test_uncovered_requirement_fails_lint_and_blocks_before_generation(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp = build_corpus(repo_root)

    linter = load_real_spec_linter()

    # Precondition: the corpus is lint-clean with every requirement covered.
    baseline = linter.lint(None, repo_root)
    assert baseline.hard_failures == 0

    # The spec change: R-FOO-002 in the Behavior section loses its covering criterion.
    (comp / "acceptance" / "AC-FOO-002.md").unlink()

    report = linter.lint(None, repo_root)
    findings = field(report, "findings")
    fail_findings = [f for f in findings if field(f, "severity") == "fail"]
    assert fail_findings, "expected a fail-severity finding for the uncovered requirement"
    assert field(report, "hard_failures") >= 1
    assert any(
        str(field(f, "file")).replace("\\", "/").startswith("specs/components/foo/")
        for f in fail_findings
    )

    # The merge gate: spec-linter's CLI exits 1 on a fail-severity finding.
    exit_code = linter.main(["--repo-root=" + str(repo_root), "--format=json"])
    capsys.readouterr()
    assert exit_code == 1

    # Submitting the change to the pipeline halts at lint, before anything
    # downstream (blast radius, review, and so generation) runs.
    log_path = tmp_path / "downstream_calls.log"
    write_downstream_fakes(repo_root, log_path)

    completeness = spec_completeness_assistant.assist(["comp-foo"], repo_root)
    assert field(completeness, "halted") is True
    assert list(field(completeness, "predicted_blast_radius")) == []
    lint_findings = field(completeness, "lint_findings")
    assert any(field(f, "severity") == "fail" for f in lint_findings)

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == []