import os
import stat
import urllib.request

import pytest

import llm_endpoint


def _install_call_traps(tmp_path, monkeypatch):
    """Record any attempted model call: an HTTP request or a `claude` run."""
    log_path = tmp_path / "attempted_calls.log"
    log_path.write_text("")

    def fake_urlopen(request, *args, **kwargs):
        url = getattr(request, "full_url", request)
        with open(log_path, "a") as fh:
            fh.write("urlopen %s\n" % (url,))
        raise OSError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    script.write_text(
        "#!/bin/sh\n"
        'echo "claude $*" >> "%s"\n'
        "exit 1\n" % str(log_path)
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return log_path


def _fresh_cwd(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def test_unconfigured_non_claude_bare_name_raises_model_resolution_error(tmp_path, monkeypatch):
    work = _fresh_cwd(tmp_path, monkeypatch)
    assert not (work / "hotdocs.toml").exists()
    log_path = _install_call_traps(tmp_path, monkeypatch)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("Say hello.", "gpt-5")

    # Failed before any call was attempted: no HTTP request, no claude run.
    assert log_path.read_text() == ""


def test_openai_compatible_without_base_url_raises_model_resolution_error(tmp_path, monkeypatch):
    work = _fresh_cwd(tmp_path, monkeypatch)
    (work / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "my-local-model"\n'
    )
    log_path = _install_call_traps(tmp_path, monkeypatch)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("Say hello.", "my-local-model")

    assert log_path.read_text() == ""


def test_invalid_hotdocs_toml_raises_same_model_resolution_error(tmp_path, monkeypatch):
    work = _fresh_cwd(tmp_path, monkeypatch)
    (work / "hotdocs.toml").write_text("[llm\nprovider = \n")
    log_path = _install_call_traps(tmp_path, monkeypatch)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("Say hello.", "my-local-model")

    assert log_path.read_text() == ""