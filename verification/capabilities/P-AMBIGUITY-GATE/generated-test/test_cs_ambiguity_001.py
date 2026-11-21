# hotdocs-criterion: sha256:902e17de8887c9e2b7798f68d306d9b6e72d05a2094d85ee83ab142f30b43826
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

import importlib.util
import sys
from pathlib import Path


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_real_spec_linter():
    gen = next(
        p for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    return load_module(path, "spec_linter")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_clean_corpus(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this fixture corpus.\n"
        "\n"
        "- **Widget** — a thing `foo` produces.\n",
    )
    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo produces a widget.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- `R-FOO-001` — `make_widget` returns a widget.\n"
        "- `R-FOO-002` — `make_widget` rejects an empty name.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "`make_widget(name)` MUST return a dict whose `name` is `name`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "`make_widget(name)` MUST raise `ValueError` when `name` is empty.\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_widget(name: str) -> dict\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a name \"w\"\n"
        "When make_widget is called with it\n"
        "Then the result's name is \"w\"\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an empty name\n"
        "When make_widget is called with it\n"
        "Then it raises ValueError\n"
        "```\n",
    )
    return comp


def _fail_findings(report):
    return [f for f in field(report, "findings") if field(f, "severity") == "fail"]


def test_cs_ambiguity_001_uncovered_requirement_blocks_merge(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp = _build_clean_corpus(repo_root)

    linter = _load_real_spec_linter()

    # The corpus is otherwise lint-clean.
    assert field(linter.lint(None, repo_root), "hard_failures") == 0

    # Introduce the defect: R-FOO-002 loses its only covering criterion.
    (comp / "acceptance" / "AC-FOO-002.md").unlink()

    report = linter.lint(None, repo_root)
    fails = _fail_findings(report)
    assert field(report, "hard_failures") >= 1
    assert fails, "expected a fail-severity finding for the uncovered requirement"
    assert any(
        "R-FOO-002" in str(field(f, "message")) or "R-FOO-002" in str(field(f, "file"))
        for f in fails
    )
    assert all(
        str(field(f, "file")).replace("\\", "/").startswith("specs/components/foo/")
        for f in fails
    )

    # The lint gate blocks the merge: non-zero exit for fail severity.
    code = linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    capsys.readouterr()
    assert code == 1

    # Submitted to the pipeline, the run halts at lint, before anything downstream.
    log_path = tmp_path / "downstream_calls.log"
    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        "from pathlib import Path\n"
        "\n"
        "LOG = Path(" + repr(str(log_path)) + ")\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    with LOG.open('a', encoding='utf-8') as fh:\n"
        "        fh.write('compute_blast_radius\\n')\n"
        "    return {'impacted': [{'component_id': 'comp-foo'}], 'precondition_error': None}\n",
    )
    _write(
        repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py",
        "from pathlib import Path\n"
        "\n"
        "LOG = Path(" + repr(str(log_path)) + ")\n"
        "\n"
        "class _Report:\n"
        "    def to_dict(self):\n"
        "        return {'targets': [], 'criteria_checked': [], 'findings': [], 'gaps': [],\n"
        "                'writable': {}, 'lint_findings': [], 'proposals': [], 'degraded': True}\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    with LOG.open('a', encoding='utf-8') as fh:\n"
        "        fh.write('check\\n')\n"
        "    return _Report()\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    with LOG.open('a', encoding='utf-8') as fh:\n"
        "        fh.write('glossary_judge\\n')\n"
        "    return lambda term, local_text, glossary_text: None\n",
    )

    assist_report = spec_completeness_assistant.assist(["comp-foo"], repo_root)
    assert field(assist_report, "halted") is True
    assist_fails = [
        f for f in field(assist_report, "lint_findings") if field(f, "severity") == "fail"
    ]
    assert assist_fails
    assert field(assist_report, "predicted_blast_radius") == []
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert "compute_blast_radius" not in calls
    assert "check" not in calls