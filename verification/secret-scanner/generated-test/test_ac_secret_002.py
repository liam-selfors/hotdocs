import contextlib
import io
import json

import secret_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _run_main(argv):
    buf = io.StringIO()
    code = None
    try:
        with contextlib.redirect_stdout(buf):
            code = secret_scanner.main(argv)
    except SystemExit as exc:
        code = exc.code
    if code is None:
        code = 0
    return code, buf.getvalue()


def test_full_scan_with_match_flags_true_and_blocks_merge(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".secret-allowlist.json").write_text(
        json.dumps({"version": 1, "entries": []})
    )
    (repo_root / "config.py").write_text(
        'aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"\n'
    )

    result = secret_scanner.scan(repo_root)

    assert _get(result, "flagged") is True
    matches = _get(result, "matches")
    assert matches
    assert len(matches) >= 1

    exit_code, _ = _run_main(
        ["--repo-root=" + str(repo_root), "--format=json"]
    )

    assert exit_code == 1