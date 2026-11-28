# hotdocs-criterion: sha256:4e34a5d5315094bb467f40d1c8dce5dab03b2af1ca25e8e3cf1eeafdc8cb665c
# CS-ZERO-EDIT-001 (Covers: P-ZERO-EDIT)
#
# Given a ratified, non-sealed component spec bundle with complete,
#   agent-checkable acceptance criteria
# When a spec change is merged through the pipeline (lint -> generation ->
#   verification -> review packet -> merge)
# Then the resulting gen/<component>/ passes every gate with zero commits to
#   gen/<component>/ authored by a human between the spec merge and the
#   pipeline's own merge commit
#
# The pipeline is driven through component-gate-runner's public
# `run_component_gates`, with the real generation-loop (the tool root's
# copy) between it and its leaf dependencies. Every leaf dependency is a
# flat-module fake under the fixture's own `gen/<slug>/`, so the only code
# that ever writes `gen/widget/` is the pipeline's generation step. The
# first generated candidate is wrong; the pipeline must repair it on its
# own (retry feedback), never a human.

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import component_gate_runner


HUMAN_NAME = "Spec Author"
HUMAN_EMAIL = "spec-author@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@hotdocs.invalid"


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


def git(repo, *args, name=HUMAN_NAME, email=HUMAN_EMAIL):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    cmd = [
        "git",
        "-c", "user.name=" + name,
        "-c", "user.email=" + email,
        "-c", "commit.gpgsign=false",
        "-c", "core.hooksPath=/dev/null",
        *args,
    ]
    proc = subprocess.run(cmd, cwd=str(repo), env=env, capture_output=True, text=True)
    assert proc.returncode == 0, "git " + " ".join(args) + " failed: " + proc.stderr
    return proc.stdout


# ---------------------------------------------------------------- fixtures

REQUIREMENT_V1 = (
    "# R-WIDGET-001\n"
    "\n"
    "`slugify(text)` MUST return `text` lowercased, with each run of\n"
    "whitespace replaced by a single hyphen.\n"
)

REQUIREMENT_V2 = (
    "# R-WIDGET-001\n"
    "\n"
    "`slugify(text)` MUST return `text` lowercased, with each run of\n"
    "whitespace replaced by a single hyphen. Leading and trailing\n"
    "whitespace is dropped.\n"
)


def write_corpus(repo):
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Slug** - a lowercase, hyphen-joined form of a piece of text.\n",
    )
    write(
        repo / "specs" / "product" / "P-SLUG.md",
        "---\n"
        "id: P-SLUG\n"
        "title: Slugs\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Slugs\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Readable URL slugs from titles.\n"
        "\n"
        "## Capability scenario\n"
        "\n"
        "### CS-SLUG-001\n"
        "Covers: P-SLUG\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a page title\n"
        "When its slug is made\n"
        "Then the slug is readable in a URL\n"
        "```\n",
    )
    comp = repo / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-SLUG]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Turns text into URL slugs.\n",
    )
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_V1)
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the text \"  Hello   World \"\n"
        "When slugify is called with it\n"
        "Then the result is \"hello-world\"\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "slugify(text: str) -> str\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNo third-party imports.\n")


LOG_HELPER = r'''
import json as _json


def _log(entry):
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(_json.dumps(entry, sort_keys=True, default=str) + "\n")
'''


FAKE_PROVENANCE_CHECKER = r'''
class _Key:
    def __init__(self):
        self.spec_bundle_hash = "sha256:" + "ab" * 32
        self.spec_bundle_parts = {"spec": "sha256:" + "cd" * 32,
                                  "dependency_code": "sha256:" + "ef" * 32}
        self.gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@3.0.0",
            "verifier": "verifier-orchestrator@4.0.0",
            "license_scanner": "license_scanner@4.0.3+fake",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.2.0+v12",
        }
        self.assets = [{"kind": "python", "path": ".", "definition_sha256": None,
                        "adapter_sha256": "sha256:" + "00" * 32,
                        "versions": {"python": "3.14.6"}, "lockfile_sha256": None}]
        self.drivers = []


def current_sealed_key(component_id, repo_root):
    _log({"call": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"call": "current_provenance_key", "component_id": component_id})
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):
    _log({"call": "check_provenance", "component_id": component_id})
    return {"hit": False, "reason": "no manifest", "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    return {"hit": False, "sealed": False, "reason": "not_sealed",
            "verification_report": None, "license_scan": None, "secret_scan": None,
            "owners": None, "source_hash": None, "written_at": None}
'''


