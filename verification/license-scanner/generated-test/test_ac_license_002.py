import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


CACHE_MANAGER_SOURCE = r"""
import dataclasses
import json
import os


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


def get(cache_key, *, repo_root=None):
    # Always a miss: payload is null, forcing a fresh scan.
    return {"gate_type": None, "payload": None, "stored_at": None}


def put(cache_key, result, *, repo_root=None):
    log_path = os.environ["TEST_CACHE_PUT_LOG"]
    record = {"gate_type": result.gate_type, "payload": result.payload}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
"""


class AcLicense002Test(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo_root = Path(self._tmp.name)

        # Clean, non-matching generated content for the scanned component.
        widget_dir = self.repo_root / "gen" / "widget"
        widget_dir.mkdir(parents=True)
        (widget_dir / "main.py").write_text(
            textwrap.dedent(
                """
                def add(a, b):
                    return a + b


                def subtract(a, b):
                    return a - b
                """
            ),
            encoding="utf-8",
        )

        # Reference corpus whose single hash cannot match the clean content
        # above (it is not derived from any real 9-token window of it).
        corpus_dir = self.repo_root / "corpus"
        corpus_dir.mkdir(parents=True)
        corpus_path = corpus_dir / "reference.json"
        corpus_path.write_text(
            json.dumps(
                {
                    "corpus_version": 7,
                    "block_threshold": 0.70,
                    "entries": [
                        {
                            "reference_id": "ref-999",
                            "license_family": "mit",
                            "risk_tier": "low",
                            "hashes": ["f" * 64],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        # Fake cache-manager dependency, loaded by the target at runtime
        # from gen/cache-manager/cache_manager.py (flat module), per its
        # own documented dynamic-loading contract.
        cache_manager_dir = self.repo_root / "gen" / "cache-manager"
        cache_manager_dir.mkdir(parents=True)
        (cache_manager_dir / "cache_manager.py").write_text(
            CACHE_MANAGER_SOURCE, encoding="utf-8"
        )

        self._put_log = self.repo_root / "cache_put_log.jsonl"
        self._put_log.write_text("", encoding="utf-8")

        self._old_env = {}
        for key, value in {
            "VAR_LICENSE_CORPUS_PATH": str(Path("corpus") / "reference.json"),
            "TEST_CACHE_PUT_LOG": str(self._put_log),
        }.items():
            self._old_env[key] = os.environ.get(key)
            os.environ[key] = value
        # Ensure notification is not accidentally triggered by an
        # inherited webhook configuration from the outer environment.
        self._old_env["VAR_COMPLIANCE_WEBHOOK_URL"] = os.environ.pop(
            "VAR_COMPLIANCE_WEBHOOK_URL", None
        )
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for key, old_value in self._old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value

    def test_clean_scan_result_is_still_recorded_not_omitted(self):
        import license_scanner

        result = license_scanner.scan("comp-widget", self.repo_root)

        self.assertIsNotNone(result)
        self.assertEqual(_get(result, "component_id"), "comp-widget")
        self.assertEqual(_get(result, "gate_version"), "license_scanner@3.1.7")
        self.assertEqual(_get(result, "similarity_score"), 0.0)
        self.assertEqual(_get(result, "block_threshold"), 0.70)
        self.assertEqual(_get(result, "blocked"), False)
        self.assertEqual(_get(result, "matches"), [])
        self.assertEqual(_get(result, "notified"), False)
        self.assertIsNone(_get(result, "notification_delivery_error"))
        self.assertEqual(_get(result, "cache_hit"), False)

        # A clean result must still flow through the exact same recording
        # path ("after a fresh scan, put(...)") that a flagged result
        # would use -- never silently skipped because nothing was flagged.
        log_lines = self._put_log.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(log_lines), 1)

        recorded = json.loads(log_lines[0])
        self.assertEqual(recorded["gate_type"], "license_scanner")

        payload = recorded["payload"]
        self.assertIsNotNone(payload)
        for field in (
            "component_id",
            "gate_version",
            "similarity_score",
            "block_threshold",
            "blocked",
            "matches",
            "notified",
            "notification_delivery_error",
            "cache_hit",
        ):
            self.assertEqual(_get(payload, field), _get(result, field), field)


if __name__ == "__main__":
    unittest.main()