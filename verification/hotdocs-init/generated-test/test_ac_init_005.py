import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


FAKE_LLM_ENDPOINT = r'''
import functools
import json
from pathlib import Path

_LOG_PATH = __LOG_PATH__
_CONN_MODE = __CONN_MODE__
_SAVE_MODE = __SAVE_MODE__


def _record(name, args, kwargs):
    entry = {"fn": name, "args": list(args), "kwargs": dict(kwargs)}
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")


def _logged(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        _record(fn.__name__, args, kwargs)
        return fn(*args, **kwargs)
    return wrapper


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
    out = []
    for name, info in PROVIDERS.items():
        available = name == "openai"
        out.append({
            "provider": name,
            "available": available,
            "reason": "configured" if available else "not configured",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    if _CONN_MODE == "ok":
        return {"ok": True, "error": None}
    if _CONN_MODE == "auth":
        return {"ok": False, "error": {"category": "auth", "message": "bad"}}
    if _CONN_MODE == "valueerror":
        raise ValueError("no base_url")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    if _SAVE_MODE == "raise":
        raise ValueError("nope")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[llm]", 'provider = "%s"' % provider, 'model = "%s"' % model]
    if base_url is not None:
        lines.append('base_url = "%s"' % base_url)
    if api_key_env is not None:
        lines.append('api_key_env = "%s"' % api_key_env)
    if timeout_seconds is not None:
        lines.append("timeout_seconds = %d" % int(timeout_seconds))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config(config_path=None):
    if config_path is None:
        return None
    path = Path(config_path)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if "[llm]" not in text:
        return None
    result = {"provider": None, "model": None, "base_url": None,
              "api_key_env": None, "timeout_seconds": None}
    in_llm = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            in_llm = line == "[llm]"
            continue
        if not in_llm or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"')
        if key in result:
            result[key] = int(value) if key == "timeout_seconds" else value
    return result


detect_providers = _logged(detect_providers)
check_connection = _logged(check_connection)
save_config = _logged(save_config)
load_config = _logged(load_config)
'''


def _make_fixture(base, conn_mode="ok", save_mode="ok"):
    base = Path(base)
    tool = base / "tool"
    proj = base / "proj"
    logdir = base / "logs"
    for d in (tool, proj, logdir):
        d.mkdir(parents=True, exist_ok=True)
    log_path = logdir / "llm_endpoint_calls.jsonl"

    gen_dir = tool / "gen" / "llm-endpoint"
    gen_dir.mkdir(parents=True, exist_ok=True)
    code = (
        FAKE_LLM_ENDPOINT
        .replace("__LOG_PATH__", repr(str(log_path)))
        .replace("__CONN_MODE__", repr(conn_mode))
        .replace("__SAVE_MODE__", repr(save_mode))
    )
    (gen_dir / "llm_endpoint.py").write_text(code, encoding="utf-8")

    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True, exist_ok=True)
    (slugs / "slugs.md").write_text(
        "---\nid: P-SLUGS\ntitle: Slugs\nstatus: draft\nowners: [alice]\n---\n\n# Slugs\n",
        encoding="utf-8",
    )

    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return tool, proj, log_path


def _read_log(log_path):
    if not Path(log_path).is_file():
        return []
    entries = []
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _calls(log_path, name):
    return [e for e in _read_log(log_path) if e.get("fn") == name]


class _Asker:
    def __init__(self, save_answer=None):
        self.save_answer = save_answer
        self.prompts = []
        self.counts = {}

    def __call__(self, prompt=""):
        p = str(prompt)
        self.prompts.append(p)
        if len(self.prompts) > 80:
            raise RuntimeError("too many questions asked: %r" % self.prompts[-5:])
        if "Save anyway?" in p:
            if self.save_answer is None:
                raise RuntimeError("unexpected Save anyway question")
            return self.save_answer
        n = self.counts.get(p, 0)
        self.counts[p] = n + 1
        fallbacks = ["", "openai", "3"]
        return fallbacks[n] if n < len(fallbacks) else ""


def _env():
    env = {"PATH": os.environ.get("PATH", "")}
    if os.environ.get("HOME"):
        env["HOME"] = os.environ["HOME"]
    return env


def _run(tool, proj, extra_argv, asker, capsys):
    outputs = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    capsys.readouterr()
    rc = hotdocs_init.main(
        [str(proj)] + list(extra_argv),
        tool_root=tool,
        input_fn=asker,
        output_fn=output_fn,
        env=_env(),
        cwd=proj,
    )
    captured = capsys.readouterr()
    return rc, "\n".join(outputs), captured.out, captured.err


NON_INTERACTIVE = ["--provider", "openai", "--model", "m", "--api-key-env", "MY_KEY"]


def _same_path(a, b):
    return os.path.realpath(str(a)) == os.path.realpath(str(b))


