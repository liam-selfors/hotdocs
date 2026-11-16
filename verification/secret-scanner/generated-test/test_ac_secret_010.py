import hashlib
import textwrap
import urllib.request

import pytest

import secret_scanner


# The token and hex digest are assembled at runtime from short pieces so this
# test file itself never holds a long random-looking literal (the real repo's
# own secret scan covers this file too).
_TOKEN_PIECES = [
    "aB3d", "E5gH", "7jK9", "mN1p", "Q3sT",
    "5vW7", "yZ9b", "D1fH", "3jL5", "nP7r",
]
TOKEN = "".join(_TOKEN_PIECES)
# First 40 hex digits of SHA-256(b"test"): 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b
SHA = hashlib.sha256(b"test").hexdigest()[:40]

LOG_ENV = "SECRET_SCAN_FAKE_CACHE_LOG"

FAKE_CACHE_MANAGER = textwrap.dedent(
    '''\
    import dataclasses
    import datetime
    import os


    class SchemaValidationError(ValueError):
        pass


    @dataclasses.dataclass
    class CacheKey:
        spec_bundle_hash: str
        gate_inputs_hash: str
        gate_version: str
        model_pin: str


    @dataclasses.dataclass
    class CachedResult:
        gate_type: str
        payload: dict
        stored_at: str


    class Miss:
        def __eq__(self, other):
            return isinstance(other, Miss)

        def __hash__(self):
            return 0


    _REQUIRED = {
        "generator": ["component_id", "model", "prompt_version", "files"],
        "compiler": ["outputs", "gate_version", "summary"],
        "generated_test": ["component_id", "criterion_id", "model", "file"],
        "llm_judge": ["result", "rationale"],
        "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
        "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
    }


    def _field(obj, name):
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)


    def _log(op):
        path = os.environ.get("SECRET_SCAN_FAKE_CACHE_LOG")
        if path:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(op + "\\n")


    def get(cache_key, *, repo_root=None):
        _log("get")
        return Miss()


    def put(cache_key, result, *, repo_root=None):
        _log("put")
        gate_type = _field(result, "gate_type")
        key_version = _field(cache_key, "gate_version") or ""
        if gate_type not in _REQUIRED:
            raise SchemaValidationError("unknown gate type")
        if key_version.split("@")[0] != gate_type:
            raise SchemaValidationError("gate type mismatch")
        payload = _field(result, "payload")
        if not isinstance(payload, dict):
            raise SchemaValidationError("payload not a dict")
        for name in _REQUIRED[gate_type]:
            if name not in payload:
                raise SchemaValidationError("missing key")
        return None


    def now_iso():
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


    def stats(*, repo_root=None):
        return {"entry_count": 0}
    '''
)


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_repo(tmp_path, monkeypatch, e_py_text):
    repo_root = tmp_path / "repo"
    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "cache-manager").mkdir(parents=True)
    (repo_root / "gen" / "cache-manager" / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER, encoding="utf-8"
    )
    (repo_root / "gen" / "foo" / "e.py").write_text(e_py_text, encoding="utf-8")

    log_path = tmp_path / "fake_cache_log.txt"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    def _no_network(*args, **kwargs):
        raise AssertionError("urlopen must not be called in this test")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    return repo_root


def _projected(matches):
    out = []
    for m in matches:
        out.append(
            (
                _field(m, "file"),
                _field(m, "line"),
                _field(m, "rule_id"),
                _field(m, "risk_tier"),
            )
        )
    return out


def test_quoted_base64_and_hex_strings_are_low_tier_matches(tmp_path, monkeypatch):
    assert len(TOKEN) == 40
    assert len(SHA) == 40
    text = 'token = "%s"\nsha = "%s"\n' % (TOKEN, SHA)
    repo_root = _make_repo(tmp_path, monkeypatch, text)

    result = secret_scanner.scan(repo_root)

    matches = _field(result, "matches")
    assert matches is not None
    matches = list(matches)
    assert len(matches) == 2, matches

    assert _projected(matches) == [
        ("gen/foo/e.py", 1, "Base64 High Entropy String", "low"),
        ("gen/foo/e.py", 2, "Hex High Entropy String", "low"),
    ]

    for m in matches:
        values = list(m.values()) if isinstance(m, dict) else list(vars(m).values())
        for v in values:
            assert v != TOKEN
            assert v != SHA
            if isinstance(v, str):
                assert TOKEN not in v
                assert SHA not in v

    assert _field(result, "flagged") is True


def test_unquoted_token_is_not_matched(tmp_path, monkeypatch):
    text = "token = %s\n" % TOKEN
    repo_root = _make_repo(tmp_path, monkeypatch, text)

    result = secret_scanner.scan(repo_root)

    matches = _field(result, "matches")
    assert matches is not None
    assert list(matches) == []
    assert _field(result, "flagged") is False