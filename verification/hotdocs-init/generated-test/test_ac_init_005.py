# hotdocs-criterion: sha256:478d8bfe2a9a9a8c392d555647208f4fc7a1c463dcd1d744db1f0164957b94f9
import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


FAKE_BODY = '''
import json
import os
from pathlib import Path

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


def _log(name, **kw):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": kw}, default=str) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    result = []
    for name, info in PROVIDERS.items():
        available = name == "openai"
        result.append({
            "provider": name,
            "available": available,
            "reason": "available" if available else "not configured",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if CHECK_MODE == "raise":
        raise ValueError(CHECK_MESSAGE)
    if CHECK_MODE == "fail":
        return {"ok": False, "error": {"category": "auth", "message": "bad"}}
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider,
         model=model, base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if SAVE_ERROR is not None:
        raise ValueError(SAVE_ERROR)
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.is_file():
        skipping = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                skipping = stripped == "[llm]"
            if not skipping:
                kept.append(line)
    table = ["[llm]", "provider = " + json.dumps(provider), "model = " + json.dumps(model)]
    if base_url is not None:
        table.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        table.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        table.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        table.append("auth = " + json.dumps(auth))
    text = "\\n".join(kept + table) + "\\n"
    path.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path) if config_path is not None else None)
    if config_path is None:
        return None
    path = Path(config_path)
    if not path.is_file():
        return None
    values = {}
    in_llm = False
    found = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_llm = stripped == "[llm]"
            found = found or in_llm
            continue
        if in_llm and "=" in stripped:
            key, _, raw = stripped.partition("=")
            raw = raw.strip()
            try:
                values[key.strip()] = json.loads(raw)
            except ValueError:
                raise ValueError("invalid value for " + key.strip())
    if not found:
        return None
    return {
        "provider": values.get("provider"),
        "model": values.get("model"),
        "base_url": values.get("base_url"),
        "api_key_env": values.get("api_key_env"),
        "timeout_seconds": values.get("timeout_seconds"),
        "auth": values.get("auth"),
    }
'''


def make_tool_root(base, log_path, check_mode="ok", check_message="", save_error=None):
    tool_root = base / "toolroot"
    mod_dir = tool_root / "gen" / "llm-endpoint"
    mod_dir.mkdir(parents=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "CHECK_MODE = " + repr(check_mode) + "\n"
        + "CHECK_MESSAGE = " + repr(check_message) + "\n"
        + "SAVE_ERROR = " + repr(save_error) + "\n"
        + FAKE_BODY
    )
    (mod_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")
    ex = tool_root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True)
    (ex / "slugs.md").write_text("# Slugs\n\nA small example.\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool_root


def setup(tmp_path, name, **kw):
    base = tmp_path / name
    base.mkdir()
    logs = base / "logs"
    logs.mkdir()
    log_path = logs / "llm_endpoint.log"
    tool_root = make_tool_root(base, log_path, **kw)
    project = base / "project"
    project.mkdir()
    return tool_root, project, log_path


def read_log(log_path):
    if not Path(log_path).is_file():
        return []
    entries = []
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def calls(log_path, name):
    return [e["args"] for e in read_log(log_path) if e["call"] == name]


def base_env():
    return {"PATH": os.environ.get("PATH", "")}


class Recorder:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))

    def text(self):
        return "\n".join(self.lines)


def no_input(prompts):
    def fn(prompt=""):
        prompts.append(prompt)
        raise AssertionError("init asked a question: " + repr(prompt))
    return fn


def scripted_input(prompts, save_answer):
    seen = {}
    fallbacks = ["", "openai", "1"]

    def fn(prompt=""):
        prompts.append(prompt)
        assert len(prompts) < 60, "too many questions: " + repr(prompts[-5:])
        if "Save anyway?" in prompt:
            return save_answer
        count = seen.get(prompt, 0)
        seen[prompt] = count + 1
        if count >= len(fallbacks):
            raise AssertionError("question repeated too often: " + repr(prompt))
        return fallbacks[count]
    return fn