FAKE_ASSEMBLER = r'''
def assemble(component_id, repo_root, mode="cold"):
    _log({"call": "assemble", "component_id": component_id, "mode": mode})
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "slugify spec",
        "interface": "slugify(text: str) -> str",
        "constraints": "No third-party imports.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
        "spec_bundle_parts": {"spec": "sha256:" + "cd" * 32,
                              "dependency_code": "sha256:" + "ef" * 32},
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-WIDGET-001",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
'''


FAKE_GENERATOR = r'''
from pathlib import Path

GATE_VERSION = "generator@3.2.0"
PROMPT_VERSION = "v12"

BUGGY = 'def slugify(text):\n    return text.lower()\n'
GOOD = 'def slugify(text):\n    return "-".join(text.lower().split())\n'


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = bundle["component_id"]
    slug = component_id[len("comp-"):]
    if retry_feedback and "R-WIDGET-001" in retry_feedback:
        files = {"widget.py": GOOD}
    else:
        files = {"widget.py": BUGGY}
    out = Path(repo_root) / "gen" / slug
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    _log({"call": "generate", "feedback": retry_feedback, "files": files})
    return {
        "component_id": component_id,
        "spec_bundle_hash": bundle["spec_bundle_hash"],
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": False,
        "files": files,
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def commit_cache(result, repo_root=None):
    _log({"call": "commit_cache"})


def check_write_allowed(bundle, repo_root=None):
    return None


def render_prompt_sections(bundle, retry_feedback=None):
    return [("Spec", bundle["spec"])]


def write_files(component_id, files, repo_root=None):
    out = Path(repo_root) / "gen" / component_id[len("comp-"):]
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")


def check_assets(component_id, files, repo_root=None):
    return (None, [])


def check_asset_environment(component_id, repo_root=None):
    return (None, [])
'''


FAKE_SURFACE_CHECKER = r'''
from pathlib import Path

GATE_VERSION = "surface-checker@1.2.0"


def check_surface(component_id, repo_root, code_dir=None):
    slug = component_id[len("comp-"):]
    base = Path(code_dir) if code_dir is not None else Path(repo_root) / "gen" / slug
    present = (base / (slug.replace("-", "_") + ".py")).is_file()
    findings = [] if present else [{"kind": "import_error", "message": "no module"}]
    _log({"call": "check_surface", "ok": present})
    return {"ok": present, "findings": findings}
'''


FAKE_VERIFIER = r'''
import importlib.util
import uuid
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@4.0.0"
DEFAULT_TEST_TIMEOUT = 300.0


def verify(component_id, repo_root, judge=None, test_author=None):
    slug = component_id[len("comp-"):]
    path = Path(repo_root) / "gen" / slug / (slug.replace("-", "_") + ".py")
    actual = None
    try:
        name = "fake_verified_" + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        actual = module.slugify("  Hello   World ")
        ok = actual == "hello-world"
    except Exception:
        ok = False
    criterion = {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001",
                 "kind": "generated-test", "result": "pass" if ok else "fail"}
    if not ok:
        criterion["failure_origin"] = "implementation"
        criterion["failure_detail"] = {"message": "slugify result differs",
                                       "expected": "hello-world", "actual": actual}
    overall = "pass" if ok else "fail"
    _log({"call": "verify", "overall": overall})
    return {
        "component_id": component_id,
        "criteria": [criterion],
        "requirement_results": {"R-WIDGET-001": overall},
        "interface_drift": False,
        "mutation_score": 1.0 if ok else None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }
'''


