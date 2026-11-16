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

import pytest


MODEL = "claude-sonnet-5"
SLUG = "doubler"
COMPONENT_ID = "comp-doubler"
CAPABILITY_ID = "P-DOUBLE"
AC_ID = "AC-DOUBLER-001"
CS_ID = "CS-DOUBLE-001"

HUMAN = ("Human Developer", "human.developer@example.com")
PIPELINE = ("hotdocs-pipeline", "pipeline@hotdocs.invalid")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def opt_field(value, name, default=None):
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _tool_root():
    here = Path(component_gate_runner.__file__).resolve()
    gen = next(p for p in here.parents if p.name == "gen")
    return gen.parent


def _load_spec_linter():
    base = _tool_root() / "gen" / "spec-linter"
    path = base / "spec_linter.py"
    if not path.is_file():
        path = base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git_env(identity):
    env = dict(os.environ)
    name, email = identity
    env.update(
        {
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
    )
    return env


def _git(repo, *args, identity=HUMAN):
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        cwd=str(repo),
        env=_git_env(identity),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _commit_all(repo, message, identity):
    _git(repo, "add", "-A", identity=identity)
    _git(repo, "commit", "-m", message, identity=identity)
    return _git(repo, "rev-parse", "HEAD", identity=identity)


GLOSSARY = """# Glossary

- **Doubling** — multiplying a number by two.
"""

CAPABILITY = """---
id: P-DOUBLE
title: Doubling
status: draft
owners: [team-a]
---

# Doubling

## Purpose

A caller can double a number.

## Scope

In scope: integers.

## Capability scenario

### CS-DOUBLE-001
Covers: P-DOUBLE
Kind: generated-test

```gherkin
Given x = 2
When double(x) is called
Then it returns 4
```
"""


def _component_md(last_ratified_commit):
    return (
        "---\n"
        "id: comp-doubler\n"
        "title: Doubler\n"
        "status: ratified\n"
        f"last_ratified_commit: {last_ratified_commit}\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "realizes: [P-DOUBLE]\n"
        "---\n"
        "\n"
        "# Doubler\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubler doubles a number.\n"
    )


REQUIREMENT = """# R-DOUBLER-001

**R-DOUBLER-001** — `double(x)` MUST return `2 * x`.
"""

ACCEPTANCE = """# AC-DOUBLER-001

Covers: R-DOUBLER-001
Kind: generated-test

```gherkin
Given x = 2
When double(x) is called
Then it returns 4
```
"""

LIBRARY = """# Library

```
double(x: int) -> int
```
"""

CONSTRAINTS = """# Constraints

None.
"""

GENERATED_MODULE = '''def double(x):
    """Return twice x."""
    return 2 * x
'''


def _generated_test_source(repo_root: Path, test_name: str) -> str:
    module_path = repo_root / "gen" / SLUG / "doubler.py"
    return (
        "import importlib.util\n"
        "import sys\n"
        "\n"
        "\n"
        "def _load():\n"
        "    try:\n"
        "        import doubler\n"
        "        return doubler\n"
        "    except ImportError:\n"
        f"        path = {str(module_path)!r}\n"
        "        spec = importlib.util.spec_from_file_location('doubler', path)\n"
        "        module = importlib.util.module_from_spec(spec)\n"
        "        sys.modules['doubler'] = module\n"
        "        spec.loader.exec_module(module)\n"
        "        return module\n"
        "\n"
        "\n"
        f"def {test_name}():\n"
        "    doubler = _load()\n"
        "    assert doubler.double(2) == 4\n"
        "    assert doubler.double(3) == 6\n"
        "    assert doubler.double(0) == 0\n"
        "    assert doubler.double(-5) == -10\n"
    )


def _make_backend(repo_root: Path, log_path: Path):
    def _nonce(prompt):
        m = re.search(r"BEGIN FILE\s+([0-9a-f]{32})", prompt)
        if m:
            return m.group(1)
        tokens = re.findall(r"\b[0-9a-f]{32}\b", prompt)
        return tokens[0] if tokens else "0" * 32

    def backend(prompt, model, **params):
        nonce = _nonce(prompt)
        if CS_ID in prompt:
            role = "test-author"
            body = _generated_test_source(repo_root, "test_cs_double_001")
            text = f"-----BEGIN FILE {nonce}-----\n{body}-----END FILE {nonce}-----\n"
        elif AC_ID in prompt:
            role = "test-author"
            body = _generated_test_source(repo_root, "test_ac_doubler_001")
            text = f"-----BEGIN FILE {nonce}-----\n{body}-----END FILE {nonce}-----\n"
        else:
            role = "generator"
            text = (
                f"-----BEGIN FILE {nonce}: doubler.py-----\n"
                f"{GENERATED_MODULE}"
                f"-----END FILE {nonce}-----\n"
            )
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"role": role, "model": model}) + "\n")
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def _snapshot(dir_path: Path):
    return {
        str(p.relative_to(dir_path)): p.read_bytes()
        for p in sorted(dir_path.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")
    }


def test_cs_zero_edit_001_pipeline_merge_needs_no_human_edit_to_gen(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work_cwd = tmp_path / "cwd"
    work_cwd.mkdir()
    log_path = tmp_path / "backend_calls.log"

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(work_cwd)

    # --- Human-authored history: corpus scaffolding, then the spec merge. ---
    _git(repo_root, "init")
    _git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")
    _write(repo_root / ".gitignore", "__pycache__/\n*.pyc\n")
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "doubling.md", CAPABILITY)
    base_commit = _commit_all(repo_root, "Add doubling capability", HUMAN)

    comp_dir = repo_root / "specs" / "components" / SLUG
    _write(comp_dir / "component.md", _component_md(base_commit))
    _write(comp_dir / "requirements" / "R-DOUBLER-001.md", REQUIREMENT)
    _write(comp_dir / "acceptance" / "AC-DOUBLER-001.md", ACCEPTANCE)
    _write(comp_dir / "interface" / "library.md", LIBRARY)
    _write(comp_dir / "constraints.md", CONSTRAINTS)
    spec_merge = _commit_all(repo_root, "Merge comp-doubler spec (ratified)", HUMAN)

    gen_dir = repo_root / "gen" / SLUG
    assert not gen_dir.exists()

    # --- Pipeline: lint. ---
    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0

    backend = _make_backend(repo_root, log_path)

    # --- Pipeline: generation + verification + scans + provenance. ---
    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, MODEL, 0, llm_backend=backend
    )
    assert field(result, "model_call_error") is None
    assert field(result, "blocked") is False, field(result, "block_reason")
    assert field(result, "block_reason") is None
    verification = field(result, "verification")
    assert field(verification, "overall") == "pass"
    assert field(field(result, "license_scan"), "blocked") is False
    assert field(field(result, "secret_scan"), "flagged") is False

    assert (gen_dir / "doubler.py").is_file()
    roles = [json.loads(line)["role"] for line in log_path.read_text().splitlines() if line.strip()]
    assert "generator" in roles

    # --- Pipeline: capability-scenario gate for the realized capability. ---
    cap_result = capability_scenario_verifier.run_capability_gates(
        CAPABILITY_ID, repo_root, MODEL, 0, backend
    )
    cap_report = field(cap_result, "capability_scenario_report")
    assert field(field(cap_report, CAPABILITY_ID), "overall") == "pass"

    generated_snapshot = _snapshot(gen_dir)
    assert "doubler.py" in generated_snapshot

    # --- Pipeline: commit its own output on a pipeline branch. ---
    branch = "pipeline/comp-doubler"
    _git(repo_root, "checkout", "-b", branch, identity=PIPELINE)
    _commit_all(repo_root, "pipeline: regenerate comp-doubler", PIPELINE)

    # --- Pipeline: review packet. ---
    packet = review_packet_builder.build_review_packet([COMPONENT_ID], repo_root)
    vr = field(packet, "verification_results")
    assert field(field(vr, COMPONENT_ID), "overall") == "pass"
    flags = field(packet, "compliance_flags")
    assert list(field(flags, "license_scan")) == []
    assert list(field(flags, "secret_scan")) == []

    # --- Pipeline: merge. ---
    _git(repo_root, "checkout", "main", identity=PIPELINE)
    _git(
        repo_root, "merge", "--no-ff", branch, "-m", "pipeline: merge comp-doubler",
        identity=PIPELINE,
    )
    pipeline_merge = _git(repo_root, "rev-parse", "HEAD", identity=PIPELINE)
    assert _git(repo_root, "log", "-1", "--format=%an%x09%ae", pipeline_merge) == "\t".join(PIPELINE)

    # --- Then: zero human-authored commits to gen/<component>/ in the window. ---
    assert _git(repo_root, "log", "--format=%H", spec_merge, "--", f"gen/{SLUG}") == ""
    window = _git(
        repo_root, "log", "--full-history", "--format=%H%x09%an%x09%ae",
        f"{spec_merge}..{pipeline_merge}", "--", f"gen/{SLUG}",
    )
    entries = [line.split("\t") for line in window.splitlines() if line.strip()]
    assert entries, "the pipeline itself must have committed gen/doubler/"
    for sha, name, email in entries:
        assert (name, email) == PIPELINE, f"commit {sha} to gen/{SLUG} authored by {name} <{email}>"
        assert (name, email) != HUMAN

    # The merged gen/<component>/ is byte-for-byte what the pipeline produced.
    for rel, content in generated_snapshot.items():
        merged = subprocess.run(
            ["git", "show", f"{pipeline_merge}:gen/{SLUG}/{rel}"],
            cwd=str(repo_root), capture_output=True, env=_git_env(PIPELINE),
        )
        assert merged.returncode == 0, rel
        assert merged.stdout == content, rel

    # --- Then: the merged gen/<component>/ passes every gate. ---
    key = provenance_checker.current_provenance_key(COMPONENT_ID, repo_root)
    check = provenance_checker.check_provenance(
        COMPONENT_ID, field(key, "spec_bundle_hash"), field(key, "gate_versions"), repo_root
    )
    assert field(check, "hit") is True
    assert field(field(check, "verification_report"), "overall") == "pass"
    assert field(field(check, "license_scan"), "blocked") is False
    assert field(field(check, "secret_scan"), "flagged") is False

    reverify = verifier_orchestrator.verify(COMPONENT_ID, repo_root)
    assert field(reverify, "overall") == "pass"

    cap_check = capability_scenario_verifier.check_capability_provenance(CAPABILITY_ID, repo_root)
    assert field(cap_check, "hit") is True
    assert field(field(field(cap_check, "capability_scenario_report"), CAPABILITY_ID), "overall") == "pass"

    assert spec_linter.lint(None, repo_root)
    post = spec_linter.lint(None, repo_root)
    post_hard = post["hard_failures"] if isinstance(post, dict) else post.hard_failures
    assert post_hard == 0