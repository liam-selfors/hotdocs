import os
import shutil
import tempfile
import textwrap
from pathlib import Path

import secret_scanner


def _write_fake_cache_manager(gen_dir: Path) -> None:
    cache_manager_dir = gen_dir / "cache-manager"
    cache_manager_dir.mkdir(parents=True, exist_ok=True)
    module_path = cache_manager_dir / "cache_manager.py"
    module_path.write_text(
        textwrap.dedent(
            """
            from dataclasses import dataclass
            from typing import Any


            @dataclass
            class CacheKey:
                spec_bundle_hash: str
                gate_inputs_hash: str
                gate_version: str
                model_pin: str


            @dataclass
            class CachedResult:
                gate_type: str
                payload: Any
                stored_at: str


            class Miss:
                pass


            def get(cache_key, *, repo_root=None):
                return Miss()


            def put(cache_key, result, *, repo_root=None):
                return None
            """
        )
    )


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def test_clean_scan_has_notified_false():
    repo_root = Path(tempfile.mkdtemp(prefix="secscan_repo_"))
    saved_webhook_var = os.environ.get("VAR_COMPLIANCE_WEBHOOK_URL")
    try:
        if "VAR_COMPLIANCE_WEBHOOK_URL" in os.environ:
            del os.environ["VAR_COMPLIANCE_WEBHOOK_URL"]

        gen_dir = repo_root / "gen"
        _write_fake_cache_manager(gen_dir)

        (repo_root / "README.md").write_text(
            "This project documentation contains no secrets at all.\n"
        )
        (repo_root / "notes.txt").write_text(
            "Just a plain text file with ordinary, unremarkable words.\n"
        )

        result = secret_scanner.scan(repo_root)

        matches = _field(result, "matches")
        flagged = _field(result, "flagged")
        notified = _field(result, "notified")
        notification_delivery_error = _field(result, "notification_delivery_error")

        assert matches is not None
        assert len(matches) == 0
        assert flagged is False
        assert notified is False
        assert notification_delivery_error is None
    finally:
        if saved_webhook_var is None:
            os.environ.pop("VAR_COMPLIANCE_WEBHOOK_URL", None)
        else:
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = saved_webhook_var
        shutil.rmtree(repo_root, ignore_errors=True)