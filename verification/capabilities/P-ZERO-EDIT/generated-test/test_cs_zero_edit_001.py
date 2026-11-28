# hotdocs-criterion: sha256:6897a61ece9e1d8d8e39197930867c817ee024b7b952b71d102bd858d9c68356
"""CS-ZERO-EDIT-001: a ratified, non-sealed spec change goes through the
pipeline alone, and the resulting gen/<component>/ passes every gate with no
human-authored commit to gen/<component>/ between the spec merge and the
pipeline's own merge commit."""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import agentic_generator
import component_gate_runner


HUMAN_NAME = "Human Developer"
HUMAN_EMAIL = "human@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@hotdocs.invalid"

MODEL = "mock-model"

GENERATED_CODE = (
    '"""Widget: tells whether a number is negative."""\n'
    "\n"
    "\n"
    "def is_negative(n):\n"
    '    """Return True exactly when n is below zero."""\n'
    "    return n < 0\n"
)

COMMITTED_TEST = (
    "import widget\n"
    "\n"
    "\n"
    "def test_negative_number_is_negative():\n"
    "    assert widget.is_negative(-1) is True\n"
    "\n"
    "\n"
    "def test_zero_is_not_negative():\n"
    "    assert widget.is_negative(0) is False\n"
    "\n"
    "\n"
    "def test_positive_number_is_not_negative():\n"
    "    assert widget.is_negative(1) is False\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FENCE = "`" * 3


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — the fixture component under test.\n",
    )

    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget Capability\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [widget-team]\n"
        "---\n"
        "\n"
        "# Widget Capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Tell whether a number is negative.\n"
        "\n"
        "## Capability scenario\n"
        "\n"
        "### CS-WIDGET-001\n"
        "Covers: P-WIDGET\n"
        "Kind: generated-test\n"
        "\n"
        + FENCE + "gherkin\n"
        "Given the number -1\n"
        "When is_negative is called with it\n"
        "Then the result is True\n"
        + FENCE + "\n",
    )

    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [widget-team]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Tells whether a number is negative.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "`is_negative(n)` MUST return `True` exactly when the integer `n` is\n"
        "below zero, and `False` otherwise.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        + FENCE + "gherkin\n"
        "Given the integers -1, 0 and 1\n"
        "When is_negative is called with each\n"
        "Then it returns True for -1 and False for 0 and 1\n"
        + FENCE + "\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "One module file, `widget.py`.\n"
        "\n"
        + FENCE + "\n"
        "is_negative(n: int) -> bool\n"
        + FENCE + "\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n\nPure function: no I/O, no network access.\n",
    )

    # The criterion's test, committed with the spec change (outside gen/).
    write(
        repo_root / "verification" / "widget" / "generated-test" / "test_ac_widget_001.py",
        COMMITTED_TEST,
    )


def make_backend(log_path):
    gen_marker = re.compile(r"-----BEGIN FILE ([0-9a-f]{32}): ")
    test_marker = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

    def backend(prompt, model, **params):
        match = gen_marker.search(prompt)
        if match:
            nonce = match.group(1)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write("generator\n")
            text = (
                "-----BEGIN FILE " + nonce + ": widget.py-----\n"
                + GENERATED_CODE
                + "-----END FILE " + nonce + "-----\n"
                + "-----END REPLY " + nonce + "-----\n"
            )
        else:
            match = test_marker.search(prompt)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write("other\n")
            if match:
                nonce = match.group(1)
                text = (
                    "-----BEGIN FILE " + nonce + "-----\n"
                    + COMMITTED_TEST
                    + "-----END FILE " + nonce + "-----\n"
                )
            else:
                text = '{"result": "pass", "rationale": "ok"}'
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def git(repo_root, *args, author=None):
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    name, email = author or (HUMAN_NAME, HUMAN_EMAIL)
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    out = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout


def test_spec_change_merges_with_zero_human_edits_to_gen(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git is required to check the commit history")

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    # Precondition: the spec change is lint-clean.
    gen = next(p for p in Path(agentic_generator.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # The human merges the spec change.
    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "Merge spec change: comp-widget")
    spec_merge = git(repo_root, "rev-parse", "HEAD").strip()

    # The pipeline alone generates and verifies.
    log_path = tmp_path / "backend.log"
    backend = make_backend(log_path)
    result = component_gate_runner.run_component_gates(
        "comp-widget", repo_root, MODEL, 0, backend
    )

    assert field(result, "blocked") is False, result
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass", verification
    license_scan = field(result, "license_scan")
    assert field(license_scan, "blocked") is not True, license_scan
    secret_scan = field(result, "secret_scan")
    assert field(secret_scan, "flagged") is not True, secret_scan

    assert "generator" in log_path.read_text(encoding="utf-8").splitlines()

    # gen/widget/ is exactly what the pipeline produced: untouched by hand.
    produced = repo_root / "gen" / "widget" / "widget.py"
    assert produced.read_text(encoding="utf-8") == GENERATED_CODE
    assert (repo_root / "gen" / "widget" / ".provenance.json").is_file()

    # The pipeline makes its own merge commit.
    git(repo_root, "add", "-A")
    git(
        repo_root,
        "commit",
        "-q",
        "-m",
        "hotdocs pipeline: merge generated comp-widget",
        author=(PIPELINE_NAME, PIPELINE_EMAIL),
    )
    pipeline_merge = git(repo_root, "rev-parse", "HEAD").strip()
    assert pipeline_merge != spec_merge

    # Zero human-authored commits to gen/widget/ between the two merges.
    authors = git(
        repo_root,
        "log",
        "--format=%an <%ae>",
        spec_merge + ".." + pipeline_merge,
        "--",
        "gen/widget",
    ).splitlines()
    assert authors, "the pipeline's merge commit must be what lands gen/widget/"
    assert all(a == PIPELINE_NAME + " <" + PIPELINE_EMAIL + ">" for a in authors), authors
    assert not any(HUMAN_EMAIL in a for a in authors)

    # The merged gen/widget/, as committed, still passes every gate.
    log_path.write_text("", encoding="utf-8")
    again = component_gate_runner.run_component_gates(
        "comp-widget", repo_root, MODEL, 0, backend
    )
    assert field(again, "blocked") is False, again
    assert field(again, "provenance_hit") is True, again
    assert field(field(again, "verification"), "overall") == "pass"
    assert field(field(again, "license_scan"), "blocked") is not True
    assert field(field(again, "secret_scan"), "flagged") is not True
    assert "generator" not in log_path.read_text(encoding="utf-8").splitlines()
    assert produced.read_text(encoding="utf-8") == GENERATED_CODE