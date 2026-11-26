# hotdocs-criterion: sha256:5cdc5afc89ee58d88db78937dc88553afbdbcc3d301b84e0f3455eba8f1c3c66
import os
import stat
import sys
import urllib.request

import pytest

import llm_endpoint


def _install_call_traps(monkeypatch, tmp_path):
    """Make any attempted call observable: HTTP via urlopen, claude-cli via PATH."""
    log_path = tmp_path / "calls.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    script = (
        "#!" + sys.executable + "\n"
        "import sys\n"
        "with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "    f.write('claude ' + ' '.join(sys.argv[1:]) + '\\n')\n"
        "sys.exit(1)\n"
    )
    claude_path = bin_dir / "claude"
    claude_path.write_text(script)
    claude_path.chmod(claude_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir))

    def fake_urlopen(request, timeout=None, *args, **kwargs):
        url = getattr(request, "full_url", request)
        with open(log_path, "a") as f:
            f.write("urlopen " + str(url) + "\n")
        raise OSError("no network in test")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return log_path


def _calls(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line.strip()]


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def test_unconfigured_non_claude_bare_name_raises_usage_error(workdir, tmp_path, monkeypatch):
    assert not (workdir / "hotdocs.toml").exists()
    log_path = _install_call_traps(monkeypatch, tmp_path)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("hello", "gpt-5")

    assert _calls(log_path) == [], "a call was attempted before the usage error"


def test_unconfigured_non_claude_name_never_returns_model_call_error(workdir, tmp_path, monkeypatch):
    _install_call_traps(monkeypatch, tmp_path)
    result = None
    try:
        result = llm_endpoint.complete("hello", "gpt-5")
    except llm_endpoint.ModelResolutionError:
        pass
    assert result is None, "expected ModelResolutionError, got a returned response: " + repr(result)


def test_openai_compatible_without_base_url_raises_same_usage_error(workdir, tmp_path, monkeypatch):
    (workdir / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "my-local-model"\n'
    )
    log_path = _install_call_traps(monkeypatch, tmp_path)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("hello", "my-local-model")

    assert _calls(log_path) == [], "a call was attempted before the usage error"


def test_invalid_hotdocs_toml_raises_same_usage_error(workdir, tmp_path, monkeypatch):
    (workdir / "hotdocs.toml").write_text("[llm\nthis is = = not toml\n")
    log_path = _install_call_traps(monkeypatch, tmp_path)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("hello", "my-local-model")

    assert _calls(log_path) == [], "a call was attempted before the usage error"