import json
import os
import shutil
import tempfile
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


LOG_HELPER = """
import json
import os


def _log(entry):
    with open(os.environ["AC_GATE_002B_LOG"], "a") as f:
        f.write(json.dumps(entry) + "\\n")
"""

ASSEMBLED_BUNDLE_HASH = "sha256:" + "b" * 64

FAKE_PROVENANCE_CHECKER = LOG_HELPER + """

def current_sealed_key(component_id, repo_root):
    return None


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
"""

FAKE_SPEC_BUNDLE_ASSEMBLER = LOG_HELPER + """

ASSEMBLED_BUNDLE_HASH = "{bundle_hash}"


def assemble(component_id, repo_root, mode="cold"):
    _log({{"call": "assemble", "component_id": component_id, "mode": mode}})
    return {{
        "component_id": component_id,
        "spec_bundle_hash": ASSEMBLED_BUNDLE_HASH,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "",
        "dependency_interfaces": {{}},
        "dependency_context": {{}},
        "dependency_usage": {{}},
        "vars": {{}},
        "glossary": "",
        "hint_code": None,
    }}


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError
""".format(bundle_hash=ASSEMBLED_BUNDLE_HASH)

FAKE_GENERATOR = LOG_HELPER + """

def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        bundle_hash = bundle.get("spec_bundle_hash")
        component_id = bundle.get("component_id")
    else:
        bundle_hash = getattr(bundle, "spec_bundle_hash", None)
        component_id = getattr(bundle, "component_id", None)
    _log({
        "call": "generate",
        "bundle_spec_bundle_hash": bundle_hash,
        "model": model,
        "retry_feedback": retry_feedback,
    })
    return {
        "component_id": component_id,
        "spec_bundle_hash": bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "# generated"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""

FAKE_VERIFIER_ORCHESTRATOR = LOG_HELPER + """

GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log({"call": "verify", "component_id": component_id})
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
"""

FAKE_LICENSE_SCANNER = LOG_HELPER + """

def scan(component_id, repo_root):
    _log({"call": "license_scan", "component_id": component_id})
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"
"""

FAKE_SECRET_SCANNER = LOG_HELPER + """

def scan(repo_root):
    _log({"call": "secret_scan"})
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "secret_scanner@3.0.0+detect-secrets.1.5.0"
"""

FAKE_PROVENANCE_TRACKER = LOG_HELPER + """

import json as _json
import os as _os


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log({"call": "write_attempt_record", "component_id": component_id})
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = _os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    _os.makedirs(attempts_dir, exist_ok=True)
    gen_dict = generation_result if isinstance(generation_result, dict) else {}
    ver_dict = verification_report if isinstance(verification_report, dict) else None
    record = {
        "attempt_id": "2026-11-02T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-11-02T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": gen_dict,
        "verification": ver_dict,
    }
    with open(_os.path.join(attempts_dir, "attempt-0001.json"), "w") as f:
        _json.dump(record, f)
    return record


def last_requirement_failures(component_id, repo_root):
    return []
"""

FAKE_PROVENANCE_WRITER = LOG_HELPER + """

def write_provenance(component_id, inputs, repo_root):
    _log({"call": "write_provenance", "component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log({"call": "write_sealed_provenance", "component_id": component_id})
    return None
"""

FAKE_TEST_AUTHOR = LOG_HELPER + """

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    _log({"call": "author_test"})
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-002",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {"path": "verification/foo/generated-test/test_ac_foo_002.py", "content": "# test"},
        "model_call_error": None,
    }
"""

FAKE_LLM_ENDPOINT = LOG_HELPER + """

def complete(prompt, model, *, backend=None, **params):
    _log({"call": "complete"})
    return {
        "text": "ok",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
"""


def test_ac_gate_002b():
    tmp_dir = tempfile.mkdtemp(prefix="ac_gate_002b_")
    old_log_env = os.environ.get("AC_GATE_002B_LOG")
    try:
        repo_root = Path(tmp_dir) / "repo"
        repo_root.mkdir(parents=True)
        log_path = Path(tmp_dir) / "invocations.jsonl"
        log_path.write_text("")
        os.environ["AC_GATE_002B_LOG"] = str(log_path)

        gen_dir = repo_root / "gen"

        _write(gen_dir / "provenance-checker" / "provenance_checker.py", FAKE_PROVENANCE_CHECKER)
        _write(gen_dir / "spec-bundle-assembler" / "spec_bundle_assembler.py", FAKE_SPEC_BUNDLE_ASSEMBLER)
        _write(gen_dir / "generator" / "generator.py", FAKE_GENERATOR)
        _write(gen_dir / "verifier-orchestrator" / "verifier_orchestrator.py", FAKE_VERIFIER_ORCHESTRATOR)
        _write(gen_dir / "license-scanner" / "license_scanner.py", FAKE_LICENSE_SCANNER)
        _write(gen_dir / "secret-scanner" / "secret_scanner.py", FAKE_SECRET_SCANNER)
        _write(gen_dir / "provenance-tracker" / "provenance_tracker.py", FAKE_PROVENANCE_TRACKER)
        _write(gen_dir / "provenance-writer" / "provenance_writer.py", FAKE_PROVENANCE_WRITER)
        _write(gen_dir / "test-author" / "test_author.py", FAKE_TEST_AUTHOR)
        _write(gen_dir / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT)

        result = component_gate_runner.run_component_gates(
            "comp-foo", repo_root, "m", retry_feedback=["R-FOO-002"]
        )

        assert _get(result, "blocked") is False
        assert _get(result, "block_reason") is None

        entries = []
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        calls_in_order = [e["call"] for e in entries]
        assert "assemble" in calls_in_order
        assert "generate" in calls_in_order
        assert "verify" in calls_in_order

        assemble_idx = calls_in_order.index("assemble")
        generate_idx = calls_in_order.index("generate")
        verify_idx = calls_in_order.index("verify")

        assert assemble_idx < generate_idx < verify_idx

        assemble_entry = entries[assemble_idx]
        generate_entry = entries[generate_idx]

        assert assemble_entry["mode"] == "cold"

        assert generate_entry["bundle_spec_bundle_hash"] == ASSEMBLED_BUNDLE_HASH
        assert generate_entry["model"] == "m"
        assert generate_entry["retry_feedback"] == ["R-FOO-002"]
    finally:
        if old_log_env is None:
            os.environ.pop("AC_GATE_002B_LOG", None)
        else:
            os.environ["AC_GATE_002B_LOG"] = old_log_env
        shutil.rmtree(tmp_dir, ignore_errors=True)