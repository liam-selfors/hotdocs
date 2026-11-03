import shutil
import tempfile
import unittest
from pathlib import Path

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TestAcSecret004c(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="hotdocs-ac-secret-004c-"))
        self.addCleanup(shutil.rmtree, self.repo_root, ignore_errors=True)

    def test_clean_scan_notified_false(self):
        clean_file = self.repo_root / "clean.txt"
        clean_file.write_text("hello world, nothing secret here\n")

        result = secret_scanner.scan_files([clean_file], repo_root=self.repo_root)

        self.assertEqual(_get(result, "matches"), [])
        self.assertFalse(_get(result, "flagged"))
        self.assertFalse(_get(result, "notified"))


if __name__ == "__main__":
    unittest.main()