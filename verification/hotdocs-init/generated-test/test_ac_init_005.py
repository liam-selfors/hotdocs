# hotdocs-criterion: sha256:b6e15883f0d458770b6770ad2551a6c9d13f473900478f194e029e3826700083
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


FAKE_BODY = '''

def _log(fn, data):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"fn": fn, "data": data}, default=str) + "\\n")


PROVIDERS = {
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "anthropic": {
        "default_base_url": "https://api.anthropic.com",
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai": {
        "default_base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-6-astra",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
    "gemini": {
        "default_base_url": "https://generativelanguage.googleapis.com",
        "default_api_key_env": "GEMINI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gemini-4-argon",
    },
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.2",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"env_given": env is not None, "probe_ollama": probe_ollama})
    out = []
    for name, info in PROVIDERS.items():
        available = name == "openai"
        out.append({
            "provider": name,
            "available": available,
            "reason": "fake available" if available else "fake unavailable",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    })
    if CHECK_MODE == "raise":
        raise ValueError("no base_url")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("missing base_url")
    if CHECK_MODE == "fail":
        return {"ok": False, "error": {"category": "auth", "message": "bad"}}
    return {"ok": True, "error": None}


def _q(value):
    return json.dumps(value)


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config", {
        "config_path": str(config_path),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "timeout_seconds": timeout_seconds,
        "auth": auth,
    })
    if SAVE_MODE == "raise":
        raise ValueError("nope")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[llm]", "provider = " + _q(provider), "model = " + _q(model)]
    if base_url is not None:
        lines.append("base_url = " + _q(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + _q(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + _q(auth))
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", {"config_path": None if config_path is None else str(config_path)})
    path = Path(config_path) if config_path is not None else Path.cwd() / "hotdocs.toml"
    if not path.is_file():
        return None
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("invalid config: " + str(exc))
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


def make_tool_root(base, check_mode, save_mode):
    tool_root = base / "tool"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_endpoint_calls.jsonl"

    mod_dir = tool_root / "gen" / "llm-endpoint"
    mod_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "from pathlib import Path\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "CHECK_MODE = " + repr(check_mode) + "\n"
        "SAVE_MODE = " + repr(save_mode) + "\n"
        + FAKE_BODY
    )
    (mod_dir / "llm_endpoint.py").write_text(src, encoding="utf-8")

    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True, exist_ok=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake example product spec.\n", encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (tool_root / "pyproject.toml").write_text(
        "[project]\n" + "name = " + repr("hotdocs").replace("'", '"') + "\n"
        + "version = " + repr("9.8.7a1").replace("'", '"') + "\n",
        encoding="utf-8",
    )
    return tool_root, log_path


def read_log(log_path):
    if not log_path.is_file():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def calls(entries, fn):
    return [e["data"] for e in entries if e["fn"] == fn]


def run_init(base, capsys, argv_extra, check_mode="ok", save_mode="ok", save_answer=""):
    base.mkdir(parents=True, exist_ok=True)
    tool_root, log_path = make_tool_root(base, check_mode, save_mode)
    proj = base / "proj"
    proj.mkdir(parents=True, exist_ok=True)

    asked = []
    out = []

    def input_fn(question=""):
        asked.append(question)
        if len(asked) > 60:
            raise EOFError("too many questions")
        if "Save anyway?" in str(question):
            return save_answer
        return ""

    def output_fn(*args, **kwargs):
        out.append(" ".join(str(a) for a in args))

    capsys.readouterr()
    code = hotdocs_init.run(
        [str(proj)] + list(argv_extra),
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env={"PATH": os.environ.get("PATH", "")},
        cwd=str(proj),
    )
    captured = capsys.readouterr()
    return {
        "code": code,
        "out": "\n".join(out) + "\n" + captured.out,
        "err": captured.err,
        "asked": asked,
        "log": read_log(log_path),
        "proj": proj,
    }


def printed(result, text):
    return text in result["out"] or text in result["err"]


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_connection_ok_saves_with_only_given_keywords_and_asks_nothing(tmp_path, capsys):
    r = run_init(
        tmp_path / "s1", capsys,
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        check_mode="ok",
    )
    assert printed(r, "connection ok"), r
    assert calls(r["log"], "check_connection"), r["log"]
    saves = calls(r["log"], "save_config")
    assert len(saves) == 1, saves
    s = saves[0]
    assert same_path(s["config_path"], r["proj"] / "hotdocs.toml")
    assert s["provider"] == "openai"
    assert s["model"] == "m"
    assert s["api_key_env"] == "MY_KEY"
    assert s["base_url"] is None
    assert s["timeout_seconds"] is None
    assert s["auth"] is None
    assert r["asked"] == []


def test_connection_failure_interactive_save_anyway_n_then_y(tmp_path, capsys):
    r_no = run_init(tmp_path / "s2n", capsys, [], check_mode="fail", save_answer="n")
    assert printed(r_no, "connection failed: auth: bad"), r_no
    assert "Save anyway? [y/N] " in r_no["asked"], r_no["asked"]
    assert calls(r_no["log"], "check_connection")
    assert calls(r_no["log"], "save_config") == []

    r_yes = run_init(tmp_path / "s2y", capsys, [], check_mode="fail", save_answer="y")
    assert printed(r_yes, "connection failed: auth: bad"), r_yes
    assert "Save anyway? [y/N] " in r_yes["asked"], r_yes["asked"]
    saves = calls(r_yes["log"], "save_config")
    assert len(saves) == 1, saves
    assert same_path(saves[0]["config_path"], r_yes["proj"] / "hotdocs.toml")


def test_check_connection_value_error_is_printed_as_invalid(tmp_path, capsys):
    r = run_init(
        tmp_path / "s3", capsys,
        ["--provider", "openai", "--model", "m"],
        check_mode="raise",
    )
    assert calls(r["log"], "check_connection")
    assert printed(r, "connection failed: invalid: no base_url"), r


def test_save_config_value_error_goes_to_stderr_and_exit_code_unchanged(tmp_path, capsys):
    argv = ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"]
    baseline = run_init(tmp_path / "s4ok", capsys, argv, check_mode="ok", save_mode="ok")
    assert len(calls(baseline["log"], "save_config")) == 1

    r = run_init(tmp_path / "s4bad", capsys, argv, check_mode="ok", save_mode="raise")
    assert len(calls(r["log"], "save_config")) == 1
    assert "could not save: nope" in r["err"], r["err"]
    assert r["code"] == baseline["code"], (r["code"], baseline["code"])


def test_no_test_never_calls_check_connection(tmp_path, capsys):
    r = run_init(
        tmp_path / "s5", capsys,
        ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY", "--no-test"],
        check_mode="ok",
    )
    assert calls(r["log"], "save_config"), r["log"]
    assert calls(r["log"], "check_connection") == []


def test_auth_flag_reaches_check_connection_and_save_config(tmp_path, capsys):
    r = run_init(
        tmp_path / "s6", capsys,
        ["--provider", "claude-cli", "--model", "m", "--auth", "login", "--yes"],
        check_mode="ok",
    )
    checks = calls(r["log"], "check_connection")
    assert checks, r["log"]
    assert checks[-1]["auth"] == "login"
    assert checks[-1]["provider"] == "claude-cli"
    saves = calls(r["log"], "save_config")
    assert len(saves) == 1, saves
    s = saves[0]
    assert same_path(s["config_path"], r["proj"] / "hotdocs.toml")
    assert s["provider"] == "claude-cli"
    assert s["model"] == "m"
    assert s["auth"] == "login"
    assert s["base_url"] is None
    assert s["api_key_env"] is None
    assert s["timeout_seconds"] is None