import json
import urllib.request

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir


# --- Scenario 1: the prefix counts only when it names a known provider ---


def test_ollama_prefix_and_bare_ollama_tag(clean_env):
    provider, model = llm_endpoint.parse_model("ollama:llama3.1:8b")
    assert provider == "ollama"
    assert model == "llama3.1:8b"

    provider, model = llm_endpoint.parse_model("llama3.1:8b")
    assert provider is None
    assert model == "llama3.1:8b"


def test_ollama_prefixed_identifier_resolves_to_ollama(clean_env):
    resolved = llm_endpoint.resolve_provider("ollama:llama3.1:8b", None)
    assert field(resolved, "provider") == "ollama"
    assert field(resolved, "model") == "llama3.1:8b"


# --- Scenario 2: bare name uses configured provider, prefix uses its defaults ---


def _write_config(tmp_path):
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    path = config_dir / "hotdocs.toml"
    path.write_text(
        "[llm]\n"
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'api_key_env = "MY_KEY"\n'
        "timeout_seconds = 400\n",
        encoding="utf-8",
    )
    return path


def test_bare_name_uses_configured_provider_and_prefix_uses_defaults(
    tmp_path, clean_env
):
    path = _write_config(tmp_path)
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "provider") == "openai"

    bare = llm_endpoint.resolve_provider("gpt-6-astra", config)
    assert field(bare, "provider") == "openai"
    assert field(bare, "model") == "gpt-6-astra"
    assert field(bare, "api_key_env") == "MY_KEY"
    assert field(bare, "timeout_seconds") == 400

    gem = llm_endpoint.resolve_provider("gemini:gemini-4-argon", config)
    assert field(gem, "provider") == "gemini"
    assert field(gem, "model") == "gemini-4-argon"
    assert field(gem, "base_url") == "https://generativelanguage.googleapis.com"
    assert field(gem, "api_key_env") == "GEMINI_API_KEY"
    assert field(gem, "timeout_seconds") == llm_endpoint.DEFAULT_TIMEOUT_SECONDS
    assert field(gem, "timeout_seconds") == 600
    assert field(gem, "api_key_env") != "MY_KEY"


# --- Scenario 3: provider receives the stripped model; response keeps the identifier ---


class _FakeReply:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args, **kwargs):
        return self._body


def _request_body(request):
    data = getattr(request, "data", None)
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    try:
        return json.loads(data)
    except (TypeError, ValueError):
        return None


def test_provider_gets_stripped_model_but_response_keeps_identifier(
    clean_env, monkeypatch
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    recorded = []

    def recorder(request, *args, **kwargs):
        recorded.append(request)
        return _FakeReply(
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-5-5",
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", recorder)

    response = llm_endpoint.complete("hi", "anthropic:claude-sonnet-5-5")

    bodies = [b for b in (_request_body(r) for r in recorded) if isinstance(b, dict)]
    model_bodies = [b for b in bodies if "model" in b]
    assert model_bodies, "no request with a JSON body naming a model was recorded"
    assert model_bodies[-1]["model"] == "claude-sonnet-5-5"

    assert field(response, "model_call_error") is None
    assert field(response, "model") == "anthropic:claude-sonnet-5-5"


def test_injected_backend_is_passed_identifier_unchanged(tmp_path, clean_env):
    log_path = tmp_path / "backend_calls.jsonl"

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        return {
            "text": "ok",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    response = llm_endpoint.complete(
        "hi", "anthropic:claude-sonnet-5-5", backend=backend
    )

    lines = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["model"] == "anthropic:claude-sonnet-5-5"
    assert field(response, "model") == "anthropic:claude-sonnet-5-5"