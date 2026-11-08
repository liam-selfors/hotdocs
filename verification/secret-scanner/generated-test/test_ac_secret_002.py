import contextlib
import io
import tempfile
import textwrap
from pathlib import Path

import secret_scanner


def _get_field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _write_fake_cache_manager(repo_root: Path) -> None:
    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True, exist_ok=True)
    module_path = cache_manager_dir / "cache_manager.py"
    module_path.write_text(
        textwrap.dedent(
            '''
            from dataclasses import dataclass


            @dataclass
            class CacheKey:
                spec_bundle_hash: str
                gate_inputs_hash: str
                gate_version: str
                model_pin: str


            @dataclass
            class CachedResult:
                gate_type: str
                payload: dict
                stored_at: str


            class Miss:
                pass


            def get(cache_key, *, repo_root=None):
                return Miss()


            def put(cache_key, result, *, repo_root=None):
                return None
            '''
        )
    )


def _run_main(argv):
    try:
        result = secret_scanner.main(argv)
    except SystemExit as exc:
        return exc.code
    return result


def test_full_scan_with_match_flags_and_blocks_merge():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _write_fake_cache_manager(repo_root)

        secret_file = repo_root / "config.py"
        secret_file.write_text('aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"\n')

        result = secret_scanner.scan(repo_root)

        flagged = _get_field(result, "flagged")
        matches = _get_field(result, "matches")

        assert flagged is True
        assert isinstance(matches, list)
        assert len(matches) >= 1

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = _run_main(
                ["--repo-root=" + str(repo_root), "--format=text"]
            )

        output = buf.getvalue()

        assert exit_code == 1
        assert "FLAGGED" in output