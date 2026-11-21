# hotdocs-criterion: sha256:3bd4ff41770ce4487532f0fab29e81e8abf2360d10338dbee0d6234bcafb6dc4
import os
import stat
import sys
import urllib.request

import pytest

import llm_endpoint


def _install_call_traps(tmp_path, monkeypatch):
    """Record any attempt to reach a network or the claude command."""
    log_path = tmp_path / "call_attempts.log"

    def fake_urlopen(*args, **kwargs):
        with open(log_path, "a") as fh:
            fh.write("urlopen\n")
        raise AssertionError("urlopen must not be called")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "claude"
    source = (
        "#!" + sys.executable + "\n"
        "import sys\n"
        "with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "    fh.write('claude ' + ' '.join(sys.argv[1:]) + '\\n')\n"
        "sys.exit(1)\n"
    )
    script.write_text(source)
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return log_path


def _fresh_cwd(tmp_path, monkeypatch, name):
    work = tmp_path / name
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return work


def test_unmatched_bare_name_without_config_raises_usage_error(tmp_path, monkeypatch):
    work = _fresh_cwd(tmp_path, monkeypatch, "work")
    assert not (work / "hotdocs.toml").exists()
    log_path = _install_call_traps(tmp_path, monkeypatch)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("Say hello.", "gpt-5")

    assert not log_path.exists(), log_path.read_text()


def test_openai_compatible_without_base_url_raises_usage_error(tmp_path, monkeypatch):
    work = _fresh_cwd(tmp_path, monkeypatch, "work")
    (work / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "my-local-model"\n'
    )
    log_path = _install_call_traps(tmp_path, monkeypatch)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("Say hello.", "my-local-model")

    assert not log_path.exists(), log_path.read_text()


def test_invalid_config_raises_same_usage_error(tmp_path, monkeypatch):
    work = _fresh_cwd(tmp_path, monkeypatch, "work")
    (work / "hotdocs.toml").write_text("[llm\nprovider = = broken\n")
    log_path = _install_call_traps(tmp_path, monkeypatch)

    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("Say hello.", "my-local-model")

    assert not log_path.exists(), log_path.read_text()