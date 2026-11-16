import json
import os
import subprocess
import urllib.error
import urllib.request

import pytest

import llm_endpoint


def _resolution_error_class():
    cls = getattr(llm_endpoint, "ModelResolutionError", None)
    assert cls is not None, "llm_endpoint must expose ModelResolutionError"
    assert isinstance(cls, type) and issubclass(cls, BaseException), (
        "ModelResolutionError must be an exception class"
    )
    return cls


def _read_log(log_path):
    if not log_path.exists():
        return []
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Fresh cwd, VAR_HOTDOCS_CONFIG unset, and every outbound call recorded."""
    workdir = tmp_path / "work"
    workdir.mkdir()
    log_path = tmp_path / "outbound_calls.log"
    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(workdir)
    # No `claude` command (or anything else) reachable on PATH.
    monkeypatch.setenv("PATH", str(empty_bin))

    def _record(kind, detail):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"kind": kind, "detail": detail}) + "\n")

    def fake_urlopen(request, *args, **kwargs):
        url = getattr(request, "full_url", None) or str(request)
        _record("urlopen", url)
        raise urllib.error.URLError("network blocked by test")

    def fake_run(*args, **kwargs):
        _record("subprocess.run", repr(args[:1]))
        raise OSError("subprocess blocked by test")

    class FakePopen:
        def __init__(self, *args, **kwargs):
            _record("subprocess.Popen", repr(args[:1]))
            raise OSError("subprocess blocked by test")

    def fake_check_output(*args, **kwargs):
        _record("subprocess.check_output", repr(args[:1]))
        raise OSError("subprocess blocked by test")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    return {"workdir": workdir, "log_path": log_path}


def test_unmatched_bare_name_without_config_raises_usage_error_before_any_call(isolated):
    err_cls = _resolution_error_class()
    workdir = isolated["workdir"]
    assert not (workdir / "hotdocs.toml").exists()
    assert os.environ.get("VAR_HOTDOCS_CONFIG") in (None, "")

    with pytest.raises(err_cls) as excinfo:
        llm_endpoint.complete("Say hello.", "gpt-5")

    # A usage error, raised -- never returned as a model_call_error.
    assert str(excinfo.value).strip() != ""
    # Nothing was attempted: no HTTP request, no `claude` command.
    assert _read_log(isolated["log_path"]) == []


def test_openai_compatible_config_without_base_url_raises_usage_error(isolated):
    err_cls = _resolution_error_class()
    workdir = isolated["workdir"]
    (workdir / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "my-local-model"\n',
        encoding="utf-8",
    )

    with pytest.raises(err_cls) as excinfo:
        llm_endpoint.complete("Say hello.", "my-local-model")

    assert str(excinfo.value).strip() != ""
    assert _read_log(isolated["log_path"]) == []


def test_invalid_config_raises_same_usage_error(isolated):
    err_cls = _resolution_error_class()
    workdir = isolated["workdir"]
    (workdir / "hotdocs.toml").write_text(
        "[llm\nprovider = = \"openai\nmodel\n",
        encoding="utf-8",
    )

    with pytest.raises(err_cls) as excinfo:
        llm_endpoint.complete("Say hello.", "some-model")

    assert str(excinfo.value).strip() != ""
    assert _read_log(isolated["log_path"]) == []


def test_missing_base_url_and_invalid_config_raise_the_same_error_type(isolated):
    err_cls = _resolution_error_class()
    workdir = isolated["workdir"]
    config_path = workdir / "hotdocs.toml"

    config_path.write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "my-local-model"\n',
        encoding="utf-8",
    )
    missing_base_url_exc = None
    try:
        llm_endpoint.complete("Say hello.", "my-local-model")
    except BaseException as exc:  # noqa: BLE001
        missing_base_url_exc = exc

    config_path.write_text("this is [[[ not valid toml =\n", encoding="utf-8")
    invalid_exc = None
    try:
        llm_endpoint.complete("Say hello.", "my-local-model")
    except BaseException as exc:  # noqa: BLE001
        invalid_exc = exc

    assert isinstance(missing_base_url_exc, err_cls), (
        f"expected ModelResolutionError for missing base_url, got {missing_base_url_exc!r}"
    )
    assert isinstance(invalid_exc, err_cls), (
        f"expected ModelResolutionError for invalid hotdocs.toml, got {invalid_exc!r}"
    )
    assert _read_log(isolated["log_path"]) == []