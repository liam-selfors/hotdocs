# hotdocs-criterion: sha256:f877eacd15e4897af288df0b83b77aa822090b1a9e707c6ff3bce3dd665ed4d7
import agentic_generator
import cache_manager
import capability_scenario_verifier
import component_gate_runner
import criterion_compiler
import generation_loop
import generator
import graph_query_engine
import hotdocs_cli
import hotdocs_init
import impact_analyzer
import kind_javascript
import kind_python
import llm_endpoint
import llm_tool_endpoint
import provenance_checker
import provenance_writer
import review_packet_builder
import spec_bundle_assembler
import surface_checker
import test_author
import test_probe
import verifier_orchestrator

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


HUMAN_NAME = "Human Developer"
HUMAN_EMAIL = "human@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@example.invalid"

SPEC_HASH = "sha256:" + "ab" * 32

GENERATED_FILES = {
    "foo.py": "def hello():\n    return 'hi'\n",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = r'''
import json
from pathlib import Path


def _log(call, **data):
    entry = {"call": call}
    entry.update(data)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def _f(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)
'''


GENERATOR_BODY = r'''
GATE_VERSION = "generator@3.2.0"
PROMPT_VERSION = "v12"


def _result(component_id, spec_bundle_hash, model, retry_feedback, files):
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": False,
        "files": dict(files),
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generate", component_id=bundle["component_id"], model=model,
         retry_feedback=retry_feedback)
    out = Path(repo_root) / "gen" / "foo"
    out.mkdir(parents=True, exist_ok=True)
    for rel, text in FILES.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return _result(bundle["component_id"], bundle["spec_bundle_hash"], model,
                   retry_feedback, FILES)


def commit_cache(result, repo_root=None):
    _log("commit_cache")
    return None


def check_write_allowed(bundle, repo_root=None):
    return None


def render_prompt_sections(bundle, retry_feedback=None):
    return [("Spec", "SPEC TEXT"), ("Component interface", "IFACE TEXT")]


def write_files(component_id, files, repo_root=None):
    _log("write_files", component_id=component_id)
    return None


def check_assets(component_id, files, repo_root=None):
    return (None, [])


def check_asset_environment(component_id, repo_root=None):
    return (None, [])
'''


SURFACE_BODY = r'''
GATE_VERSION = "surface-checker@1.2.0"


def check_surface(component_id, repo_root, code_dir=None):
    _log("check_surface", component_id=component_id)
    return {"ok": True, "findings": []}
'''


VERIFIER_BODY = r'''
GATE_VERSION = "verifier-orchestrator@3.5.0"
DEFAULT_TEST_TIMEOUT = 300.0


def verify(component_id, repo_root, judge=None, test_author=None):
    present = (Path(repo_root) / "gen" / "foo" / "foo.py").is_file()
    _log("verify", component_id=component_id, present=present)
    result = "pass" if present else "fail"
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": result},
        ],
        "requirement_results": {"R-FOO-001": result},
        "interface_drift": False,
        "mutation_score": 1.0,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "cd" * 32,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "overall": result,
    }
'''


TEST_AUTHOR_BODY = r'''
GATE_VERSION = "generated_test@3.0.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log("author_test")
    return {
        "component_id": _f(bundle, "component_id"),
        "criterion_id": _f(bundle, "criterion_id"),
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_x.py", "content": "def test_x():\n    pass\n"},
        "model_call_error": None,
        "repair_attempts": 0,
        "probe_findings": [],
    }
'''


LLM_ENDPOINT_BODY = r'''
DEFAULT_TIMEOUT_SECONDS = 600


def complete(prompt, model, *, backend=None, **params):
    _log("complete")
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}


def load_config(config_path=None):
    return None
'''


PROVENANCE_CHECKER_BODY = r'''
class _Key:
    def __init__(self):
        self.spec_bundle_hash = SPEC_HASH
        self.gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@3.0.0",
            "verifier": "verifier-orchestrator@3.5.0",
            "license_scanner": "license_scanner@0.0.0",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.2.0+v12",
        }
        self.assets = [{"kind": "python", "path": ".",
                        "definition_sha256": None,
                        "adapter_sha256": "sha256:" + "cd" * 32,
                        "versions": {"python": "3.12.4"},
                        "lockfile_sha256": None}]


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id)
    return {"hit": False, "reason": "no manifest", "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    return {"hit": False, "sealed": False, "reason": "not_sealed",
            "verification_report": None, "license_scan": None, "secret_scan": None,
            "owners": None, "source_hash": None, "written_at": None}
'''


ASSEMBLER_BODY = r'''
def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return {
        "component_id": component_id,
        "spec_bundle_hash": SPEC_HASH,
        "spec": "Foo spec",
        "interface": "hello() -> str",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "hello() -> str",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
'''


TRACKER_BODY = r'''
def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    d = Path(repo_root) / ".hotdocs" / "attempts" / component_id
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.iterdir())) + 1
    (d / (str(n) + ".json")).write_text(json.dumps({"number": n}), encoding="utf-8")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {}


def last_requirement_failures(component_id, repo_root):
    return []
'''


LICENSE_BODY = r'''
def gate_version(repo_root):
    return "license_scanner@0.0.0"


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    return {"component_id": component_id, "gate_version": "license_scanner@0.0.0",
            "similarity_score": 0.0, "blocked": False, "matches": [], "evaluated": True}
'''


SECRET_BODY = r'''
def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan(repo_root):
    _log("secret_scan")
    return {"scope": "repo", "gate_version": "secret_scanner@0.0.0",
            "flagged": False, "matches": []}
'''


WRITER_BODY = r'''
def write_provenance(component_id, inputs, repo_root):
    vr = _f(inputs, "verification_report")
    gr = _f(inputs, "generation_result")
    manifest = {
        "spec_bundle_hash": _f(gr, "spec_bundle_hash"),
        "model_pin": _f(gr, "model"),
        "provenance_hit": _f(inputs, "provenance_hit"),
        "attempts": _f(inputs, "attempts"),
        "overall": _f(vr, "overall") if vr is not None else None,
    }
    _log("write_provenance", component_id=component_id, overall=manifest["overall"])
    for base in ("gen", "verification"):
        d = Path(repo_root) / base / "foo"
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(json.dumps(manifest, sort_keys=True) + "\n",
                                            encoding="utf-8")


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
'''


def write_fake(repo, log, slug, body, extra=""):
    module = slug.replace("-", "_")
    path = repo / "gen" / slug / (module + ".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG = " + repr(str(log)) + "\n"
        + "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
        + extra
        + COMMON
        + body
    )
    path.write_text(source, encoding="utf-8")


def write_corpus(repo, requirement_sentence):
    comp = repo / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "last_ratified_commit: 0000000\n"
        "depends_on: []\n"
        "---\n\n"
        "# Foo\n\n"
        "## Purpose\n\n"
        "Returns a fixed greeting.\n",
        encoding="utf-8",
    )
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n" + requirement_sentence + "\n", encoding="utf-8"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "When hello is called\n"
        "Then result equals \"hi\"\n"
        "```\n",
        encoding="utf-8",
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nhello() -> str\n```\n", encoding="utf-8"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")


def git(repo, home, args, name, email):
    env = dict(os.environ)
    env.update({
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    })
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"] + list(args),
        cwd=str(repo), env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, "git " + " ".join(args) + " failed: " + proc.stderr
    return proc.stdout


def read_log(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_cs_zero_edit_001_pipeline_merge_needs_no_human_edit_to_gen(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not available")

    repo = tmp_path / "repo"
    home = tmp_path / "home"
    logdir = tmp_path / "logs"
    repo.mkdir()
    home.mkdir()
    logdir.mkdir()
    log = logdir / "calls.jsonl"

    def human(*args):
        return git(repo, home, args, HUMAN_NAME, HUMAN_EMAIL)

    def pipeline(*args):
        return git(repo, home, args, PIPELINE_NAME, PIPELINE_EMAIL)

    # A ratified, non-sealed component spec with a complete criterion.
    human("init", "-q")
    human("symbolic-ref", "HEAD", "refs/heads/main")
    (repo / ".gitignore").write_text(".hotdocs/\n__pycache__/\n", encoding="utf-8")
    write_corpus(repo, "`hello()` MUST return a greeting.")
    human("add", "-A")
    human("commit", "-q", "-m", "Initial spec for comp-foo")

    # The pipeline's stand-in dependencies live outside gen/foo/ and are
    # infrastructure, committed before the spec merge.
    write_fake(repo, log, "generator", GENERATOR_BODY, "FILES = " + repr(GENERATED_FILES) + "\n")
    write_fake(repo, log, "surface-checker", SURFACE_BODY)
    write_fake(repo, log, "verifier-orchestrator", VERIFIER_BODY)
    write_fake(repo, log, "test-author", TEST_AUTHOR_BODY)
    write_fake(repo, log, "llm-endpoint", LLM_ENDPOINT_BODY)
    write_fake(repo, log, "provenance-checker", PROVENANCE_CHECKER_BODY)
    write_fake(repo, log, "spec-bundle-assembler", ASSEMBLER_BODY)
    write_fake(repo, log, "provenance-tracker", TRACKER_BODY)
    write_fake(repo, log, "license-scanner", LICENSE_BODY)
    write_fake(repo, log, "secret-scanner", SECRET_BODY)
    write_fake(repo, log, "provenance-writer", WRITER_BODY)
    human("add", "-A")
    human("commit", "-q", "-m", "Pipeline stand-ins")

    # The spec change, merged by a human.
    human("checkout", "-q", "-b", "spec-change")
    write_corpus(repo, "`hello()` MUST return the string `hi`.")
    human("add", "-A")
    human("commit", "-q", "-m", "Tighten R-FOO-001")
    human("checkout", "-q", "main")
    human("merge", "-q", "--no-ff", "-m", "Merge spec change", "spec-change")
    spec_merge = human("rev-parse", "HEAD").strip()

    assert human("ls-tree", "-r", "--name-only", spec_merge, "--", "gen/foo") == ""

    # The pipeline runs: generation -> verification -> scans -> provenance.
    def mock_backend(prompt, model, **params):
        return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo, "mock-model", 0, mock_backend, None,
        max_attempts=3, mode="single",
    )

    # Every gate passes.
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    assert field(field(result, "verification"), "overall") == "pass"
    assert field(field(result, "license_scan"), "blocked") is False
    assert field(field(result, "secret_scan"), "flagged") is False
    attempts = field(result, "attempts")
    assert len(attempts) >= 1
    assert field(attempts[-1], "outcome") == "passed"

    calls = [entry["call"] for entry in read_log(log)]
    assert "generate" in calls
    assert "verify" in calls
    assert "write_provenance" in calls
    assert calls.index("generate") < calls.index("verify") < calls.index("write_provenance")

    # gen/foo/ was produced by the pipeline alone.
    for rel, text in GENERATED_FILES.items():
        assert (repo / "gen" / "foo" / rel).read_text(encoding="utf-8") == text

    # The pipeline's own merge commit.
    pipeline("checkout", "-q", "-b", "pipeline/comp-foo")
    pipeline("add", "--", "gen/foo", "verification/foo")
    pipeline("commit", "-q", "-m", "Regenerate comp-foo")
    pipeline("checkout", "-q", "main")
    pipeline("merge", "-q", "--no-ff", "-m", "Pipeline merge comp-foo", "pipeline/comp-foo")
    pipeline_merge = pipeline("rev-parse", "HEAD").strip()

    # Nothing under gen/foo/ is left needing an edit.
    assert human("status", "--porcelain", "--", "gen/foo") == ""

    # The merged content is exactly what the pipeline generated.
    for rel, text in GENERATED_FILES.items():
        merged = human("show", pipeline_merge + ":gen/foo/" + rel)
        assert merged == text

    # Zero human-authored commits touch gen/foo/ between the two merges.
    authors = [
        line.strip()
        for line in human(
            "log", "--format=%ae", spec_merge + ".." + pipeline_merge, "--", "gen/foo"
        ).splitlines()
        if line.strip()
    ]
    assert authors, "the pipeline's commit touching gen/foo/ must exist"
    assert HUMAN_EMAIL not in authors
    assert all(author == PIPELINE_EMAIL for author in authors)