# hotdocs-criterion: sha256:208c3fdab7035c6632bef5ceee405bd07bdd607549468744eb917600b670b53f
import importlib.metadata
import json
import os
import shutil
from pathlib import Path

import pytest

import hotdocs_init


FAKE_LLM_ENDPOINT_BODY = '''
import json
from pathlib import Path


def _log(name, **kw):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": {k: repr(v) for k, v in kw.items()}}) + "\\n")


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
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    out = []
    for name, p in PROVIDERS.items():
        out.append({
            "provider": name,
            "available": name == "ollama",
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


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model and provider != "openai-compatible":
        raise ValueError("model required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    keep = []
    skip = False
    for line in existing.splitlines():
        s = line.strip()
        if s.startswith("["):
            skip = (s == "[llm]")
        if not skip:
            keep.append(line)
    block = ["[llm]", "provider = " + json.dumps(provider), "model = " + json.dumps(model)]
    if base_url is not None:
        block.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        block.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        block.append("timeout_seconds = " + json.dumps(int(timeout_seconds)))
    if auth is not None:
        block.append("auth = " + json.dumps(auth))
    text = "\\n".join(keep).rstrip("\\n")
    text = (text + "\\n\\n" if text else "") + "\\n".join(block) + "\\n"
    path.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    if config_path is None:
        config_path = Path.cwd() / "hotdocs.toml"
    path = Path(config_path)
    if not path.exists():
        return None
    data = None
    in_llm = False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("["):
            in_llm = (s == "[llm]")
            if in_llm:
                data = {"provider": None, "model": None, "base_url": None,
                        "api_key_env": None, "timeout_seconds": None, "auth": None}
            continue
        if in_llm and "=" in s:
            k, v = s.split("=", 1)
            try:
                data[k.strip()] = json.loads(v.strip())
            except Exception:
                raise ValueError("invalid hotdocs.toml")
    return data
'''

EXAMPLE_CONTENT = "# Slugs\n\nExample product spec for slugify.\n"


def make_tool_root(base, log_path, with_llm_endpoint=True):
    root = base
    root.mkdir(parents=True, exist_ok=True)
    if with_llm_endpoint:
        ep = root / "gen" / "llm-endpoint"
        ep.mkdir(parents=True, exist_ok=True)
        src = "LOG = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY
        (ep / "llm_endpoint.py").write_text(src, encoding="utf-8")
    else:
        (root / "gen").mkdir(parents=True, exist_ok=True)
    ex = root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True, exist_ok=True)
    (ex / "slugs.md").write_text(EXAMPLE_CONTENT, encoding="utf-8")
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    return root


def snapshot(root):
    snap = {}
    root = Path(root)
    if not root.exists():
        return snap
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_dir():
            snap[rel] = "<dir>"
        else:
            snap[rel] = p.read_bytes()
    return snap


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]


class Runner:
    def __init__(self, cwd):
        self.out = []
        self.prompts = []
        self.cwd = cwd

    def output_fn(self, *args, **kwargs):
        self.out.append(" ".join(str(a) for a in args))

    def input_fn(self, prompt=""):
        self.prompts.append(prompt)
        return ""

    def run(self, argv, tool_root):
        return hotdocs_init.main(
            argv,
            tool_root=tool_root,
            input_fn=self.input_fn,
            output_fn=self.output_fn,
            env={"PATH": os.environ.get("PATH", "")},
            cwd=self.cwd,
        )


@pytest.fixture
def setup(tmp_path):
    log_path = tmp_path / "logs" / "llm.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tool_root = make_tool_root(tmp_path / "tool", log_path)
    work = tmp_path / "work"
    work.mkdir()
    return tmp_path, tool_root, log_path, work


def test_example_copies_slugs_and_prints_next_steps(setup):
    tmp_path, tool_root, log_path, work = setup
    proj = tmp_path / "proj"
    proj.mkdir()
    tool_before = snapshot(tool_root)
    r = Runner(work)
    code = r.run([str(proj), "--example", "--yes"], tool_root)
    assert code in (0, 3), r.out

    copied = proj / "specs" / "product" / "slugs.md"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == EXAMPLE_CONTENT
    assert not (proj / "examples").exists()

    tail = "\n".join(r.out[-12:])
    for needle in ("hotdocs lint", "hotdocs generate comp-slugify", "hotdocs verify", "QUICKSTART.md"):
        assert needle in tail, (needle, r.out)
    last_nonempty = [l for l in r.out if l.strip()]
    assert last_nonempty
    end = "\n".join(last_nonempty[-6:])
    assert any(n in end for n in ("hotdocs lint", "hotdocs generate comp-slugify",
                                  "hotdocs verify", "QUICKSTART.md"))

    assert snapshot(tool_root) == tool_before


