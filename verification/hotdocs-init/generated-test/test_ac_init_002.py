# hotdocs-criterion: sha256:1837814ee4d26ff8a60edc2f4f92b699b56053824d1e7838406021423c79d850
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


FAKE_ENDPOINT_BODY = '''
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
    "ollama": {"default_base_url": "http://localhost:11434",
               "default_api_key_env": None,
               "needs_base_url": False, "suggested_model": "llama3.2"},
}


def _log(name):
    p = _Path(LOG_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(name + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
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
    _log("check_connection")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    p = _Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"provider": provider, "model": model, "base_url": base_url,
            "api_key_env": api_key_env, "timeout_seconds": timeout_seconds,
            "auth": auth}
    lines = ["[llm]"]
    for k, v in data.items():
        if v is not None:
            lines.append(k + " = " + _json.dumps(v))
    p.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config")
    if config_path is None:
        config_path = _Path.cwd() / "hotdocs.toml"
    p = _Path(config_path)
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8")
    if "[llm]" not in text:
        return None
    result = {"provider": None, "model": None, "base_url": None,
              "api_key_env": None, "timeout_seconds": None, "auth": None}
    in_llm = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_llm = s == "[llm]"
            continue
        if in_llm and "=" in s:
            k, v = s.split("=", 1)
            k = k.strip()
            if k in result:
                result[k] = _json.loads(v.strip())
    return result
'''


def make_tool_root(tmp_path):
    tool = tmp_path / "tool"
    log_path = tmp_path / "logs" / "llm.log"
    ep = tool / "gen" / "llm-endpoint"
    ep.mkdir(parents=True)
    (ep / "llm_endpoint.py").write_text(
        "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_ENDPOINT_BODY,
        encoding="utf-8",
    )
    ab = tool / "gen" / "a-b"
    ab.mkdir(parents=True)
    (ab / "a_b.py").write_text("VALUE = 1\n", encoding="utf-8")
    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n", encoding="utf-8")
    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool, log_path


def snapshot(root):
    root = Path(root)
    snap = {".": ("dir", None, os.stat(root).st_mtime_ns)}
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            p = Path(dirpath) / d
            snap[str(p.relative_to(root))] = ("dir", None, os.stat(p).st_mtime_ns)
        for f in filenames:
            p = Path(dirpath) / f
            snap[str(p.relative_to(root))] = (
                "file", p.read_bytes(), os.stat(p).st_mtime_ns)
    return snap


def make_input():
    calls = {"n": 0}

    def input_fn(prompt):
        calls["n"] += 1
        if calls["n"] > 50:
            raise RuntimeError("too many prompts")
        return ""
    return input_fn


def do_run(target, tool, outputs):
    env = {"PATH": os.environ.get("PATH", "")}
    return hotdocs_init.run(
        [str(target), "--yes", "--no-test", "--provider", "ollama",
         "--model", "llama3.2"],
        tool_root=tool,
        input_fn=make_input(),
        output_fn=lambda *a, **k: outputs.append(" ".join(str(x) for x in a)),
        env=env,
        cwd=str(target),
    )


def test_init_writes_empty_gen_and_tool_json(tmp_path):
    tool, _ = make_tool_root(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    outputs = []
    code = do_run(target, tool, outputs)
    assert code in (0, 3)

    gen = target / "gen"
    assert gen.is_dir()
    assert list(gen.iterdir()) == []
    others = [p.name for p in target.iterdir()
              if p.name not in ("gen", ".hotdocs-tool.json")]
    assert others, "expected R-INIT-001's other entries beside gen/"
    assert not (target / "pipeline").exists()
    assert not (gen / "pipeline").exists()

    tool_json = target / ".hotdocs-tool.json"
    assert json.loads(tool_json.read_text(encoding="utf-8")) == {"tool_version": "0.1.0"}

    # Second run: file left byte for byte, mtime untouched.
    past = 1_000_000_000_000_000_000
    os.utime(tool_json, ns=(past, past))
    before_bytes = tool_json.read_bytes()
    before_mtime = os.stat(tool_json).st_mtime_ns
    outputs2 = []
    code2 = do_run(target, tool, outputs2)
    assert code2 in (0, 3)
    assert tool_json.read_bytes() == before_bytes
    assert os.stat(tool_json).st_mtime_ns == before_mtime


def test_init_refuses_shadowing_component(tmp_path, capsys):
    tool, log_path = make_tool_root(tmp_path)
    target = tmp_path / "proj"
    (target / "gen" / "a-b").mkdir(parents=True)
    (target / "gen" / "mine").mkdir(parents=True)
    before_target = snapshot(target)
    before_tool = snapshot(tool)

    outputs = []
    code = do_run(target, tool, outputs)
    captured = capsys.readouterr()
    text = captured.err + captured.out + "\n".join(outputs)

    assert code == 1
    assert "gen/a-b" in text
    assert "gen/mine" not in text
    assert snapshot(target) == before_target
    assert snapshot(tool) == before_tool
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""


def test_init_refuses_tool_root_itself(tmp_path, capsys):
    tool, log_path = make_tool_root(tmp_path)
    before_tool = snapshot(tool)

    outputs = []
    code = do_run(tool, tool, outputs)
    capsys.readouterr()

    assert code == 1
    assert snapshot(tool) == before_tool
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""