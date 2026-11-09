import importlib.metadata
import os

import pytest

import hotdocs_init


LLM_ENDPOINT_SRC = '''
PROVIDERS = {
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4o",
    },
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_COMPATIBLE_API_KEY",
        "needs_base_url": True,
        "suggested_model": "",
    },
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.1:8b",
    },
}

LOG_PATH = "__LOG_PATH__"


def _log(name, kwargs):
    with open(LOG_PATH, "a") as f:
        f.write(name + " " + repr(kwargs) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"env": env, "probe_ollama": probe_ollama})
    return [
        {
            "provider": p,
            "available": True,
            "reason": None,
            "suggested_model": PROVIDERS[p]["suggested_model"],
            "api_key_env": PROVIDERS[p]["default_api_key_env"],
        }
        for p in PROVIDERS
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log(
        "check_connection",
        {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "timeout_seconds": timeout_seconds,
        },
    )
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required for " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log(
        "save_config",
        {
            "config_path": str(config_path),
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "timeout_seconds": timeout_seconds,
        },
    )
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    with open(config_path, "a") as f:
        f.write("[llm]\\nprovider = \\"" + provider + "\\"\\n")


def load_config(config_path=None):
    _log("load_config", {"config_path": str(config_path)})
    return None
'''


def snapshot(dir_path):
    entries = set()
    for root, _dirs, files in os.walk(dir_path):
        for name in files:
            full = os.path.join(root, name)
            entries.add(os.path.relpath(full, dir_path))
    return entries


def make_output_collector():
    messages = []

    def output_fn(msg=""):
        messages.append(str(msg))

    return output_fn, messages


def forbidden_input(prompt=""):
    raise AssertionError("input_fn should not be called for a usage error")


@pytest.fixture
def log_path(tmp_path_factory):
    log_dir = tmp_path_factory.mktemp("log")
    return log_dir / "calls.log"


@pytest.fixture
def tool_root(tmp_path_factory, log_path):
    root = tmp_path_factory.mktemp("tool_root")

    llm_dir = root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    source = LLM_ENDPOINT_SRC.replace("__LOG_PATH__", str(log_path).replace("\\", "\\\\"))
    (llm_dir / "llm_endpoint.py").write_text(source)

    slugify_dir = root / "examples" / "slugify" / "specs" / "product"
    slugify_dir.mkdir(parents=True)
    (slugify_dir / "slugs.md").write_text("# slugs\n")

    version = importlib.metadata.version("pytest")
    (root / "requirements.txt").write_text("pytest==" + version + "\n")

    return str(root)


@pytest.mark.parametrize(
    "argv",
    [
        ["--bogus"],
        ["--provider"],
        ["a", "b"],
        ["--provider=openai", "--model"],
    ],
    ids=["unknown-flag", "flag-no-value", "two-positionals", "model-no-value"],
)
def test_basic_usage_errors_exit_2_and_write_nothing(tool_root, tmp_path, argv):
    cwd_dir = tmp_path / "work"
    cwd_dir.mkdir()
    before = snapshot(cwd_dir)

    output_fn, _messages = make_output_collector()
    rc = hotdocs_init.main(
        argv,
        tool_root=tool_root,
        input_fn=forbidden_input,
        output_fn=output_fn,
        cwd=str(cwd_dir),
    )

    after = snapshot(cwd_dir)
    assert rc == 2
    assert before == after


def test_unknown_provider_exits_2_writes_nothing_and_lists_provider_keys(tool_root, tmp_path, capsys):
    cwd_dir = tmp_path / "work"
    cwd_dir.mkdir()
    before = snapshot(cwd_dir)

    output_fn, messages = make_output_collector()
    rc = hotdocs_init.main(
        ["--provider", "nope"],
        tool_root=tool_root,
        input_fn=forbidden_input,
        output_fn=output_fn,
        cwd=str(cwd_dir),
    )

    after = snapshot(cwd_dir)
    captured = capsys.readouterr()
    combined = "\n".join(messages) + captured.err + captured.out

    assert rc == 2
    assert before == after
    for key in ["openai", "claude-cli", "openai-compatible", "ollama"]:
        assert key in combined


