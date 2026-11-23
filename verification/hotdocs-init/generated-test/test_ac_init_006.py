# hotdocs-criterion: sha256:a707aac305aa36f175c2c391dece54917022044677b9bda52f5d92295eda311b
import importlib.metadata
import os
import shutil
import tomllib
from pathlib import Path

import hotdocs_init


FAKE_ENDPOINT_BODY = '''
import json
import tomllib
from pathlib import Path


def _log(name, **kw):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": {k: repr(v) for k, v in kw.items()}}) + "\\n")


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


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env=env, probe_ollama=probe_ollama)
    out = []
    for name, p in PROVIDERS.items():
        out.append({
            "provider": name,
            "available": name == "claude-cli",
            "reason": "fake detection",
            "suggested_model": p["suggested_model"],
            "api_key_env": p["default_api_key_env"],
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


def _q(value):
    return json.dumps(value)


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not isinstance(model, str) or not model:
        raise ValueError("model required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    kept = []
    in_llm = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = stripped == "[llm]"
            if in_llm:
                continue
        if not in_llm:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    llm = ["[llm]", "provider = " + _q(provider), "model = " + _q(model)]
    if base_url is not None:
        llm.append("base_url = " + _q(base_url))
    if api_key_env is not None:
        llm.append("api_key_env = " + _q(api_key_env))
    if timeout_seconds is not None:
        llm.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        llm.append("auth = " + _q(auth))
    parts = kept + ([""] if kept else []) + llm
    path.write_text("\\n".join(parts) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
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

EXAMPLE_CONTENT = "# Slugs\n\nExample product spec for slugify.\n"


def make_tool_root(base, log_path, with_endpoint=True):
    root = base
    root.mkdir(parents=True, exist_ok=True)
    ep_dir = root / "gen" / "llm-endpoint"
    ep_dir.mkdir(parents=True, exist_ok=True)
    if with_endpoint:
        src = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_ENDPOINT_BODY
        (ep_dir / "llm_endpoint.py").write_text(src, encoding="utf-8")
    ex = root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True, exist_ok=True)
    (ex / "slugs.md").write_text(EXAMPLE_CONTENT, encoding="utf-8")
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8"
    )
    (root / "QUICKSTART.md").write_text("# Quickstart\n", encoding="utf-8")
    return root


def snapshot(root):
    root = Path(root)
    result = {}
    if not root.exists():
        return result
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            rel = os.path.relpath(os.path.join(dirpath, d), root)
            result[rel + "/"] = None
        for f in filenames:
            p = Path(dirpath) / f
            result[os.path.relpath(p, root)] = p.read_bytes()
    return result


def do_run(argv, tool_root, cwd):
    lines = []

    def out(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    def inp(prompt=""):
        return ""

    env = {"PATH": os.environ.get("PATH", "")}
    rc = hotdocs_init.run(
        argv, tool_root=tool_root, input_fn=inp, output_fn=out, env=env, cwd=str(cwd)
    )
    return rc, lines


def check_next_steps(lines, tool_root_str, with_example):
    text = "\n".join(lines)
    quick = tool_root_str + "/QUICKSTART.md"
    names = ["hotdocs lint", "hotdocs verify", quick]
    if with_example:
        names.append("hotdocs generate comp-slugify")
    for n in names:
        assert n in text, (n, text)
    nonempty = [ln for ln in lines if ln.strip()]
    assert nonempty, "no output"
    last = nonempty[-1]
    all_names = ["hotdocs lint", "hotdocs verify", quick, "hotdocs generate comp-slugify"]
    assert any(n in last for n in all_names), last
    # Next steps form the tail: every named step appears after any earlier output
    first_step_pos = min(text.rfind(n) for n in names)
    tail = text[first_step_pos:]
    for n in names:
        assert n in tail


def test_example_copies_and_next_steps(tmp_path):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    tool_root = make_tool_root(tmp_path / "tool", log_path)
    tool_root_str = str(tmp_path) + "/tool"
    proj = tmp_path / "proj"
    proj.mkdir()

    rc, lines = do_run([str(proj), "--example", "--yes"], tool_root_str, tmp_path)
    assert rc in (0, 3)

    copied = proj / "specs" / "product" / "slugs.md"
    assert copied.is_file()
    assert copied.read_bytes() == (
        tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    ).read_bytes()
    assert not (proj / "examples").exists()

    check_next_steps(lines, tool_root_str, with_example=True)


def test_example_never_overwrites_existing(tmp_path):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    make_tool_root(tmp_path / "tool", log_path)
    tool_root_str = str(tmp_path) + "/tool"
    proj = tmp_path / "proj"
    existing = proj / "specs" / "product" / "slugs.md"
    existing.parent.mkdir(parents=True)
    original = "# My own slugs\n\nDo not overwrite.\n"
    existing.write_text(original, encoding="utf-8")

    do_run([str(proj), "--example", "--yes"], tool_root_str, tmp_path)

    assert existing.read_text(encoding="utf-8") == original
    assert not (proj / "examples").exists()


def test_no_example_omits_slugify(tmp_path):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    make_tool_root(tmp_path / "tool", log_path)
    tool_root_str = str(tmp_path) + "/tool"
    proj = tmp_path / "proj"
    proj.mkdir()

    rc, lines = do_run([str(proj), "--yes"], tool_root_str, tmp_path)
    assert rc in (0, 3)
    text = "\n".join(lines)
    assert "comp-slugify" not in text
    check_next_steps(lines, tool_root_str, with_example=False)


def test_reconfigure_changes_only_hotdocs_toml(tmp_path):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    tool_root = make_tool_root(tmp_path / "tool", log_path)
    tool_root_str = str(tmp_path) + "/tool"
    proj = tmp_path / "proj"
    proj.mkdir()

    rc, _ = do_run([str(proj), "--yes"], tool_root_str, tmp_path)
    assert rc in (0, 3)
    assert (proj / ".hotdocs-tool.json").is_file()
    assert (proj / "hotdocs.toml").is_file()

    before = snapshot(proj)
    tool_before = snapshot(tool_root)

    rc, _ = do_run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root_str,
        tmp_path,
    )
    assert rc in (0, 3)

    after = snapshot(proj)
    assert set(after) == set(before)
    for key in before:
        if key == "hotdocs.toml":
            continue
        assert after[key] == before[key], key
    assert after["hotdocs.toml"] != before["hotdocs.toml"]
    data = tomllib.loads((proj / "hotdocs.toml").read_text(encoding="utf-8"))
    assert data["llm"]["provider"] == "openai"
    assert data["llm"]["model"] == "m"
    assert snapshot(tool_root) == tool_before

    # A tool root without gen/llm-endpoint/llm_endpoint.py -> exit 1
    bare_root = tmp_path / "bare-tool"
    shutil.copytree(tool_root, bare_root)
    (bare_root / "gen" / "llm-endpoint" / "llm_endpoint.py").unlink()
    pkg = bare_root / "gen" / "llm-endpoint" / "llm_endpoint"
    if pkg.exists():
        shutil.rmtree(pkg)
    rc, _ = do_run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        str(tmp_path) + "/bare-tool",
        tmp_path,
    )
    assert rc == 1


def test_reconfigure_uninitialised_returns_1_and_writes_nothing(tmp_path):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    tool_root = make_tool_root(tmp_path / "tool", log_path)
    tool_root_str = str(tmp_path) + "/tool"
    proj = tmp_path / "proj"
    (proj / "specs" / "product").mkdir(parents=True)
    (proj / "specs" / "product" / "thing.md").write_text("# Thing\n", encoding="utf-8")

    before = snapshot(proj)
    tool_before = snapshot(tool_root)

    rc, _ = do_run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root_str,
        tmp_path,
    )
    assert rc == 1
    assert snapshot(proj) == before
    assert snapshot(tool_root) == tool_before