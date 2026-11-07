import importlib.metadata

import pytest

import hotdocs_init


FAKE_LLM_ENDPOINT_SOURCE = '''
PROVIDERS = {
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4o-mini",
    },
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
}


def detect_providers(env=None, probe_ollama=True):
    entries = []
    for name, info in PROVIDERS.items():
        entries.append(
            {
                "provider": name,
                "available": False,
                "reason": "not probed in fake",
                "suggested_model": info["suggested_model"],
                "api_key_env": info["default_api_key_env"],
            }
        )
    return entries


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url is required for provider: " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    from pathlib import Path

    path = Path(config_path)
    existing = path.read_text() if path.exists() else ""
    kept = []
    skipping = False
    for line in existing.splitlines():
        if line.strip() == "[llm]":
            skipping = True
            continue
        if skipping and line.strip().startswith("[") and line.strip() != "[llm]":
            skipping = False
        if not skipping:
            kept.append(line)

    block = ["[llm]", 'provider = "%s"' % provider, 'model = "%s"' % model]
    if base_url:
        block.append('base_url = "%s"' % base_url)
    if api_key_env:
        block.append('api_key_env = "%s"' % api_key_env)
    if timeout_seconds is not None:
        block.append("timeout_seconds = %d" % timeout_seconds)

    text = "\\n".join(kept).rstrip("\\n")
    text = (text + "\\n\\n" if text else "") + "\\n".join(block) + "\\n"
    path.write_text(text)


def load_config(config_path=None):
    from pathlib import Path

    if config_path is None:
        return None
    path = Path(config_path)
    if not path.exists():
        return None
    text = path.read_text()
    if "[llm]" not in text:
        return None

    provider = None
    model = None
    base_url = None
    api_key_env = None
    timeout_seconds = None
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[llm]":
            in_section = True
            continue
        if stripped.startswith("[") and stripped != "[llm]":
            in_section = False
            continue
        if in_section and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip(chr(34))
            if key == "provider":
                provider = value
            elif key == "model":
                model = value
            elif key == "base_url":
                base_url = value
            elif key == "api_key_env":
                api_key_env = value
            elif key == "timeout_seconds":
                timeout_seconds = int(value)

    if provider is None:
        raise ValueError("invalid [llm] section: missing provider")

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
    }
'''


PROVIDER_KEYS = ["openai", "claude-cli", "openai-compatible"]


@pytest.fixture
def tool_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("tool_root")
    (root / "gen" / "llm-endpoint").mkdir(parents=True)
    (root / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(FAKE_LLM_ENDPOINT_SOURCE)
    (root / "pipeline" / "criterion-compiler").mkdir(parents=True)
    (root / "pipeline" / "criterion-compiler" / "criterion_compiler.py").write_text(
        "# fake criterion-compiler placeholder\n"
    )
    pytest_version = importlib.metadata.version("pytest")
    (root / "requirements.txt").write_text("pytest==%s\n" % pytest_version)
    return root


def _refuse_input(_prompt):
    raise AssertionError("input_fn must not be called for a usage error")


def _call(argv, tool_root, project, capsys, env=None):
    messages = []
    rc = hotdocs_init.main(
        list(argv),
        tool_root=str(tool_root),
        input_fn=_refuse_input,
        output_fn=messages.append,
        env={} if env is None else env,
        cwd=str(project),
    )
    captured = capsys.readouterr()
    return rc, messages, captured.out, captured.err


def test_malformed_usage_returns_2_and_writes_nothing(tool_root, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()

    cases = [
        ["--bogus"],
        ["--provider"],
        ["a", "b"],
        ["--provider", "nope"],
        ["--provider=openai", "--model"],
    ]

    for argv in cases:
        before = sorted(p.name for p in project.iterdir())
        rc, _messages, _out, err = _call(argv, tool_root, project, capsys)
        after = sorted(p.name for p in project.iterdir())

        assert rc == 2, "argv=%r returned %r" % (argv, rc)
        assert after == before, "argv=%r wrote to the target directory" % (argv,)

        if argv == ["--provider", "nope"]:
            for key in PROVIDER_KEYS:
                assert key in err, (
                    "expected PROVIDERS key %r in the error message for argv=%r, got %r"
                    % (key, argv, err)
                )


def test_invalid_api_key_env_name_never_echoes_the_value(tool_root, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()

    suspicious_value = "s" + "k-" + "abc123"
    cases = [
        ["--provider", "openai", "--api-key-env", suspicious_value],
        ["--provider", "openai", "--api-key-env", "9X"],
    ]

    for argv in cases:
        before = sorted(p.name for p in project.iterdir())
        rc, messages, out, err = _call(argv, tool_root, project, capsys)
        after = sorted(p.name for p in project.iterdir())

        assert rc == 2, "argv=%r returned %r" % (argv, rc)
        assert after == before, "argv=%r wrote to the target directory" % (argv,)
        assert suspicious_value not in out
        assert suspicious_value not in err
        for message in messages:
            assert suspicious_value not in str(message)


def test_claude_cli_rejects_base_url_and_api_key_env(tool_root, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()

    cases = [
        ["--provider", "claude-cli", "--base-url", "http://h"],
        ["--provider", "claude-cli", "--api-key-env", "K"],
    ]

    for argv in cases:
        before = sorted(p.name for p in project.iterdir())
        rc, _messages, _out, _err = _call(argv, tool_root, project, capsys)
        after = sorted(p.name for p in project.iterdir())

        assert rc == 2, "argv=%r returned %r" % (argv, rc)
        assert after == before, "argv=%r wrote to the target directory" % (argv,)


def test_openai_compatible_requires_model_and_base_url(tool_root, tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()

    cases = [
        ["--provider", "openai-compatible", "--base-url", "http://h"],
        ["--provider", "openai-compatible", "--model", "m"],
    ]

    for argv in cases:
        before = sorted(p.name for p in project.iterdir())
        rc, _messages, _out, _err = _call(argv, tool_root, project, capsys)
        after = sorted(p.name for p in project.iterdir())

        assert rc == 2, "argv=%r returned %r" % (argv, rc)
        assert after == before, "argv=%r wrote to the target directory" % (argv,)


def test_provider_and_yes_flags_succeed_in_either_order_and_form(tool_root, tmp_path, capsys):
    env = {"OPENAI_API_KEY": "placeholder-not-a-real-key"}
    variants = [
        ["--provider", "openai", "--yes"],
        ["--yes", "--provider", "openai"],
        ["--provider=openai", "--yes"],
        ["--yes", "--provider=openai"],
    ]

    for i, flags in enumerate(variants):
        project = tmp_path / ("project%d" % i)
        project.mkdir()
        argv = list(flags) + [str(project)]
        rc, _messages, _out, err = _call(argv, tool_root, project, capsys, env=env)
        assert rc == 0, "argv=%r returned %r, stderr=%r" % (argv, rc, err)