@pytest.mark.parametrize("bad_api_key_env", ["sk-abc123", "9X"])
def test_invalid_api_key_env_name_exits_2_writes_nothing_and_is_never_echoed(
    tool_root, tmp_path, capsys, bad_api_key_env
):
    cwd_dir = tmp_path / "work"
    cwd_dir.mkdir()
    before = snapshot(cwd_dir)

    output_fn, messages = make_output_collector()
    rc = hotdocs_init.main(
        ["--provider", "openai", "--api-key-env", bad_api_key_env],
        tool_root=tool_root,
        input_fn=forbidden_input,
        output_fn=output_fn,
        cwd=str(cwd_dir),
    )

    after = snapshot(cwd_dir)
    captured = capsys.readouterr()
    combined = "\n".join(messages) + captured.err + captured.out

    assert rc == 2
    assert before == after
    assert bad_api_key_env not in combined


def test_claude_cli_rejects_base_url_and_api_key_env(tool_root, tmp_path):
    cwd1 = tmp_path / "c1"
    cwd1.mkdir()
    before1 = snapshot(cwd1)
    rc1 = hotdocs_init.main(
        ["--provider", "claude-cli", "--base-url", "http://h"],
        tool_root=tool_root,
        input_fn=forbidden_input,
        output_fn=lambda msg="": None,
        cwd=str(cwd1),
    )
    after1 = snapshot(cwd1)
    assert rc1 == 2
    assert before1 == after1

    cwd2 = tmp_path / "c2"
    cwd2.mkdir()
    before2 = snapshot(cwd2)
    rc2 = hotdocs_init.main(
        ["--provider", "claude-cli", "--api-key-env", "K"],
        tool_root=tool_root,
        input_fn=forbidden_input,
        output_fn=lambda msg="": None,
        cwd=str(cwd2),
    )
    after2 = snapshot(cwd2)
    assert rc2 == 2
    assert before2 == after2


def test_openai_compatible_requires_model_and_base_url(tool_root, tmp_path):
    cwd1 = tmp_path / "oc1"
    cwd1.mkdir()
    before1 = snapshot(cwd1)
    rc1 = hotdocs_init.main(
        ["--provider", "openai-compatible", "--base-url", "http://h"],
        tool_root=tool_root,
        input_fn=forbidden_input,
        output_fn=lambda msg="": None,
        cwd=str(cwd1),
    )
    after1 = snapshot(cwd1)
    assert rc1 == 2
    assert before1 == after1

    cwd2 = tmp_path / "oc2"
    cwd2.mkdir()
    before2 = snapshot(cwd2)
    rc2 = hotdocs_init.main(
        ["--provider", "openai-compatible", "--model", "m"],
        tool_root=tool_root,
        input_fn=forbidden_input,
        output_fn=lambda msg="": None,
        cwd=str(cwd2),
    )
    after2 = snapshot(cwd2)
    assert rc2 == 2
    assert before2 == after2


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda d: ["--provider", "openai", "--yes", d],
        lambda d: ["--yes", "--provider", "openai", d],
        lambda d: ["--provider=openai", "--yes", d],
        lambda d: ["--yes", "--provider=openai", d],
    ],
    ids=["order-a-space-form", "order-b-space-form", "order-a-eq-form", "order-b-eq-form"],
)
def test_yes_flag_succeeds_regardless_of_order_and_flag_form(tool_root, tmp_path, argv_builder):
    target_dir = tmp_path / "proj"
    target_dir.mkdir()
    argv = argv_builder(str(target_dir))

    output_fn, _messages = make_output_collector()
    rc = hotdocs_init.main(
        argv,
        tool_root=tool_root,
        input_fn=lambda prompt="": "y",
        output_fn=output_fn,
        cwd=str(tmp_path),
    )

    assert rc == 0