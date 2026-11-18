# hotdocs-criterion: sha256:929bb7b123f7449a6b62b73f0e119e354cb61948d95fde0a5d0bd1bcf40de2ed
import importlib.metadata
import json
import os
import time
from pathlib import Path

import hotdocs_init


FAKE_LLM_ENDPOINT_BODY = '''
import json as _json
from pathlib import Path as _Path

PROVIDERS = {
    "claude-cli": {"default_base_url": None, "default_api_key_env": None,
                   "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "anthropic": {"default_base_url": "https://api.anthropic.com",
                  "default_api_key_env": "ANTHROPIC_API_KEY",
                  "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "openai": {"default_base_url": "https://api.openai.com/v1",
               "default_api_key_env": "OPENAI_API_KEY",
               "needs_base_url": False, "suggested_model": "gpt-6-astra"},
    "openai-compatible": {"default_base_url": None, "default_api_key_env": None,
                          "needs_base_url": True, "suggested_model": ""},
    "gemini": {"default_base_url": "https://generativelanguage.googleapis.com",
               "default_api_key_env": "GEMINI_API_KEY",
               "needs_base_url": False, "suggested_model": "gemini-4-argon"},
    "ollama": {"default_base_url": "http://localhost:11434", "default_api_key_env": None,
               "needs_base_url": False, "suggested_model": "llama3.2"},
}


def _log(name, **kwargs):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({"call": name, "args": {k: repr(v) for k, v in kwargs.items()}}) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env=env is not None, probe_ollama=probe_ollama)
    out = []
    for name, info in PROVIDERS.items():
        out.append({
            "provider": name,
            "available": name == "ollama",
            "reason": "fake",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _strip_llm(text):
    kept = []
    in_llm = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_llm = s == "[llm]"
            if in_llm:
                continue
        if not in_llm:
            kept.append(line)
    return "\\n".join(kept).strip()


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model:
        raise ValueError("model required")
    p = _Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text(encoding="utf-8") if p.exists() else ""
    rest = _strip_llm(existing)
    lines = ["[llm]", "provider = " + _json.dumps(provider), "model = " + _json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + _json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + _json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + _json.dumps(auth))
    text = (rest + "\\n\\n" if rest else "") + "\\n".join(lines) + "\\n"
    p.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    if config_path is None:
        config_path = _Path.cwd() / "hotdocs.toml"
    p = _Path(config_path)
    if not p.exists():
        return None
    try:
        import tomllib
    except ImportError:
        return None
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("invalid config") from exc
    llm = data.get("llm")
    if llm is None:
        return None
    return {
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "base_url": llm.get("base_url"),
        "api_key_env": llm.get("api_key_env"),
        "timeout_seconds": llm.get("timeout_seconds"),
        "auth": llm.get("auth"),
    }
'''


def make_tool_root(tmp_path):
    tool_root = tmp_path / "tool"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_endpoint_calls.log"

    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    (llm_dir / "llm_endpoint.py").write_text(
        "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY,
        encoding="utf-8",
    )

    ab_dir = tool_root / "gen" / "a-b"
    ab_dir.mkdir(parents=True)
    (ab_dir / "a_b.py").write_text("def hello():\n    return 'a-b'\n", encoding="utf-8")

    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nExample product spec.\n", encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool_root


def snapshot(root):
    root = Path(root)
    entries = {}
    st = os.stat(root)
    entries["."] = ("dir", None, st.st_mtime_ns)
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            p = Path(dirpath) / d
            entries[str(p.relative_to(root))] = ("dir", None, os.stat(p).st_mtime_ns)
        for f in filenames:
            p = Path(dirpath) / f
            entries[str(p.relative_to(root))] = (
                "file", p.read_bytes(), os.stat(p).st_mtime_ns
            )
    return entries


def make_input_fn():
    calls = {"n": 0}

    def input_fn(prompt=""):
        calls["n"] += 1
        if calls["n"] > 100:
            raise EOFError("too many prompts")
        return ""

    return input_fn


def run_init(target, tool_root, outputs):
    argv = [str(target), "--yes", "--no-test", "--provider", "ollama", "--model", "llama3.2"]
    env = {"PATH": os.environ.get("PATH", "")}
    return hotdocs_init.main(
        argv,
        tool_root=tool_root,
        input_fn=make_input_fn(),
        output_fn=lambda *a, **k: outputs.append(" ".join(str(x) for x in a)),
        env=env,
        cwd=str(target),
    )


def test_tool_version_constant():
    assert hotdocs_init.TOOL_VERSION == "0.1.0"


def test_init_writes_marker_and_empty_gen_then_leaves_marker_alone(tmp_path):
    tool_root = make_tool_root(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    outputs = []
    rc = run_init(target, tool_root, outputs)
    assert rc in (0, 3), outputs

    gen = target / "gen"
    assert gen.is_dir()
    assert list(gen.iterdir()) == []
    assert not (target / "pipeline").exists()

    others = [p.name for p in target.iterdir() if p.name not in ("gen", ".hotdocs-tool.json")]
    assert others, "expected other skeleton entries beside gen/"

    marker = target / ".hotdocs-tool.json"
    assert marker.is_file()
    assert json.loads(marker.read_text(encoding="utf-8")) == {"tool_version": "0.1.0"}

    before_bytes = marker.read_bytes()
    before_mtime = os.stat(marker).st_mtime_ns

    time.sleep(0.05)
    outputs2 = []
    rc2 = run_init(target, tool_root, outputs2)
    assert rc2 in (0, 3), outputs2

    assert marker.read_bytes() == before_bytes
    assert os.stat(marker).st_mtime_ns == before_mtime


def test_init_refuses_on_gen_collision_and_writes_nothing(tmp_path, capsys):
    tool_root = make_tool_root(tmp_path)
    target = tmp_path / "project"
    (target / "gen" / "a-b").mkdir(parents=True)
    (target / "gen" / "mine").mkdir(parents=True)

    target_before = snapshot(target)
    tool_before = snapshot(tool_root)

    outputs = []
    rc = run_init(target, tool_root, outputs)
    captured = capsys.readouterr()
    text = captured.err + captured.out + "\n".join(outputs)

    assert rc == 1
    assert "gen/a-b" in text
    assert "gen/mine" not in text

    assert snapshot(target) == target_before
    assert snapshot(tool_root) == tool_before


def test_init_refuses_on_tool_root_and_writes_nothing(tmp_path, capsys):
    tool_root = make_tool_root(tmp_path)
    tool_before = snapshot(tool_root)

    outputs = []
    rc = run_init(tool_root, tool_root, outputs)
    capsys.readouterr()

    assert rc == 1
    assert snapshot(tool_root) == tool_before