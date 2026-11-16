import importlib.metadata
import json
import os
import sys
from pathlib import Path

import pytest

import hotdocs_init


EXAMPLE_TEXT = "# Slugs\n\nExample product spec for slugify.\n"

FAKE_ENDPOINT_TEMPLATE = r'''
import json
import os
from pathlib import Path

LOG = __LOG_PATH__

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


def _log(name, **kwargs):
    Path(LOG).parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, **kwargs}, default=str) + "\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    out = []
    for name, info in PROVIDERS.items():
        available = name == "claude-cli"
        out.append({
            "provider": name,
            "available": available,
            "reason": "fake: available" if available else "fake: unavailable",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url is required for %s" % provider)
    return {"ok": True, "error": None}


def _strip_llm(text):
    out = []
    in_llm = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_llm = stripped == "[llm]"
            if in_llm:
                continue
        if in_llm:
            continue
        out.append(line)
    return "\n".join(out).strip()


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env, timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    if not model:
        raise ValueError("model is required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url is required for %s" % provider)
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    rest = _strip_llm(existing)
    lines = ["[llm]", "provider = " + json.dumps(provider), "model = " + json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = %d" % int(timeout_seconds))
    body = "\n".join(lines) + "\n"
    if rest:
        body = rest + "\n\n" + body
    path.write_text(body, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=None if config_path is None else str(config_path))
    path = Path(config_path) if config_path is not None else Path.cwd() / "hotdocs.toml"
    if not path.exists():
        return None
    result = {"provider": None, "model": None, "base_url": None,
              "api_key_env": None, "timeout_seconds": None}
    in_llm = False
    found = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            in_llm = stripped == "[llm]"
            if in_llm:
                found = True
            continue
        if in_llm and "=" in stripped:
            key, value = stripped.split("=", 1)
            key = key.strip()
            try:
                parsed = json.loads(value.strip())
            except Exception:
                raise ValueError("invalid value for %s" % key)
            if key in result:
                result[key] = parsed
    if not found:
        return None
    if result["provider"] not in PROVIDERS:
        raise ValueError("invalid provider")
    return result
'''

FAKE_LINTER = '''
def lint(paths=None, repo_root=None):
    return []
'''


def _make_tool_root(root, log_path, with_endpoint=True):
    root.mkdir(parents=True, exist_ok=True)
    if with_endpoint:
        ep = root / "gen" / "llm-endpoint"
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "llm_endpoint.py").write_text(
            FAKE_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path))),
            encoding="utf-8",
        )
    else:
        (root / "gen" / "llm-endpoint").mkdir(parents=True, exist_ok=True)
    lint_dir = root / "gen" / "spec-linter"
    lint_dir.mkdir(parents=True, exist_ok=True)
    (lint_dir / "spec_linter.py").write_text(FAKE_LINTER, encoding="utf-8")
    ex = root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True, exist_ok=True)
    (ex / "slugs.md").write_text(EXAMPLE_TEXT, encoding="utf-8")
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return root


def _snapshot(root):
    snap = {}
    root = Path(root)
    if not root.exists():
        return snap
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        snap[rel] = p.read_bytes() if p.is_file() else None
    return snap


def _read_log(log_path):
    if not Path(log_path).exists():
        return []
    out = []
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


class _Collector:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        text = " ".join(str(a) for a in args)
        self.lines.extend(text.splitlines() or [""])

    def text(self):
        return "\n".join(self.lines)


class _Input:
    def __init__(self, answer=""):
        self.answer = answer
        self.prompts = []

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        return self.answer


@pytest.fixture
def setup(tmp_path):
    log_path = tmp_path / "logs" / "endpoint_calls.jsonl"
    tool_root = _make_tool_root(tmp_path / "tool", log_path)
    project = tmp_path / "proj"
    home = tmp_path / "home"
    home.mkdir()
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home)}
    return {
        "tmp": tmp_path,
        "log": log_path,
        "tool_root": tool_root,
        "project": project,
        "env": env,
    }


def _run(s, argv, tool_root=None):
    out = _Collector()
    inp = _Input("")
    rc = hotdocs_init.main(
        argv,
        tool_root=str(tool_root if tool_root is not None else s["tool_root"]),
        input_fn=inp,
        output_fn=out,
        env=dict(s["env"]),
        cwd=str(s["tmp"]),
    )
    return rc, out, inp


def _tail_text(collector, n=15):
    non_empty = [line for line in collector.lines if line.strip()]
    return "\n".join(non_empty[-n:])