FAKE_TRACKER = r'''
import json
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    directory = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    directory.mkdir(parents=True, exist_ok=True)
    number = len(list(directory.iterdir())) + 1
    (directory / (str(number) + ".json")).write_text(
        json.dumps({"spec_bundle_hash": spec_bundle_hash}), encoding="utf-8")
    _log({"call": "write_attempt_record", "component_id": component_id})
'''


FAKE_LICENSE_SCANNER = r'''
def gate_version(repo_root):
    return "license_scanner@4.0.3+fake"


def scan(component_id, repo_root):
    _log({"call": "license_scan", "component_id": component_id})
    return {"component_id": component_id, "gate_version": "license_scanner@4.0.3+fake",
            "similarity_score": 0.0, "blocked": False, "matches": []}
'''


FAKE_SECRET_SCANNER = r'''
def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan(repo_root):
    _log({"call": "secret_scan"})
    return {"scope": "repo", "gate_version": "secret_scanner@0.0.0",
            "flagged": False, "matches": []}
'''


FAKE_PROVENANCE_WRITER = r'''
import json
from pathlib import Path


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_provenance(component_id, inputs, repo_root):
    slug = component_id[len("comp-"):]
    generation = _get(inputs, "generation_result")
    manifest = {
        "spec_bundle_hash": _get(generation, "spec_bundle_hash"),
        "spec_bundle_parts": _get(inputs, "spec_bundle_parts"),
        "model_pin": _get(generation, "model"),
        "attempts": _get(inputs, "attempts"),
        "attempt_history": _get(inputs, "attempt_history"),
        "gate_versions": _get(inputs, "gate_versions"),
        "provenance_hit": _get(inputs, "provenance_hit"),
        "verification_report": _get(inputs, "verification_report"),
        "license_scan": _get(inputs, "license_scan_result"),
        "secret_scan": _get(inputs, "secret_scan_result"),
    }
    text = json.dumps(manifest, sort_keys=True, default=str, indent=2) + "\n"
    for where in (Path(repo_root) / "gen" / slug, Path(repo_root) / "verification" / slug):
        where.mkdir(parents=True, exist_ok=True)
        (where / ".provenance.json").write_text(text, encoding="utf-8")
    _log({"call": "write_provenance", "component_id": component_id})


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"call": "write_sealed_provenance", "component_id": component_id})
'''


FAKES = {
    "provenance-checker": FAKE_PROVENANCE_CHECKER,
    "spec-bundle-assembler": FAKE_ASSEMBLER,
    "generator": FAKE_GENERATOR,
    "surface-checker": FAKE_SURFACE_CHECKER,
    "verifier-orchestrator": FAKE_VERIFIER,
    "provenance-tracker": FAKE_TRACKER,
    "license-scanner": FAKE_LICENSE_SCANNER,
    "secret-scanner": FAKE_SECRET_SCANNER,
    "provenance-writer": FAKE_PROVENANCE_WRITER,
}


def write_fakes(repo, log_path):
    for slug, body in FAKES.items():
        source = "LOG = " + repr(str(log_path)) + "\n" + LOG_HELPER + "\n" + body
        write(repo / "gen" / slug / (slug.replace("-", "_") + ".py"), source)


