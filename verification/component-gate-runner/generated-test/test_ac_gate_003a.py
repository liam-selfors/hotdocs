import shutil
import tempfile
import unittest
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestACGate003a(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo_root, ignore_errors=True)
        self.generator_call_log = self.repo_root / "generator_calls.log"

        self._write_fixture_component()
        self._write_fake_dependencies()

    def _write_fixture_component(self):
        comp_dir = self.repo_root / "specs" / "components" / "foo"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(
            "---\n"
            "id: comp-foo\n"
            "title: Foo\n"
            "status: draft\n"
            "owners: [test-team]\n"
            "sealed: false\n"
            "---\n\n"
            "# Foo\n\n"
            "Purpose: test fixture for AC-GATE-003a.\n"
        )

    def _write_module(self, dep_slug, module_name, content):
        dep_dir = self.repo_root / "gen" / dep_slug
        dep_dir.mkdir(parents=True, exist_ok=True)
        (dep_dir / f"{module_name}.py").write_text(content)

    def _write_fake_dependencies(self):
        self._write_module(
            "provenance-checker",
            "provenance_checker",
            '''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


class ProvenanceCheckResult:
    def __init__(self, hit):
        self.hit = hit
        self.verification_report = None
        self.license_scan = None
        self.secret_scan = None


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "0" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return ProvenanceCheckResult(hit=False)
''',
        )

        self._write_module(
            "spec-bundle-assembler",
            "spec_bundle_assembler",
            '''
class SpecBundle:
    def __init__(self, component_id, spec_bundle_hash):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.spec = ""
        self.interface = ""
        self.constraints = ""
        self.dependency_interfaces = {}
        self.dependency_context = {}
        self.dependency_usage = {}
        self.vars = {}
        self.glossary = ""
        self.hint_code = None


def assemble(component_id, repo_root, mode="cold"):
    return SpecBundle(component_id, "sha256:" + "0" * 64)
''',
        )

        generator_log_path = str(self.generator_call_log)
        self._write_module(
            "generator",
            "generator",
            f'''
GENERATOR_CALL_LOG = {generator_log_path!r}


class GenerationResult:
    def __init__(self, component_id, spec_bundle_hash, model, prompt_version,
                 cache_hit, files, model_call_error, refused, retry_feedback):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.model = model
        self.prompt_version = prompt_version
        self.cache_hit = cache_hit
        self.files = files
        self.model_call_error = model_call_error
        self.refused = refused
        self.retry_feedback = retry_feedback


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    with open(GENERATOR_CALL_LOG, "a") as f:
        f.write("call\\n")
    return GenerationResult(
        component_id=bundle.component_id,
        spec_bundle_hash=bundle.spec_bundle_hash,
        model=model,
        prompt_version="v1",
        cache_hit=False,
        files={{"foo.py": "# generated content"}},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
''',
        )

        self._write_module(
            "verifier-orchestrator",
            "verifier_orchestrator",
            '''
GATE_VERSION = "verifier-orchestrator@2.0.0"


class VerificationReport:
    def __init__(self, component_id):
        self.component_id = component_id
        self.criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ]
        self.requirement_results = {"R-FOO-001": "pass"}
        self.interface_drift = False
        self.mutation_score = 1.0
        self.overall = "pass"

    def to_dict(self):
        return dict(self.__dict__)


def verify(component_id, repo_root, judge=None, test_author=None):
    return VerificationReport(component_id)
''',
        )

        self._write_module(
            "license-scanner",
            "license_scanner",
            '''
def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"


class LicenseScanResult:
    def __init__(self, component_id):
        self.component_id = component_id
        self.gate_version = gate_version(None)
        self.evaluated = False
        self.reason = "no-reference-corpus"
        self.similarity_score = None
        self.block_threshold = None
        self.blocked = False
        self.matches = []
        self.notified = False
        self.notification_delivery_error = None
        self.cache_hit = False

    def to_dict(self):
        return dict(self.__dict__)


def scan(component_id, repo_root):
    return LicenseScanResult(component_id)
''',
        )

        self._write_module(
            "secret-scanner",
            "secret_scanner",
            '''
def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


class SecretScanResult:
    def __init__(self):
        self.scope = "full"
        self.gate_version = gate_version(None)
        self.flagged = False
        self.matches = []
        self.allowed = []
        self.unused_allowlist_entries = []
        self.notified = False
        self.notification_delivery_error = None
        self.cache_hit = False

    def to_dict(self):
        return dict(self.__dict__)


def scan(repo_root):
    return SecretScanResult()
''',
        )

        self._write_module(
            "provenance-tracker",
            "provenance_tracker",
            '''
from pathlib import Path


class AttemptRecord:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def write_attempt_record(component_id, generation_result, verification_report,
                          spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "attempt-1.json").write_text("{}")
    return AttemptRecord(
        attempt_id="attempt-1",
        component_id=component_id,
        timestamp="2026-01-01T00:00:00Z",
        spec_bundle_hash=spec_bundle_hash,
        generation=generation_result,
        verification=verification_report,
    )
''',
        )

        self._write_module(
            "provenance-writer",
            "provenance_writer",
            '''
def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
''',
        )

    def test_non_sealed_miss_one_file_pass(self):
        result = component_gate_runner.run_component_gates(
            "comp-foo", self.repo_root, model="claude-sonnet-5", seed=0,
        )

        self.assertTrue(self.generator_call_log.exists())
        calls = self.generator_call_log.read_text().splitlines()
        self.assertEqual(len(calls), 1)

        self.assertFalse(_get(result, "blocked"))
        self.assertIsNone(_get(result, "block_reason"))
        self.assertIsNone(_get(result, "model_call_error"))

        verification = _get(result, "verification")
        self.assertEqual(_get(verification, "overall"), "pass")


if __name__ == "__main__":
    unittest.main()