def test_example_copies_slugs_and_prints_next_steps(setup):
    s = setup
    rc, out, _ = _run(s, [str(s["project"]), "--example", "--yes"])
    assert rc in (0, 3), out.text()

    copied = s["project"] / "specs" / "product" / "slugs.md"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == EXAMPLE_TEXT
    assert not (s["project"] / "examples").exists()

    full = out.text()
    for needle in ("hotdocs lint", "hotdocs generate comp-slugify", "hotdocs verify", "QUICKSTART.md"):
        assert needle in full, full
    tail = _tail_text(out)
    for needle in ("hotdocs lint", "hotdocs generate comp-slugify", "hotdocs verify", "QUICKSTART.md"):
        assert needle in tail, tail


def test_example_never_overwrites_existing_file(setup):
    s = setup
    existing = s["project"] / "specs" / "product" / "slugs.md"
    existing.parent.mkdir(parents=True, exist_ok=True)
    mine = "# My own slugs\n\nDo not touch.\n"
    existing.write_text(mine, encoding="utf-8")

    rc, out, _ = _run(s, [str(s["project"]), "--example", "--yes"])
    assert rc != 2, out.text()
    assert existing.read_text(encoding="utf-8") == mine
    assert not (s["project"] / "examples").exists()


def test_without_example_next_steps_omit_comp_slugify(setup):
    s = setup
    rc, out, _ = _run(s, [str(s["project"]), "--yes"])
    assert rc in (0, 3), out.text()
    full = out.text()
    assert "comp-slugify" not in full
    for needle in ("hotdocs lint", "hotdocs verify", "QUICKSTART.md"):
        assert needle in full, full
    tail = _tail_text(out)
    for needle in ("hotdocs lint", "hotdocs verify", "QUICKSTART.md"):
        assert needle in tail, tail
    assert not (s["project"] / "specs" / "product" / "slugs.md").exists()
    assert not (s["project"] / "examples").exists()


def _init_project(s):
    rc, out, _ = _run(s, [str(s["project"]), "--yes"])
    assert rc in (0, 3), out.text()
    assert (s["project"] / ".hotdocs-tool.json").is_file()
    assert (s["project"] / "hotdocs.toml").is_file()


def test_reconfigure_changes_only_hotdocs_toml(setup):
    s = setup
    _init_project(s)
    before = _snapshot(s["project"])
    log_before = len(_read_log(s["log"]))

    rc, out, _ = _run(
        s,
        [str(s["project"]), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
    )
    assert rc in (0, 3), out.text()

    after = _snapshot(s["project"])
    assert set(after.keys()) == set(before.keys())
    changed = sorted(k for k in after if after[k] != before[k])
    assert changed == ["hotdocs.toml"], changed

    toml_text = (s["project"] / "hotdocs.toml").read_text(encoding="utf-8")
    assert '"openai"' in toml_text
    assert 'model = "m"' in toml_text

    new_calls = _read_log(s["log"])[log_before:]
    saves = [c for c in new_calls if c.get("call") == "save_config"]
    assert saves, new_calls
    last = saves[-1]
    assert last.get("provider") == "openai"
    assert last.get("model") == "m"
    assert Path(last.get("config_path")).resolve() == (s["project"] / "hotdocs.toml").resolve()
    assert not any(c.get("call") == "check_connection" for c in new_calls)


def test_reconfigure_without_endpoint_module_returns_1(setup):
    s = setup
    _init_project(s)
    bare_tool = _make_tool_root(s["tmp"] / "bare_tool", s["log"], with_endpoint=False)
    assert not (bare_tool / "gen" / "llm-endpoint" / "llm_endpoint.py").exists()
    assert not (bare_tool / "gen" / "llm-endpoint" / "llm_endpoint" / "__init__.py").exists()

    before = _snapshot(s["project"])
    rc, out, _ = _run(
        s,
        [str(s["project"]), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=bare_tool,
    )
    assert rc == 1, out.text()
    after = _snapshot(s["project"])
    assert after == before


def test_reconfigure_on_uninitialised_directory_returns_1_and_writes_nothing(setup):
    s = setup
    project = s["project"]
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    before = _snapshot(project)
    log_before = len(_read_log(s["log"]))

    rc, out, _ = _run(
        s,
        [str(project), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
    )
    assert rc == 1, out.text()
    after = _snapshot(project)
    assert after == before
    assert not (project / "hotdocs.toml").exists()
    assert not (project / ".hotdocs-tool.json").exists()
    new_calls = _read_log(s["log"])[log_before:]
    assert not any(c.get("call") == "save_config" for c in new_calls)