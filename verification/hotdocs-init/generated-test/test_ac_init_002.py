# hotdocs-criterion: sha256:b743b5e6ddc6cdf98aca97d61a3d2ce534f7f51be8bfde0ffefa2033a1531aa4
import importlib.metadata
import json
import os
import time
from pathlib import Path

import hotdocs_init


FAKE_LLM_ENDPOINT_BODY = '''
import json
import os
from pathlib import Path


def _log(name, **kwargs):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": {k: repr(v) for k, v in kwargs.items()}}) + "\\n")


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

_KEYS = ("provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env=env, probe_ollama=probe_ollama)
    out = []
    for name, info in PROVIDERS.items():
        out.append({
            "provider": name,
            "available": name == "ollama",
            "reason": "fake detection",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model:
        raise ValueError("model required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.is_file():
        in_llm = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_llm = stripped == "[llm]"
                if in_llm:
                    continue
            if not in_llm:
                kept.append(line)
    lines = list(kept)
    if lines and lines[-1].strip():
        lines.append("")
    lines.append("[llm]")
    values = {"provider": provider, "model": model, "base_url": base_url,
              "api_key_env": api_key_env, "timeout_seconds": timeout_seconds,
              "auth": auth}
    for key in _KEYS:
        if values[key] is not None:
            lines.append(key + " = " + json.dumps(values[key]))
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.is_file():
        return None
    in_llm = False
    found = False
    result = {k: None for k in _KEYS}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = stripped == "[llm]"
            found = found or in_llm
            continue
        if in_llm and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            if key in result:
                try:
                    result[key] = json.loads(value.strip())
                except ValueError:
                    raise ValueError("invalid value for " + key)
    if not found:
        return None
    return result
'''


def make_tool_root(tmp_path):
    tool_root = tmp_path / "tool"
    log_path = tmp_path / "logs" / "llm_endpoint_calls.log"
    log_path.parent.mkdir(parents=True)

    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    (llm_dir / "llm_endpoint.py").write_text(
        "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY,
        encoding="utf-8",
    )

    ab_dir = tool_root / "gen" / "a-b"
    ab_dir.mkdir(parents=True)
    (ab_dir / "a_b.py").write_text(
        "def main(argv=None):\n    return 0\n", encoding="utf-8"
    )

    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake product spec.\n", encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool_root, log_path


def snapshot(root):
    root = Path(root)
    result = {}
    st = os.stat(root)
    result["."] = ("dir", None, st.st_mtime_ns)
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            p = Path(dirpath) / d
            result[str(p.relative_to(root))] = ("dir", None, os.stat(p).st_mtime_ns)
        for f in filenames:
            p = Path(dirpath) / f
            result[str(p.relative_to(root))] = (
                "file", p.read_bytes(), os.stat(p).st_mtime_ns
            )
    return result


def log_lines(log_path):
    if not log_path.exists():
        return []
    return [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def run_init(argv, tool_root, tmp_path):
    outputs = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        outputs.append(str(prompt))
        return ""

    env = {"PATH": os.environ.get("PATH", "")}
    rc = hotdocs_init.main(
        argv,
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=str(tmp_path),
    )
    return rc, outputs


def init_args(target):
    return [
        str(target), "--yes", "--no-test",
        "--provider", "ollama", "--model", "llama3.2",
    ]


def test_init_writes_empty_gen_and_tool_json_and_is_idempotent(tmp_path):
    tool_root, _log = make_tool_root(tmp_path)
    target = tmp_path / "project"
    target.mkdir()

    rc, _ = run_init(init_args(target), tool_root, tmp_path)
    assert rc in (0, 3)

    gen = target / "gen"
    assert gen.is_dir()
    assert list(gen.iterdir()) == []

    others = [p.name for p in target.iterdir()
              if p.name not in ("gen", ".hotdocs-tool.json")]
    assert others, "expected R-INIT-001's other entries beside gen/"

    assert not (target / "pipeline").exists()

    tool_json = target / ".hotdocs-tool.json"
    assert tool_json.is_file()
    assert json.loads(tool_json.read_text(encoding="utf-8")) == {"tool_version": "0.1.0"}

    before_bytes = tool_json.read_bytes()
    before_mtime = os.stat(tool_json).st_mtime_ns

    time.sleep(0.1)
    rc2, _ = run_init(init_args(target), tool_root, tmp_path)
    assert rc2 in (0, 3)

    assert tool_json.read_bytes() == before_bytes
    assert os.stat(tool_json).st_mtime_ns == before_mtime


def test_init_refuses_shadowing_component_and_writes_nothing(tmp_path, capsys):
    tool_root, log_path = make_tool_root(tmp_path)
    target = tmp_path / "project"
    (target / "gen" / "a-b").mkdir(parents=True)
    (target / "gen" / "mine").mkdir(parents=True)

    target_before = snapshot(target)
    tool_before = snapshot(tool_root)

    rc, outputs = run_init(init_args(target), tool_root, tmp_path)
    captured = capsys.readouterr()
    text = captured.err + "\n" + captured.out + "\n" + "\n".join(outputs)

    assert rc == 1
    assert "gen/a-b" in text
    assert "gen/mine" not in text

    assert snapshot(target) == target_before
    assert snapshot(tool_root) == tool_before
    assert log_lines(log_path) == []


def test_init_refuses_tool_root_itself_and_writes_nothing(tmp_path):
    tool_root, log_path = make_tool_root(tmp_path)

    tool_before = snapshot(tool_root)

    rc, _ = run_init(init_args(tool_root), tool_root, tmp_path)

    assert rc == 1
    assert snapshot(tool_root) == tool_before
    assert log_lines(log_path) == []