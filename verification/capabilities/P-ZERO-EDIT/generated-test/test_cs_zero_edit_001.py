# hotdocs-criterion: sha256:3dc5eddf2efe855a6706c0c11a63b18971cd67e5f4cc3db04ecf91430563d045
"""CS-ZERO-EDIT-001: a ratified, non-sealed component's spec change goes through
the pipeline (generation -> verification -> scans -> provenance -> merge) and the
resulting gen/<component>/ passes every gate with zero human-authored commits to
gen/<component>/ between the spec merge and the pipeline's own merge commit.

The pipeline is driven through component_gate_runner.run_component_gates. Every
dependency it loads is a flat-module fake under <repo_root>/gen/<slug>/, matching
the documented signatures and return shapes. Each fake logs one line per call to
a file outside the repository.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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


HUMAN_NAME = "Spec Author"
HUMAN_EMAIL = "spec.author@example.com"
BOT_NAME = "hotdocs-pipeline"
BOT_EMAIL = "pipeline@hotdocs.invalid"

COMPONENT_ID = "comp-doubler"
SLUG = "doubler"
SPEC_HASH = "sha256:" + ("ab" * 32)

GENERATED = {"doubler.py": "def double(x):\n    return 2 * x\n"}

TEST_CONTENT = (
    "import doubler\n"
    "\n"
    "\n"
    "def test_double_returns_twice_its_input():\n"
    "    assert doubler.double(2) == 4\n"
    "    assert doubler.double(-3) == -6\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------

def git(repo, *args, name=HUMAN_NAME, email=HUMAN_EMAIL):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    cmd = ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + os.devnull]
    cmd += list(args)
    proc = subprocess.run(cmd, cwd=str(repo), env=env, capture_output=True, text=True)
    assert proc.returncode == 0, "git " + " ".join(args) + " failed: " + proc.stderr
    return proc.stdout


def head(repo):
    return git(repo, "rev-parse", "HEAD").strip()


# ---------------------------------------------------------------------------
# fixture files
# ---------------------------------------------------------------------------

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

COMPONENT_MD = (
    "---\n"
    "id: comp-doubler\n"
    "title: Doubler\n"
    "status: ratified\n"
    "last_ratified_commit: 0000000\n"
    "owners: [team-a]\n"
    "sealed: false\n"
    "depends_on: []\n"
    "realizes: [P-DOUBLING]\n"
    "---\n"
    "\n"
    "# Doubler\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Doubler doubles a number.\n"
)

REQUIREMENT_MD = (
    "# R-DOUBLER-001\n"
    "\n"
    "**R-DOUBLER-001** — `double(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE_MD = (
    "# AC-DOUBLER-001\n"
    "\n"
    "Covers: R-DOUBLER-001\n"
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

PRODUCT_MD = (
    "---\n"
    "id: P-DOUBLING\n"
    "title: Doubling\n"
    "status: ratified\n"
    "last_ratified_commit: 0000000\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Doubling\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A number can be doubled.\n"
    "\n"
    "## Capability scenario\n"
    "\n"
    "### CS-DOUBLING-001\n"
    "Covers: P-DOUBLING\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When double(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)


# ---------------------------------------------------------------------------
# fake dependency sources (plain raw strings, values embedded with repr())
# ---------------------------------------------------------------------------

LOG_HELPER = r'''
import json


def _log(name, **kw):
    entry = {"call": name}
    entry.update(kw)
    with open(LOG, "a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def _f(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)
'''

PROVENANCE_CHECKER_BODY = r'''
from types import SimpleNamespace

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
}


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return SimpleNamespace(spec_bundle_hash=SPEC_HASH, gate_versions=dict(GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id, spec_bundle_hash=spec_bundle_hash)
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {
        "hit": False, "sealed": False, "reason": "not_sealed",
        "verification_report": None, "license_scan": None, "secret_scan": None,
        "owners": None, "source_hash": None, "written_at": None,
    }
'''

ASSEMBLER_BODY = r'''
from pathlib import Path


def _read(path):
    return path.read_text().strip() if path.is_file() else ""


def assemble(component_id, repo_root=None, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    slug = component_id[len("comp-"):]
    base = Path(repo_root) / "specs" / "components" / slug
    spec_parts = [_read(base / "component.md")]
    for p in sorted((base / "requirements").glob("*.md")):
        spec_parts.append(_read(p))
    return {
        "component_id": component_id,
        "spec_bundle_hash": SPEC_HASH,
        "spec": "\n\n".join(x for x in spec_parts if x),
        "interface": _read(base / "interface" / "library.md"),
        "constraints": _read(base / "constraints.md"),
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": _read(Path(repo_root) / "specs" / "glossary.md"),
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-DOUBLER-001",
        "criterion_text": "Given x = 2\nWhen double(x) is called\nThen it returns 4",
        "requirement_text": "double(x) MUST return 2 * x.",
        "interface": "double(x: int) -> int",
        "glossary": "",
        "dependency_interfaces": {},
    }
'''

GENERATOR_BODY = r'''
from pathlib import Path

GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = _f(bundle, "component_id")
    slug = component_id[len("comp-"):]
    out = Path(repo_root) / "gen" / slug
    out.mkdir(parents=True, exist_ok=True)
    for rel, content in GENERATED.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    _log("generate", component_id=component_id, model=model, retry_feedback=retry_feedback)
    return {
        "component_id": component_id,
        "spec_bundle_hash": _f(bundle, "spec_bundle_hash"),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": False,
        "files": dict(GENERATED),
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

VERIFIER_BODY = r'''
import importlib.util
import sys
from pathlib import Path

GATE_VERSION = "verifier-orchestrator@2.2.0"


class VerificationReport:
    def __init__(self, component_id, criteria, requirement_results, overall):
        self.component_id = component_id
        self.criteria = criteria
        self.requirement_results = requirement_results
        self.interface_drift = False
        self.mutation_score = 1.0
        self.mutation_error = None
        self.overall = overall

    def to_dict(self):
        return {
            "component_id": self.component_id,
            "criteria": [dict(c) for c in self.criteria],
            "requirement_results": dict(self.requirement_results),
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "mutation_error": self.mutation_error,
            "overall": self.overall,
        }


def verify(component_id, repo_root, judge=None, test_author=None):
    root = Path(repo_root)
    slug = component_id[len("comp-"):]
    module_name = slug.replace("-", "_")
    bundle = {
        "component_id": component_id,
        "criterion_id": "AC-DOUBLER-001",
        "covers": "R-DOUBLER-001",
        "criterion_text": "Given x = 2\nWhen double(x) is called\nThen it returns 4",
        "requirement_text": "double(x) MUST return 2 * x.",
        "interface": "double(x: int) -> int",
        "glossary": "",
        "dependency_interfaces": {},
    }
    criterion = {"id": "AC-DOUBLER-001", "covers": "R-DOUBLER-001",
                 "kind": "generated-test", "result": "fail"}
    if test_author is None:
        criterion["failure_origin"] = "test"
        criterion["failure_detail"] = {"message": "no test_author", "expected": None, "actual": None}
    else:
        authored = test_author(bundle)
        if _f(authored, "model_call_error"):
            criterion["failure_origin"] = "test"
            criterion["failure_detail"] = {"message": "authoring failed", "expected": None, "actual": None}
        else:
            f = _f(authored, "file")
            path = root / _f(f, "path")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_f(f, "content"))
            gen_dir = str(root / "gen" / slug)
            sys.path.insert(0, gen_dir)
            sys.modules.pop(module_name, None)
            test_mod_name = "authored_test_ac_doubler_001"
            try:
                spec = importlib.util.spec_from_file_location(test_mod_name, path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[test_mod_name] = mod
                spec.loader.exec_module(mod)
                ran = 0
                for name in sorted(dir(mod)):
                    if name.startswith("test_") and callable(getattr(mod, name)):
                        getattr(mod, name)()
                        ran += 1
                criterion["result"] = "pass" if ran else "fail"
                if not ran:
                    criterion["failure_origin"] = "test"
                    criterion["failure_detail"] = {"message": "no tests", "expected": None, "actual": None}
            except Exception as exc:
                criterion["result"] = "fail"
                criterion["failure_origin"] = "implementation"
                criterion["failure_detail"] = {"message": str(exc), "expected": None, "actual": None}
            finally:
                if gen_dir in sys.path:
                    sys.path.remove(gen_dir)
                sys.modules.pop(module_name, None)
                sys.modules.pop(test_mod_name, None)
            criterion["test_authoring"] = {
                "model": _f(authored, "model"), "seed": _f(authored, "seed"),
                "prompt_version": _f(authored, "prompt_version"), "cache_hit": _f(authored, "cache_hit"),
            }
    overall = "pass" if criterion["result"] == "pass" else "fail"
    _log("verify", component_id=component_id, overall=overall)
    return VerificationReport(component_id, [criterion], {"R-DOUBLER-001": criterion["result"]}, overall)
'''

LICENSE_SCANNER_BODY = r'''
VERSION = "license_scanner@4.0.3+9f2c41ab07de"


def gate_version(repo_root=None):
    return VERSION


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    return {
        "component_id": component_id,
        "gate_version": VERSION,
        "similarity_score": 0.0,
        "blocked": False,
        "matches": [],
        "evaluated": True,
    }
'''

SECRET_SCANNER_BODY = r'''
VERSION = "secret_scanner@0.0.0"


def gate_version(repo_root=None):
    return VERSION


def scan(repo_root):
    _log("secret_scan")
    return {"scope": "repo", "gate_version": VERSION, "flagged": False, "matches": []}
'''

PROVENANCE_TRACKER_BODY = r'''
from pathlib import Path


def _plain(value):
    if value is None or isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(vars(value))


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):]
    d = Path(repo_root) / ".hotdocs" / "attempts" / slug
    d.mkdir(parents=True, exist_ok=True)
    n = len(list(d.iterdir())) + 1
    record = {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "generation_result": _plain(generation_result),
        "verification_report": _plain(verification_report),
    }
    (d / ("attempt-" + str(n) + ".json")).write_text(json.dumps(record, default=str))
    _log("write_attempt_record", component_id=component_id, spec_bundle_hash=spec_bundle_hash)


def last_requirement_failures(component_id, repo_root):
    return []
'''

PROVENANCE_WRITER_BODY = r'''
from pathlib import Path


def _plain(value):
    if value is None or isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(vars(value))


def write_provenance(component_id, inputs, repo_root):
    slug = component_id[len("comp-"):]
    gen_result = _plain(_f(inputs, "generation_result"))
    report = _plain(_f(inputs, "verification_report"))
    license_scan = _plain(_f(inputs, "license_scan_result"))
    secret_scan = _plain(_f(inputs, "secret_scan_result"))
    manifest = {
        "spec_bundle_hash": gen_result["spec_bundle_hash"] if gen_result else None,
        "model_pin": gen_result["model"] if gen_result else None,
        "prompt_version": gen_result["prompt_version"] if gen_result else None,
        "retry_feedback": gen_result["retry_feedback"] if gen_result else None,
        "pipeline_version": "v1",
        "gate_versions": _f(inputs, "gate_versions"),
        "provenance_hit": _f(inputs, "provenance_hit"),
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-1",
        "verification_report": report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }
    text = json.dumps(manifest, default=str, indent=2, sort_keys=True) + "\n"
    for base in ("gen", "verification"):
        d = Path(repo_root) / base / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(text)
    _log(
        "write_provenance",
        component_id=component_id,
        overall=report["overall"] if report else None,
        license_blocked=license_scan["blocked"],
        secret_flagged=secret_scan["flagged"],
        provenance_hit=_f(inputs, "provenance_hit"),
        attempts=_f(inputs, "attempts"),
    )


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
'''

TEST_AUTHOR_BODY = r'''
GATE_VERSION = "generated_test@1.1.0"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    component_id = _f(bundle, "component_id")
    criterion_id = _f(bundle, "criterion_id")
    slug = component_id[len("comp-"):]
    path = ("verification/" + slug + "/generated-test/test_"
            + criterion_id.lower().replace("-", "_") + ".py")
    _log("author_test", component_id=component_id, criterion_id=criterion_id, model=model, seed=seed)
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": path, "content": TEST_CONTENT},
        "model_call_error": None,
    }
'''

LLM_ENDPOINT_BODY = r'''
class ModelResolutionError(ValueError):
    pass


def complete(prompt, model, *, backend=None, **params):
    _log("complete", model=model)
    if backend is not None:
        return backend(prompt, model, **params)
    return {"text": "ok", "model": model, "backend": "fake", "model_call_error": None}


def load_config(config_path=None):
    return None
'''


def write_fakes(repo, log):
    header = (
        "LOG = " + repr(str(log)) + "\n"
        + "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
        + "GENERATED = " + repr(GENERATED) + "\n"
        + "TEST_CONTENT = " + repr(TEST_CONTENT) + "\n"
        + LOG_HELPER
    )
    fakes = {
        "provenance-checker": PROVENANCE_CHECKER_BODY,
        "spec-bundle-assembler": ASSEMBLER_BODY,
        "generator": GENERATOR_BODY,
        "verifier-orchestrator": VERIFIER_BODY,
        "license-scanner": LICENSE_SCANNER_BODY,
        "secret-scanner": SECRET_SCANNER_BODY,
        "provenance-tracker": PROVENANCE_TRACKER_BODY,
        "provenance-writer": PROVENANCE_WRITER_BODY,
        "test-author": TEST_AUTHOR_BODY,
        "llm-endpoint": LLM_ENDPOINT_BODY,
    }
    for slug, body in fakes.items():
        module_name = slug.replace("-", "_")
        write(repo / "gen" / slug / (module_name + ".py"), header + body)


def mock_backend(prompt, model, **params):
    return {"text": "ok", "model": model, "backend": "mock", "model_call_error": None}


def read_log(log):
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_spec_change_merges_through_pipeline_with_zero_human_edits_to_gen(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo = tmp_path / "repo"
    repo.mkdir()
    log = tmp_path / "calls.log"

    # --- base commit: tooling (pipeline dependency stand-ins) and glossary ---
    git(repo, "init", "-q")
    write(repo / ".gitignore", ".hotdocs/\n__pycache__/\n*.pyc\n")
    write(repo / "specs" / "glossary.md", GLOSSARY)
    write_fakes(repo, log)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base: tooling and glossary")
    git(repo, "branch", "-M", "main")

    # --- the spec change, merged by a human ---
    git(repo, "checkout", "-q", "-b", "spec-change")
    comp = repo / "specs" / "components" / SLUG
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-DOUBLER-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-DOUBLER-001.md", ACCEPTANCE_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(repo / "specs" / "product" / "doubling.md", PRODUCT_MD)
    git(repo, "add", "-A", "specs")
    git(repo, "commit", "-q", "-m", "spec: add comp-doubler")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "--no-ff", "-q", "-m", "Merge spec change", "spec-change")
    spec_merge = head(repo)

    assert git(repo, "log", "-1", "--format=%ae", spec_merge).strip() == HUMAN_EMAIL
    assert git(repo, "ls-tree", "-r", "--name-only", spec_merge, "--", "gen/" + SLUG).strip() == ""

    # --- the pipeline runs on its own branch ---
    git(repo, "checkout", "-q", "-b", "pipeline/comp-doubler")
    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo, "claude-sonnet-5", seed=0, llm_backend=mock_backend, retry_feedback=None,
    )

    # Every gate passed, with nothing blocked.
    assert field(result, "component_id") == COMPONENT_ID
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
    for c in field(verification, "criteria"):
        assert field(c, "result") == "pass"
    assert field(field(result, "license_scan"), "blocked") is False
    assert field(field(result, "secret_scan"), "flagged") is False

    calls = read_log(log)
    names = [c["call"] for c in calls]
    for required in ("generate", "verify", "author_test", "license_scan",
                     "secret_scan", "write_attempt_record", "write_provenance"):
        assert required in names, required + " was never called; calls: " + repr(names)
    assert names.index("generate") < names.index("verify") < names.index("write_provenance")
    prov = [c for c in calls if c["call"] == "write_provenance"][-1]
    assert prov["component_id"] == COMPONENT_ID
    assert prov["overall"] == "pass"
    assert prov["license_blocked"] is False
    assert prov["secret_flagged"] is False
    assert prov["provenance_hit"] is False
    assert prov["attempts"] == 1

    # The pipeline's output is exactly what generation produced — no edits needed.
    for rel, content in GENERATED.items():
        assert (repo / "gen" / SLUG / rel).read_text() == content

    # --- the pipeline's own commit and merge commit ---
    git(repo, "add", "-A", "gen/" + SLUG, "verification/" + SLUG, name=BOT_NAME, email=BOT_EMAIL)
    git(repo, "commit", "-q", "-m", "pipeline: regenerate comp-doubler", name=BOT_NAME, email=BOT_EMAIL)
    git(repo, "checkout", "-q", "main", name=BOT_NAME, email=BOT_EMAIL)
    git(repo, "merge", "--no-ff", "-q", "-m", "pipeline: merge comp-doubler",
        "pipeline/comp-doubler", name=BOT_NAME, email=BOT_EMAIL)
    pipeline_merge = head(repo)

    parents = git(repo, "rev-list", "--parents", "-n", "1", pipeline_merge).split()
    assert len(parents) == 3, "the pipeline's merge commit is a real merge"
    assert git(repo, "log", "-1", "--format=%ae", pipeline_merge).strip() == BOT_EMAIL

    # Zero human-authored commits to gen/<component>/ between the two merges.
    touched = git(
        repo, "log", "--full-history", "-m",
        "--format=%H%x09%ae%x09%ce",
        spec_merge + ".." + pipeline_merge, "--", "gen/" + SLUG + "/",
    )
    lines = [line for line in touched.splitlines() if line.strip()]
    assert lines, "the pipeline's commits must be what put gen/doubler/ in place"
    for line in lines:
        sha, author_email, committer_email = line.split("\t")
        assert author_email == BOT_EMAIL, "human-authored commit to gen/doubler/: " + sha
        assert committer_email == BOT_EMAIL, "human-committed commit to gen/doubler/: " + sha
        assert author_email != HUMAN_EMAIL

    # Nothing under gen/<component>/ is left uncommitted or hand-modified.
    status = git(repo, "status", "--porcelain", "--untracked-files=all",
                 "--", "gen/" + SLUG, "verification/" + SLUG)
    assert status.strip() == ""

    # The merged gen/<component>/ is exactly the generated output, and its
    # committed provenance records every gate passing.
    for rel, content in GENERATED.items():
        committed = git(repo, "show", pipeline_merge + ":gen/" + SLUG + "/" + rel)
        assert committed == content
    manifest = json.loads(git(repo, "show", pipeline_merge + ":gen/" + SLUG + "/.provenance.json"))
    assert manifest["provenance_hit"] is False
    assert manifest["verification_report"]["overall"] == "pass"
    assert manifest["license_scan"]["blocked"] is False
    assert manifest["secret_scan"]["flagged"] is False
    assert manifest["spec_bundle_hash"] == SPEC_HASH