def read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_lint(repo_root):
    gen = next(p for p in Path(component_gate_runner.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec_linter = load_module(path, "spec_linter")
    report = spec_linter.lint(None, repo_root)
    return report


# ---------------------------------------------------------------- the test

def test_spec_change_merges_through_pipeline_with_zero_human_edits_to_gen(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to observe commit authorship")

    repo = tmp_path / "repo"
    repo.mkdir()
    log_path = tmp_path / "calls.log"

    # Given: a ratified, non-sealed component with complete criteria,
    # committed by a human, with no gen/widget/ yet.
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    write(repo / ".gitignore", ".hotdocs/\n__pycache__/\n")
    write_corpus(repo)
    write_fakes(repo, log_path)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "Fixture corpus")
    assert not (repo / "gen" / "widget").exists()

    # The human's spec change, merged.
    git(repo, "checkout", "-q", "-b", "spec-change")
    write(repo / "specs" / "components" / "widget" / "requirements" / "R-WIDGET-001.md", REQUIREMENT_V2)
    git(repo, "commit", "-q", "-am", "Tighten R-WIDGET-001")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "spec-change", "-m", "Merge spec change")
    spec_merge = git(repo, "rev-parse", "HEAD").strip()

    # When: the pipeline runs. Lint first.
    lint_report = run_lint(repo)
    assert field(lint_report, "hard_failures") == 0, repr(lint_report)

    git(repo, "checkout", "-q", "-b", "pipeline/comp-widget",
        name=PIPELINE_NAME, email=PIPELINE_EMAIL)

    # Generation + verification + scans, through the gate runner.
    result = component_gate_runner.run_component_gates(
        "comp-widget", repo, "claude-sonnet-5", seed=0, llm_backend=None,
    )

    # Then: every gate passes.
    assert field(result, "component_id") == "comp-widget"
    assert field(result, "blocked") is False, repr(result)
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    assert field(result, "provenance_hit") is False
    assert field(field(result, "verification"), "overall") == "pass"
    assert field(field(result, "license_scan"), "blocked") is False
    assert field(field(result, "secret_scan"), "flagged") is False
    surface = field(result, "surface_report")
    assert surface is not None and field(surface, "ok") is True

    # The pipeline repaired its own first candidate: more than one attempt,
    # the last one passing, with no human touch in between.
    attempts = field(result, "attempts")
    assert len(attempts) >= 2
    assert attempts[0]["outcome"] == "verification_failed"
    assert attempts[-1]["outcome"] == "passed"

    calls = read_log(log_path)
    generations = [c for c in calls if c["call"] == "generate"]
    assert len(generations) == len(attempts)
    assert generations[-1]["feedback"] == ["R-WIDGET-001"]
    assert any(c["call"] == "write_provenance" for c in calls)
    final_files = generations[-1]["files"]

    # What is on disk under gen/widget/ is exactly what generation produced.
    for name, content in final_files.items():
        assert (repo / "gen" / "widget" / name).read_text(encoding="utf-8") == content

    # Review packet stage: the pipeline itself assembles the change; here the
    # pipeline's commit carries everything it produced, unchanged.
    git(repo, "add", "-A", name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    git(repo, "commit", "-q", "-m", "Regenerate comp-widget",
        name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    git(repo, "checkout", "-q", "main", name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    git(repo, "merge", "-q", "--no-ff", "pipeline/comp-widget", "-m", "Pipeline merge: comp-widget",
        name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    pipeline_merge = git(repo, "rev-parse", "HEAD").strip()

    # The pipeline's merge is its own and follows the spec merge.
    assert git(repo, "log", "-1", "--format=%an", pipeline_merge).strip() == PIPELINE_NAME
    proc = subprocess.run(["git", "merge-base", "--is-ancestor", spec_merge, pipeline_merge],
                          cwd=str(repo), capture_output=True, text=True)
    assert proc.returncode == 0

    # Zero human-authored commits to gen/widget/ between the two merges,
    # and at least one (the pipeline's) that did touch it.
    authors = [
        line for line in git(repo, "log", "--format=%an|%ae",
                             spec_merge + ".." + pipeline_merge, "--", "gen/widget/").splitlines()
        if line.strip()
    ]
    assert authors, "no commit touched gen/widget/ between the merges"
    assert set(authors) == {PIPELINE_NAME + "|" + PIPELINE_EMAIL}, authors

    # The merged gen/widget/ is the generated output, byte for byte.
    tracked = set(git(repo, "ls-tree", "-r", "--name-only", pipeline_merge, "gen/widget/").split())
    assert "gen/widget/widget.py" in tracked
    assert "gen/widget/.provenance.json" in tracked
    for name, content in final_files.items():
        assert git(repo, "show", pipeline_merge + ":gen/widget/" + name) == content

    # Nothing left for a human to fix up afterwards.
    assert git(repo, "status", "--porcelain", "--", "gen/widget/").strip() == ""