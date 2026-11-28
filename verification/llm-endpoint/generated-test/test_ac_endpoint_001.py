# hotdocs-criterion: sha256:fa775f0e0bb0c3b20454927d38e580139db34efa8450212bfde1ebb1d35a1b17
import subprocess
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Fresh cwd, no VAR_HOTDOCS_CONFIG, and recorders that note any call attempt."""
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    attempts = []

    def fake_urlopen(*args, **kwargs):
        attempts.append(("urlopen", args, kwargs))
        raise AssertionError("no HTTP call may be attempted")

    real_run = subprocess.run

    def fake_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        text = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        if "claude" in text:
            attempts.append(("subprocess", args, kwargs))
            raise AssertionError("no claude command may be run")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(subprocess, "run", fake_run)

    # A fake `claude` first on PATH that records if it is ever invoked.
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "claude_calls.log"
    script = bindir / "claude"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "with open(" + repr(str(log)) + ", 'a') as f:\n"
        "    f.write(' '.join(sys.argv[1:]) + '\\n')\n"
    )
    script.chmod(0o755)
    import os

    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))

    return {"dir": workdir, "attempts": attempts, "log": log}


def _assert_no_call(env):
    assert env["attempts"] == []
    assert not env["log"].exists() or env["log"].read_text() == ""


def test_unmatched_bare_name_without_config_raises_usage_error(isolated):
    assert not (isolated["dir"] / "hotdocs.toml").exists()
    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("hello", "gpt-5")
    _assert_no_call(isolated)


def test_injected_backend_bypasses_resolution(isolated):
    def backend(prompt, model, **params):
        return {
            "text": "ok",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = llm_endpoint.complete("hello", "gpt-5", backend=backend)
    assert field(result, "model") == "gpt-5"
    assert field(result, "text") == "ok"
    assert field(result, "model_call_error") is None
    _assert_no_call(isolated)


def test_openai_compatible_without_base_url_raises_usage_error(isolated):
    (isolated["dir"] / "hotdocs.toml").write_text(
        "[llm]\n"
        'provider = "openai-compatible"\n'
        'model = "my-local-model"\n'
    )
    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("hello", "my-local-model")
    _assert_no_call(isolated)


def test_invalid_config_raises_same_usage_error(isolated):
    (isolated["dir"] / "hotdocs.toml").write_text(
        "[llm\n"
        "provider = = not valid toml\n"
    )
    with pytest.raises(llm_endpoint.ModelResolutionError):
        llm_endpoint.complete("hello", "my-local-model")
    _assert_no_call(isolated)