def test_connection_ok_non_interactive_saves_with_only_valued_keywords(tmp_path, capsys):
    tool, proj, log = _make_fixture(tmp_path, conn_mode="ok", save_mode="ok")
    asker = _Asker()
    rc, out, sout, serr = _run(tool, proj, NON_INTERACTIVE, asker, capsys)

    assert asker.prompts == [], "init asked questions: %r" % asker.prompts
    assert "connection ok" in (out + "\n" + sout), (out, sout, serr)
    assert rc in (0, 3), (rc, out, serr)

    conn = _calls(log, "check_connection")
    assert len(conn) >= 1

    saves = _calls(log, "save_config")
    assert len(saves) == 1, saves
    call = saves[0]
    args = call["args"]
    kwargs = call["kwargs"]
    names = ["config_path", "provider", "model", "base_url", "api_key_env", "timeout_seconds"]
    bound = dict(zip(names, args))
    bound.update(kwargs)

    assert len(args) <= 3, "base_url/api_key_env must be keywords: %r" % (args,)
    assert _same_path(bound["config_path"], proj / "hotdocs.toml"), bound
    assert bound["provider"] == "openai"
    assert bound["model"] == "m"
    assert kwargs.get("api_key_env") == "MY_KEY", kwargs
    assert "base_url" not in kwargs, kwargs
    assert "timeout_seconds" not in kwargs, kwargs


def test_connection_failed_interactive_save_anyway_no_then_yes(tmp_path, capsys):
    # Run 1: answer "n"
    tool1, proj1, log1 = _make_fixture(tmp_path / "run1", conn_mode="auth", save_mode="ok")
    asker1 = _Asker(save_answer="n")
    rc1, out1, sout1, serr1 = _run(tool1, proj1, [], asker1, capsys)

    combined1 = "\n".join([out1, sout1, serr1])
    assert "connection failed: auth: bad" in combined1, combined1
    assert "Save anyway? [y/N] " in asker1.prompts, asker1.prompts
    assert len(_calls(log1, "check_connection")) >= 1
    assert _calls(log1, "save_config") == [], _calls(log1, "save_config")

    # Run 2: fresh directory and tool root, answer "y"
    tool2, proj2, log2 = _make_fixture(tmp_path / "run2", conn_mode="auth", save_mode="ok")
    asker2 = _Asker(save_answer="y")
    rc2, out2, sout2, serr2 = _run(tool2, proj2, [], asker2, capsys)

    combined2 = "\n".join([out2, sout2, serr2])
    assert "connection failed: auth: bad" in combined2, combined2
    assert "Save anyway? [y/N] " in asker2.prompts, asker2.prompts
    saves2 = _calls(log2, "save_config")
    assert len(saves2) == 1, saves2
    first_arg = saves2[0]["args"][0] if saves2[0]["args"] else saves2[0]["kwargs"].get("config_path")
    assert _same_path(first_arg, proj2 / "hotdocs.toml")


def test_check_connection_value_error_printed_as_invalid(tmp_path, capsys):
    tool, proj, log = _make_fixture(tmp_path, conn_mode="valueerror", save_mode="ok")
    asker = _Asker()
    rc, out, sout, serr = _run(tool, proj, NON_INTERACTIVE, asker, capsys)

    combined = "\n".join([out, sout, serr])
    assert "connection failed: invalid: no base_url" in combined, combined
    assert len(_calls(log, "check_connection")) >= 1


def test_save_config_value_error_reported_and_exit_code_unchanged(tmp_path, capsys):
    # Baseline: same setup, save succeeds.
    tool_b, proj_b, log_b = _make_fixture(tmp_path / "baseline", conn_mode="ok", save_mode="ok")
    rc_base, out_b, sout_b, serr_b = _run(tool_b, proj_b, NON_INTERACTIVE, _Asker(), capsys)
    assert len(_calls(log_b, "save_config")) == 1

    tool, proj, log = _make_fixture(tmp_path / "failing", conn_mode="ok", save_mode="raise")
    rc, out, sout, serr = _run(tool, proj, NON_INTERACTIVE, _Asker(), capsys)

    assert "could not save: nope" in serr, (out, sout, serr)
    assert len(_calls(log, "save_config")) >= 1
    assert not (proj / "hotdocs.toml").exists()
    assert rc == rc_base, (rc, rc_base, out, serr)


def test_no_test_never_calls_check_connection(tmp_path, capsys):
    tool, proj, log = _make_fixture(tmp_path, conn_mode="ok", save_mode="ok")
    asker = _Asker()
    rc, out, sout, serr = _run(tool, proj, NON_INTERACTIVE + ["--no-test"], asker, capsys)

    assert _calls(log, "check_connection") == []
    # The fake was loaded and used (saving still happens without the test).
    assert len(_calls(log, "save_config")) == 1, _read_log(log)
    assert "connection ok" not in out
    assert "connection failed" not in (out + serr)