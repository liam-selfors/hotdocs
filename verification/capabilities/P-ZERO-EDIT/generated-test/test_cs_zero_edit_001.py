import cache_manager
import capability_scenario_verifier
import component_gate_runner
import criterion_compiler
import generator
import graph_query_engine
import hotdocs_cli
import hotdocs_init
import impact_analyzer
import llm_endpoint
import provenance_checker
import provenance_writer
import review_packet_builder
import spec_bundle_assembler
import test_author
import verifier_orchestrator

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CAPABILITY_ID = "P-WIDGET"
MODEL = "claude-sonnet-5"

HUMAN = ("Spec Author", "spec-author@example.invalid")
PIPELINE = ("hotdocs-pipeline", "pipeline@hotdocs.invalid")

GEN_SOURCE = (
    "def double(x):\n"
    "    \"\"\"Return twice x.\"\"\"\n"
    "    return 2 * x\n"
)

TEST_SOURCE = (
    "import importlib.util\n"
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def _load_widget():\n"
    "    here = Path(__file__).resolve()\n"
    "    for parent in here.parents:\n"
    "        candidate = parent / \"gen\" / \"widget\" / \"widget.py\"\n"
    "        if candidate.is_file():\n"
    "            spec = importlib.util.spec_from_file_location(\"widget\", candidate)\n"
    "            module = importlib.util.module_from_spec(spec)\n"
    "            sys.modules[\"widget\"] = module\n"
    "            spec.loader.exec_module(module)\n"
    "            return module\n"
    "    import widget\n"
    "    return widget\n"
    "\n"
    "\n"
    "def test_double_returns_twice_the_input():\n"
    "    widget = _load_widget()\n"
    "    assert widget.double(2) == 4\n"
    "    assert widget.double(3) == 6\n"
    "    assert widget.double(0) == 0\n"
    "    assert widget.double(-5) == -10\n"
)

GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"


def _component_md(status, last_ratified_commit=None):
    lines = [
        "---",
        "id: comp-widget",
        "title: Widget",
        "status: " + status,
    ]
    if last_ratified_commit is not None:
        lines.append("last_ratified_commit: " + last_ratified_commit)
    lines += [
        "owners: [team-a]",
        "sealed: false",
        "depends_on: []",
        "realizes: [P-WIDGET]",
        "---",
        "",
        "# Widget",
        "",
        "## Purpose",
        "",
        "Widget doubles a number.",
        "",
    ]
    return "\n".join(lines)


PRODUCT_MD = (
    "---\n"
    "id: P-WIDGET\n"
    "title: Widget Doubling\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Widget Doubling\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A caller can double a number.\n"
    "\n"
    "## Scope\n"
    "\n"
    "In scope: doubling integers.\n"
    "\n"
    "## Capability scenario\n"
    "\n"
    "### CS-WIDGET-001\n"
    "Covers: P-WIDGET\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a number 2\n"
    "When the widget doubles it\n"
    "Then the result is 4\n"
    "```\n"
)

REQUIREMENT_MD = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** — `double(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE_MD = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When double(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\ndouble(x: int) -> int\n```\n"
CONSTRAINTS_MD = "# Constraints\n\nNone.\n"
GITIGNORE = ".hotdocs/\n__pycache__/\n.pytest_cache/\n*.pyc\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo, identity, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_AUTHOR_NAME=identity[0],
        GIT_AUTHOR_EMAIL=identity[1],
        GIT_COMMITTER_NAME=identity[0],
        GIT_COMMITTER_EMAIL=identity[1],
        GIT_CONFIG_NOSYSTEM="1",
    )
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, "git %s failed: %s" % (args, proc.stderr)
    return proc.stdout.strip()


def _load_spec_linter():
    gen = next(
        p for p in Path(component_gate_runner.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


_HEX32 = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])")