def run_init(argv, tool_root, project, input_fn, out):
    return hotdocs_init.run(
        argv,
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=out,
        env=base_env(),
        cwd=project,
    )


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_ok_connection_saves_with_flags_and_asks_nothing(tmp_path, capsys):
    tool_root, project, log_path = setup(tmp_path, "s1", check_mode="ok")
    out = Recorder()
    prompts = []
    run_init(
        [str(project), "--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root, project, no_input(prompts), out,
    )
    captured = capsys.readouterr()
    printed = out.text() + "\n" + captured.out + "\n" + captured.err
    assert "connection ok" in printed
    assert prompts == []
    saves = calls(log_path, "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert same_path(s["config_path"], project / "hotdocs.toml")
    assert s["provider"] == "openai"
    assert s["model"] == "m"
    assert s["api_key_env"] == "MY_KEY"
    assert s["base_url"] is None
    assert s["timeout_seconds"] is None
    assert s["auth"] is None


def test_failed_connection_interactive_save_anyway(tmp_path, capsys):
    # First run: answer "n" -> nothing saved.
    tool_root1, project1, log1 = setup(tmp_path, "s2a", check_mode="fail")
    out1 = Recorder()
    prompts1 = []
    run_init([str(project1)], tool_root1, project1, scripted_input(prompts1, "n"), out1)
    cap1 = capsys.readouterr()
    printed1 = out1.text() + "\n" + cap1.out + "\n" + cap1.err
    assert "connection failed: auth: bad" in printed1
    assert "Save anyway? [y/N] " in prompts1
    assert calls(log1, "save_config") == []

    # Second run, fresh directory and tool root: answer "y" -> saved.
    tool_root2, project2, log2 = setup(tmp_path, "s2b", check_mode="fail")
    out2 = Recorder()
    prompts2 = []
    run_init([str(project2)], tool_root2, project2, scripted_input(prompts2, "y"), out2)
    cap2 = capsys.readouterr()
    printed2 = out2.text() + "\n" + cap2.out + "\n" + cap2.err
    assert "connection failed: auth: bad" in printed2
    assert "Save anyway? [y/N] " in prompts2
    saves = calls(log2, "save_config")
    assert len(saves) == 1
    assert same_path(saves[0]["config_path"], project2 / "hotdocs.toml")


def test_value_error_from_check_connection_is_invalid(tmp_path, capsys):
    tool_root, project, log_path = setup(
        tmp_path, "s3", check_mode="raise", check_message="no base_url"
    )
    out = Recorder()
    prompts = []
    run_init(
        [str(project), "--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"],
        tool_root, project, no_input(prompts), out,
    )
    captured = capsys.readouterr()
    printed = out.text() + "\n" + captured.out + "\n" + captured.err
    assert "connection failed: invalid: no base_url" in printed
    assert len(calls(log_path, "check_connection")) >= 1


def test_save_error_goes_to_stderr_and_does_not_change_exit_code(tmp_path, capsys):
    argv_tail = ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"]

    tool_root_b, project_b, log_b = setup(tmp_path, "s4base", check_mode="ok")
    out_b = Recorder()
    code_baseline = run_init(
        [str(project_b)] + argv_tail, tool_root_b, project_b, no_input([]), out_b
    )
    capsys.readouterr()
    assert len(calls(log_b, "save_config")) == 1

    tool_root, project, log_path = setup(
        tmp_path, "s4", check_mode="ok", save_error="nope"
    )
    out = Recorder()
    code = run_init(
        [str(project)] + argv_tail, tool_root, project, no_input([]), out
    )
    captured = capsys.readouterr()
    assert "could not save: nope" in captured.err
    assert len(calls(log_path, "save_config")) == 1
    assert code == code_baseline


def test_no_test_never_calls_check_connection(tmp_path, capsys):
    tool_root, project, log_path = setup(tmp_path, "s5", check_mode="ok")
    out = Recorder()
    run_init(
        [str(project), "--provider", "openai", "--model", "m",
         "--api-key-env", "MY_KEY", "--no-test"],
        tool_root, project, no_input([]), out,
    )
    capsys.readouterr()
    assert calls(log_path, "check_connection") == []


def test_auth_reaches_check_connection_and_save_config(tmp_path, capsys):
    tool_root, project, log_path = setup(tmp_path, "s6", check_mode="ok")
    out = Recorder()
    prompts = []
    run_init(
        [str(project), "--provider", "claude-cli", "--model", "m",
         "--auth", "login", "--yes"],
        tool_root, project, no_input(prompts), out,
    )
    capsys.readouterr()
    checks = calls(log_path, "check_connection")
    assert len(checks) >= 1
    assert checks[-1]["auth"] == "login"
    assert checks[-1]["provider"] == "claude-cli"
    saves = calls(log_path, "save_config")
    assert len(saves) == 1
    s = saves[0]
    assert same_path(s["config_path"], project / "hotdocs.toml")
    assert s["provider"] == "claude-cli"
    assert s["model"] == "m"
    assert s["auth"] == "login"
    assert s["base_url"] is None
    assert s["api_key_env"] is None
    assert s["timeout_seconds"] is None