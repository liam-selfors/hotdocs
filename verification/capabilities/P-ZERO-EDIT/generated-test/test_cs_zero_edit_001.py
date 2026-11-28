# hotdocs-criterion: sha256:379a41b586e371f8b2b8cf4932a28f16f75799aa90c2320eb1bd487e55a71e27
"""CS-ZERO-EDIT-001: a ratified, non-sealed component spec change merged
through the pipeline yields a gen/<component>/ that passes every gate,
with zero human-authored commits to gen/<component>/ between the spec
merge and the pipeline's own merge commit."""

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import component_gate_runner


SLUG = "doubler"
COMPONENT_ID = "comp-" + SLUG
MODULE = "doubler"
MODEL = "anthropic:claude-sonnet-5"

HUMAN_NAME = "Spec Author"
HUMAN_EMAIL = "spec-author@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@example.invalid"

GENERATED_SOURCE = "def double(n):\n    return 2 * n\n"
GENERATED_TEST = (
    "import " + MODULE + "\n"
    "\n"
    "\n"
    "def test_double_of_21_is_42():\n"
    "    assert " + MODULE + ".double(21) == 42\n"
    "\n"
    "\n"
    "def test_double_of_negative():\n"
    "    assert " + MODULE + ".double(-3) == -6\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_spec_linter():
    gen = next(
        p for p in Path(component_gate_runner.__file__).resolve().parents if p.name == "gen"
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


def build_corpus(root):
    write(
        root / ".gitignore",
        "__pycache__/\n*.pyc\n",
    )
    write(
        root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Doubling** — multiplying an integer by two.\n",
    )
    write(
        root / "specs" / "product" / "P-DOUBLING.md",
        "---\n"
        "id: P-DOUBLING\n"
        "title: Doubling\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Doubling\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Callers can double an integer.\n"
        "\n"
        "## Capability scenario\n"
        "\n"
        "### CS-DOUBLING-001\n"
        "Covers: P-DOUBLING\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given an integer\n"
        "When it is doubled\n"
        "Then the result is twice the integer\n"
        "```\n",
    )
    comp = root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Doubler\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-DOUBLING]\n"
        "---\n"
        "\n"
        "# Doubler\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubles integers.\n",
    )
    write(
        comp / "requirements" / "R-DOUBLER-001.md",
        "# R-DOUBLER-001\n"
        "\n"
        "`double(n)` MUST return `2 * n` for every integer `n`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "One module file, `" + MODULE + ".py`.\n"
        "\n"
        "```\n"
        "double(n: int) -> int\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "Python standard library only.\n",
    )
    write(
        comp / "acceptance" / "AC-DOUBLER-001.md",
        "# AC-DOUBLER-001\n"
        "\n"
        "Covers: R-DOUBLER-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the integer 21\n"
        "When double is called with it\n"
        "Then the result is 42\n"
        "```\n",
    )


def git(root, *args, author=None):
    cmd = [
        "git",
        "-c", "commit.gpgsign=false",
        "-c", "init.defaultBranch=main",
        "-c", "user.name=" + (author[0] if author else HUMAN_NAME),
        "-c", "user.email=" + (author[1] if author else HUMAN_EMAIL),
    ] + list(args)
    env = {
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(root),
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    if author:
        env.update(
            {
                "GIT_AUTHOR_NAME": author[0],
                "GIT_AUTHOR_EMAIL": author[1],
                "GIT_COMMITTER_NAME": author[0],
                "GIT_COMMITTER_EMAIL": author[1],
            }
        )
    out = subprocess.run(
        cmd, cwd=str(root), env=env, capture_output=True, text=True, check=True
    )
    return out.stdout


def make_backend(calls):
    gen_marker = re.compile(r"-----BEGIN FILE ([0-9a-f]{32}): ")
    test_marker = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

    def backend(prompt, model, **params):
        m = gen_marker.search(prompt)
        if m:
            nonce = m.group(1)
            calls.append("generator")
            text = (
                "-----BEGIN FILE " + nonce + ": " + MODULE + ".py-----\n"
                + GENERATED_SOURCE
                + "-----END FILE " + nonce + "-----\n"
                + "-----END REPLY " + nonce + "-----\n"
            )
        else:
            m = test_marker.search(prompt)
            if m:
                nonce = m.group(1)
                calls.append("test-author")
                text = (
                    "-----BEGIN FILE " + nonce + "-----\n"
                    + GENERATED_TEST
                    + "-----END FILE " + nonce + "-----\n"
                )
            else:
                calls.append("judge")
                text = '{"result": "pass", "rationale": "double(n) returns 2 * n"}'
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_spec_change_merges_with_zero_human_edits_to_gen(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git is required to observe commit authorship")

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    # Given: a ratified, non-sealed, lint-clean component spec bundle with
    # complete acceptance criteria, merged by a human.
    build_corpus(repo_root)
    spec_linter = load_spec_linter()
    assert field(spec_linter.lint(None, repo_root), "hard_failures") == 0

    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "spec: add doubler", author=(HUMAN_NAME, HUMAN_EMAIL))
    spec_merge = git(repo_root, "rev-parse", "HEAD").strip()
    assert not (repo_root / "gen" / SLUG).exists()

    # When: the pipeline alone runs generation and verification.
    calls = []
    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, MODEL, seed=0, llm_backend=make_backend(calls)
    )

    assert "generator" in calls

    # No human touched gen/ between the spec merge and the pipeline's merge.
    log_before_merge = git(
        repo_root, "log", "--format=%H", spec_merge + "..HEAD", "--", "gen/" + SLUG
    ).strip()
    assert log_before_merge == ""
    assert git(repo_root, "rev-parse", "HEAD").strip() == spec_merge

    # The pipeline's own merge commit.
    git(repo_root, "add", "-A")
    git(
        repo_root, "commit", "-q", "-m", "pipeline: merge " + COMPONENT_ID,
        author=(PIPELINE_NAME, PIPELINE_EMAIL),
    )
    pipeline_merge = git(repo_root, "rev-parse", "HEAD").strip()

    # Then: every gate passes.
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
    license_scan = field(result, "license_scan")
    assert license_scan is not None
    assert field(license_scan, "blocked") is not True
    secret_scan = field(result, "secret_scan")
    assert secret_scan is not None
    assert field(secret_scan, "flagged") is not True
    assert field(spec_linter.lint(None, repo_root), "hard_failures") == 0

    # The merged gen/<component>/ is exactly what the pipeline produced.
    merged_source = git(repo_root, "show", pipeline_merge + ":gen/" + SLUG + "/" + MODULE + ".py")
    assert merged_source == GENERATED_SOURCE
    assert (repo_root / "gen" / SLUG / ".provenance.json").is_file()

    # And zero commits to gen/<component>/ between the spec merge and the
    # pipeline's merge commit were authored by a human.
    lines = [
        line
        for line in git(
            repo_root,
            "log",
            "--format=%an%x09%ae%x09%H",
            spec_merge + ".." + pipeline_merge,
            "--",
            "gen/" + SLUG,
        ).splitlines()
        if line.strip()
    ]
    assert lines, "the pipeline's merge commit must touch gen/" + SLUG
    for line in lines:
        name, email, sha = line.split("\t")
        assert (name, email) == (PIPELINE_NAME, PIPELINE_EMAIL), (
            "human-authored commit " + sha + " touched gen/" + SLUG
        )
    last = lines[0].split("\t")[2]
    assert last == pipeline_merge