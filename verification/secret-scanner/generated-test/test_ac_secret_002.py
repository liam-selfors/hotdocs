import contextlib
import io
import json

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_full_scan_with_match_flags_true_and_blocks_merge(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    secret_file = repo_root / "config.py"
    secret_file.write_text('AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"\n')

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is True
    matches = _get(result, "matches")
    assert matches
    assert len(matches) >= 1

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = secret_scanner.main(
            ["--repo-root=" + str(repo_root), "--format=json"]
        )

    assert exit_code == 1

    payload = json.loads(stdout.getvalue())
    assert payload["flagged"] is True