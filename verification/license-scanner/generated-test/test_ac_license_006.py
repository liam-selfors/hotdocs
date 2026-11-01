import os
import shutil
import tempfile
import unittest
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _has(obj, key):
    if isinstance(obj, dict):
        return key in obj
    return hasattr(obj, key)


FAKE_CACHE_MANAGER_SOURCE = '''
import dataclasses
import os

_INVOCATIONS_FILE = os.environ.get("FAKE_CACHE_INVOCATIONS_FILE")


def _record(event):
    if _INVOCATIONS_FILE:
        with open(_INVOCATIONS_FILE, "a") as f:
            f.write(event + "\\n")


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    _record("get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _record("put")
    return None
'''


class ExactlyOneLicenseScanResultTest(unittest.TestCase):
    def setUp(self):
        self.repo_root_str = tempfile.mkdtemp(prefix="hotdocs-license-scanner-test-")
        self.repo_root = Path(self.repo_root_str)
        self.invocations_file = os.path.join(self.repo_root_str, "invocations.log")

        cache_manager_dir = os.path.join(self.repo_root_str, "gen", "cache-manager")
        os.makedirs(cache_manager_dir, exist_ok=True)
        with open(os.path.join(cache_manager_dir, "cache_manager.py"), "w") as f:
            f.write(FAKE_CACHE_MANAGER_SOURCE)

        self._old_environ = dict(os.environ)
        os.environ["FAKE_CACHE_INVOCATIONS_FILE"] = self.invocations_file
        os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
        os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_environ)
        shutil.rmtree(self.repo_root_str, ignore_errors=True)

    def test_exactly_one_result_for_the_component(self):
        import license_scanner

        component_id = "comp-sample-widget"

        result_one = license_scanner.scan(component_id, self.repo_root)

        # The result must be a single structured object, never a collection
        # of multiple results.
        self.assertNotIsInstance(result_one, (list, tuple, set))
        self.assertIsNotNone(result_one)

        self.assertEqual(_get(result_one, "component_id"), component_id)

        required_fields = (
            "component_id",
            "gate_version",
            "similarity_score",
            "block_threshold",
            "blocked",
            "matches",
            "notified",
            "notification_delivery_error",
            "cache_hit",
        )
        for field in required_fields:
            self.assertTrue(
                _has(result_one, field),
                "LicenseScanResult is missing required field: %s" % field,
            )

        self.assertIsInstance(_get(result_one, "similarity_score"), (int, float))
        self.assertIsInstance(_get(result_one, "blocked"), bool)
        self.assertIsInstance(_get(result_one, "matches"), list)
        self.assertIsInstance(_get(result_one, "cache_hit"), bool)
        self.assertTrue(
            str(_get(result_one, "gate_version")).startswith("license_scanner@")
        )

        # Run the scan again for the same component: each individual scan
        # must still yield exactly one LicenseScanResult for that component.
        result_two = license_scanner.scan(component_id, self.repo_root)
        self.assertNotIsInstance(result_two, (list, tuple, set))
        self.assertIsNotNone(result_two)
        self.assertEqual(_get(result_two, "component_id"), component_id)

        with open(self.invocations_file) as f:
            invocation_lines = [line.strip() for line in f if line.strip()]

        self.assertIn("get", invocation_lines)
        self.assertIn("put", invocation_lines)


if __name__ == "__main__":
    unittest.main()