def test_example_never_overwrites_existing_file(setup):
    tmp_path, tool_root, log_path, work = setup
    proj = tmp_path / "proj"
    existing = proj / "specs" / "product" / "slugs.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("my own slugs, keep me\n", encoding="utf-8")
    r = Runner(work)
    r.run([str(proj), "--example", "--yes"], tool_root)
    assert existing.read_text(encoding="utf-8") == "my own slugs, keep me\n"
    assert not (proj / "examples").exists()


def test_no_example_next_steps_omit_comp_slugify(setup):
    tmp_path, tool_root, log_path, work = setup
    proj = tmp_path / "proj"
    proj.mkdir()
    r = Runner(work)
    code = r.run([str(proj), "--yes"], tool_root)
    assert code in (0, 3), r.out
    text = "\n".join(r.out)
    assert "comp-slugify" not in text
    tail = "\n".join(r.out[-12:])
    for needle in ("hotdocs lint", "hotdocs verify", "QUICKSTART.md"):
        assert needle in tail, (needle, r.out)
    assert not (proj / "specs" / "product" / "slugs.md").exists()


def test_reconfigure_changes_only_hotdocs_toml(setup):
    tmp_path, tool_root, log_path, work = setup
    proj = tmp_path / "proj"
    proj.mkdir()
    r = Runner(work)
    code = r.run(
        [str(proj), "--provider", "ollama", "--model", "llama3.2", "--no-test", "--yes"],
        tool_root,
    )
    assert code in (0, 3), r.out
    assert (proj / ".hotdocs-tool.json").is_file()
    assert (proj / "hotdocs.toml").is_file()

    proj_before = snapshot(proj)
    tool_before = snapshot(tool_root)
    log_before = len(read_log(log_path))

    r2 = Runner(work)
    code2 = r2.run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root,
    )
    assert code2 in (0, 3), r2.out

    proj_after = snapshot(proj)
    assert set(proj_after) == set(proj_before)
    changed = [k for k in proj_after if proj_after[k] != proj_before[k]]
    assert changed == ["hotdocs.toml"]
    toml_text = (proj / "hotdocs.toml").read_text(encoding="utf-8")
    assert 'provider = "openai"' in toml_text
    assert 'model = "m"' in toml_text
    assert snapshot(tool_root) == tool_before

    new_calls = read_log(log_path)[log_before:]
    assert any(c["call"] == "save_config" for c in new_calls)


def test_reconfigure_without_llm_endpoint_returns_1(setup):
    tmp_path, tool_root, log_path, work = setup
    proj = tmp_path / "proj"
    proj.mkdir()
    r = Runner(work)
    code = r.run(
        [str(proj), "--provider", "ollama", "--model", "llama3.2", "--no-test", "--yes"],
        tool_root,
    )
    assert code in (0, 3), r.out
    assert (proj / ".hotdocs-tool.json").is_file()
    assert (proj / "hotdocs.toml").is_file()

    bare_log = tmp_path / "logs" / "bare.log"
    bare_root = make_tool_root(tmp_path / "bare-tool", bare_log, with_llm_endpoint=False)
    assert not (bare_root / "gen" / "llm-endpoint" / "llm_endpoint.py").exists()
    assert not (bare_root / "gen" / "llm-endpoint" / "llm_endpoint" / "__init__.py").exists()

    toml_before = (proj / "hotdocs.toml").read_bytes()
    r2 = Runner(work)
    code2 = r2.run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        bare_root,
    )
    assert code2 == 1
    assert (proj / "hotdocs.toml").read_bytes() == toml_before


def test_reconfigure_on_uninitialised_dir_returns_1_and_writes_nothing(setup):
    tmp_path, tool_root, log_path, work = setup
    proj = tmp_path / "proj"
    (proj / "specs").mkdir(parents=True)
    (proj / "specs" / "notes.md").write_text("notes\n", encoding="utf-8")
    proj_before = snapshot(proj)
    tool_before = snapshot(tool_root)
    log_before = len(read_log(log_path))

    r = Runner(work)
    code = r.run(
        [str(proj), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root,
    )
    assert code == 1
    assert snapshot(proj) == proj_before
    assert not (proj / "hotdocs.toml").exists()
    assert not (proj / ".hotdocs-tool.json").exists()
    assert snapshot(tool_root) == tool_before
    new_calls = read_log(log_path)[log_before:]
    assert not any(c["call"] == "save_config" for c in new_calls)