def _make_backend(log_path):
    def backend(prompt, model, **params):
        nonces = list(dict.fromkeys(_HEX32.findall(prompt)))
        gen_nonces = [n for n in nonces if re.search(r"BEGIN FILE " + n + r":", prompt)]
        ta_nonces = [n for n in nonces if re.search(r"BEGIN FILE " + n + r"-----", prompt)]
        blocks = []
        if gen_nonces:
            kind = "generator"
            for n in gen_nonces:
                blocks.append(
                    "-----BEGIN FILE %s: widget.py-----\n%s-----END FILE %s-----\n"
                    % (n, GEN_SOURCE, n)
                )
        elif ta_nonces:
            kind = "test-author"
            for n in ta_nonces:
                blocks.append(
                    "-----BEGIN FILE %s-----\n%s-----END FILE %s-----\n" % (n, TEST_SOURCE, n)
                )
        else:
            kind = "unknown"
            for n in nonces:
                blocks.append(
                    "-----BEGIN FILE %s: widget.py-----\n%s-----END FILE %s-----\n"
                    % (n, GEN_SOURCE, n)
                )
                blocks.append(
                    "-----BEGIN FILE %s-----\n%s-----END FILE %s-----\n" % (n, TEST_SOURCE, n)
                )
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": kind, "model": model, "nonces": len(nonces)}) + "\n")
        return {
            "text": "\n".join(blocks),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_cs_zero_edit_001_pipeline_merge_needs_no_human_edit(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    repo = tmp_path / "repo"
    repo.mkdir()
    log_path = tmp_path / "model_calls.jsonl"

    # --- Repository scaffold, authored by a human.
    _git(repo, HUMAN, "init", "-q")
    _git(repo, HUMAN, "symbolic-ref", "HEAD", "refs/heads/main")
    _write(repo / ".gitignore", GITIGNORE)
    _write(repo / "specs" / "glossary.md", GLOSSARY)
    _git(repo, HUMAN, "add", "-A")
    _git(repo, HUMAN, "commit", "-q", "-m", "Scaffold")

    # --- A human authors and ratifies the spec change on a branch.
    _git(repo, HUMAN, "checkout", "-q", "-b", "spec/widget")
    comp_dir = repo / "specs" / "components" / SLUG
    _write(comp_dir / "component.md", _component_md("draft"))
    _write(comp_dir / "requirements" / "R-WIDGET-001.md", REQUIREMENT_MD)
    _write(comp_dir / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE_MD)
    _write(comp_dir / "interface" / "library.md", LIBRARY_MD)
    _write(comp_dir / "constraints.md", CONSTRAINTS_MD)
    _write(repo / "specs" / "product" / "widget.md", PRODUCT_MD)
    _git(repo, HUMAN, "add", "-A")
    _git(repo, HUMAN, "commit", "-q", "-m", "Add widget spec")
    draft_sha = _git(repo, HUMAN, "rev-parse", "HEAD")
    _write(comp_dir / "component.md", _component_md("ratified", draft_sha))
    _git(repo, HUMAN, "add", "-A")
    _git(repo, HUMAN, "commit", "-q", "-m", "Ratify widget spec")

    # --- Spec merge (human).
    _git(repo, HUMAN, "checkout", "-q", "main")
    _git(repo, HUMAN, "merge", "-q", "--no-ff", "spec/widget", "-m", "Merge spec change")
    spec_merge = _git(repo, HUMAN, "rev-parse", "HEAD")
    assert _git(repo, HUMAN, "ls-tree", "-r", "--name-only", spec_merge, "--", "gen/") == ""

    # --- Pipeline stage 1: lint.
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    # --- Pipeline stages 2-3: generation and verification, no human involved.
    _git(repo, PIPELINE, "checkout", "-q", "-b", "pipeline/widget")
    backend = _make_backend(log_path)

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo, MODEL, seed=0, llm_backend=backend
    )
    assert field(result, "component_id") == COMPONENT_ID
    assert field(result, "model_call_error") is None
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
    assert not field(field(result, "license_scan"), "blocked")
    assert not field(field(result, "secret_scan"), "flagged")

    cap_result = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo, MODEL, 0, backend
    )
    cap_report = field(cap_result, "capability_scenario_report")
    assert cap_report is not None
    assert field(field(cap_report, CAPABILITY_ID), "overall") == "pass"

    assert log_path.is_file() and log_path.read_text(encoding="utf-8").strip()
    gen_file = repo / "gen" / SLUG / "widget.py"
    assert gen_file.is_file()
    assert gen_file.read_text(encoding="utf-8").strip() == GEN_SOURCE.strip()

    # --- Pipeline stage: commit its output and merge it, all as the pipeline.
    _git(repo, PIPELINE, "add", "-A")
    _git(repo, PIPELINE, "commit", "-q", "-m", "Regenerate gen/widget")
    _git(repo, PIPELINE, "checkout", "-q", "main")
    _git(repo, PIPELINE, "merge", "-q", "--no-ff", "pipeline/widget", "-m", "Pipeline merge")
    pipeline_merge = _git(repo, PIPELINE, "rev-parse", "HEAD")
    assert _git(repo, PIPELINE, "log", "-1", "--format=%ae", pipeline_merge) == PIPELINE[1]

    # --- Zero human commits to gen/<component>/ between the two merges.
    log = _git(
        repo, PIPELINE, "log", "--format=%H\t%an\t%ae",
        "%s..%s" % (spec_merge, pipeline_merge), "--", "gen/%s/" % SLUG,
    )
    entries = [line.split("\t") for line in log.splitlines() if line.strip()]
    assert entries, "the pipeline must itself have produced gen/widget/"
    for sha, name, email in entries:
        assert (name, email) == PIPELINE, "commit %s to gen/widget/ authored by %s <%s>" % (
            sha, name, email
        )
        assert email != HUMAN[1]

    committed = _git(repo, PIPELINE, "show", "%s:gen/%s/widget.py" % (pipeline_merge, SLUG))
    assert committed.strip() == GEN_SOURCE.strip()

    # --- The merged, unedited gen/<component>/ still passes every gate.
    report_after = spec_linter.lint(None, repo)
    hard_after = (
        report_after["hard_failures"]
        if isinstance(report_after, dict)
        else report_after.hard_failures
    )
    assert hard_after == 0

    key = provenance_checker.current_provenance_key(COMPONENT_ID, repo)
    check = provenance_checker.check_provenance(
        COMPONENT_ID, field(key, "spec_bundle_hash"), field(key, "gate_versions"), repo
    )
    assert field(check, "hit") is True
    assert field(field(check, "verification_report"), "overall") == "pass"
    assert not field(field(check, "license_scan"), "blocked")
    assert not field(field(check, "secret_scan"), "flagged")

    cap_check = capability_scenario_verifier.check_capability_provenance(CAPABILITY_ID, repo)
    assert field(cap_check, "hit") is True
    assert (
        field(field(field(cap_check, "capability_scenario_report"), CAPABILITY_ID), "overall")
        == "pass"
    )

    assert _git(repo, PIPELINE, "status", "--porcelain") == ""