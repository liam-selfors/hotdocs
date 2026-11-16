import importlib.metadata
import json
import os
import time
from pathlib import Path

import pytest

import hotdocs_init


DIRS = [
    "specs/product",
    "specs/components",
    "specs/decisions",
    "gen",
    "verification",
]
GITKEEPS = [
    "specs/product/.gitkeep",
    "specs/components/.gitkeep",
    "specs/decisions/.gitkeep",
    "verification/.gitkeep",
]
FILES = ["specs/glossary.md", ".secret-allowlist.json", ".gitignore"]
ALL_PATHS = DIRS + GITKEEPS + FILES
GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]


FAKE_LLM_ENDPOINT = r'''
import json
import os
from pathlib import Path

_LOG_PATH = __LOG_PATH__

DEFAULT_TIMEOUT_SECONDS = 600


def _log(name, **kwargs):
    rec = {"call": name}
    for k, v in kwargs.items():
        try:
            json.dumps(v)
            rec[k] = v
        except (TypeError, ValueError):
            rec[k] = repr(v)
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


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
    for name, info in PROVIDERS.items():
        available = name == "ollama"
        out.append({
            "provider": name,
            "available": available,
            "reason": "fake: reachable" if available else "fake: not available",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %r" % (provider,))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("provider %r needs a base_url" % (provider,))
    return {"ok": True, "error": None}


def _strip_llm_table(text):
    out = []
    in_llm = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_llm = s == "[llm]"
            if in_llm:
                continue
        if not in_llm:
            out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None):
    _log("save_config", config_path=str(config_path), provider=provider,
         model=model, base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %r" % (provider,))
    if not isinstance(model, str) or not model:
        raise ValueError("model must be a non-empty string")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("provider %r needs a base_url" % (provider,))
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    kept = _strip_llm_table(existing)
    lines = ["[llm]", "provider = " + json.dumps(provider),
             "model = " + json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = %d" % int(timeout_seconds))
    new = (kept + "\n\n" if kept else "") + "\n".join(lines) + "\n"
    if existing == new:
        return None
    path.write_text(new, encoding="utf-8")
    return None


def _parse(text):
    try:
        import tomllib
        return tomllib.loads(text)
    except ImportError:
        pass
    data = {}
    current = data
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            current = data.setdefault(s[1:-1].strip(), {})
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            v = v.strip()
            try:
                current[k.strip()] = json.loads(v)
            except ValueError:
                raise ValueError("invalid config line: %r" % (line,))
    return data


def load_config(config_path=None):
    _log("load_config", config_path=None if config_path is None else str(config_path))
    if config_path is None:
        config_path = Path.cwd() / "hotdocs.toml"
    path = Path(config_path)
    if not path.exists():
        return None
    try:
        data = _parse(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("invalid config: %s" % (exc,))
    llm = data.get("llm")
    if not isinstance(llm, dict):
        return None
    provider = llm.get("provider")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider in config")
    return {
        "provider": provider,
        "model": llm.get("model"),
        "base_url": llm.get("base_url"),
        "api_key_env": llm.get("api_key_env"),
        "timeout_seconds": llm.get("timeout_seconds"),
    }
'''


def _make_tool_root(base: Path, log_path: Path) -> Path:
    tool_root = base / "toolroot"
    mod_dir = tool_root / "gen" / "llm-endpoint"
    mod_dir.mkdir(parents=True)
    (mod_dir / "llm_endpoint.py").write_text(
        FAKE_LLM_ENDPOINT.replace("__LOG_PATH__", repr(str(log_path))),
        encoding="utf-8",
    )
    ex = tool_root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True)
    (ex / "slugs.md").write_text("# Slugs\n\nA fake example product spec.\n",
                                 encoding="utf-8")
    version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text("pytest==" + version + "\n",
                                                encoding="utf-8")
    return tool_root


def _env(base: Path) -> dict:
    home = base / "home"
    home.mkdir(exist_ok=True)
    return {"PATH": os.environ.get("PATH", ""), "HOME": str(home)}


class _Out:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        text = sep.join(str(a) for a in args)
        for line in text.splitlines() or [""]:
            self.lines.append(line)


def _input_fn(prompt=""):
    return ""


def _run(project: Path, tool_root: Path, base: Path):
    out = _Out()
    rc = hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=_input_fn,
        output_fn=out,
        env=_env(base),
        cwd=str(project),
    )
    return rc, out.lines


def _snapshot(root: Path) -> dict:
    snap = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file():
            st = p.stat()
            snap[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
        elif p.is_dir():
            snap[rel] = ("dir", None, None)
    return snap


def test_ac_init_001_create_then_skip(tmp_path):
    log_path = tmp_path / "fake_llm_calls.log"
    tool_root = _make_tool_root(tmp_path, log_path)
    project = tmp_path / "project"
    project.mkdir()
    assert list(project.iterdir()) == []

    rc, lines = _run(project, tool_root, tmp_path)
    assert rc not in (1, 2), "first init run failed with exit code %r; output: %r" % (rc, lines)

    for d in DIRS:
        assert (project / d).is_dir(), "missing directory %s" % d
    for g in GITKEEPS:
        gp = project / g
        assert gp.is_file(), "missing %s" % g
        assert gp.read_bytes() == b"", "%s is not empty" % g
    glossary = project / "specs" / "glossary.md"
    assert glossary.is_file()
    assert glossary.read_text(encoding="utf-8").startswith("# Glossary")
    assert (project / ".secret-allowlist.json").is_file()
    gi_lines = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
    for line in GITIGNORE_LINES:
        assert gi_lines.count(line) == 1, \
            ".gitignore holds %r %d times" % (line, gi_lines.count(line))

    for p in ALL_PATHS:
        assert (p + ": created") in lines, \
            "expected output line %r; got %r" % (p + ": created", lines)

    tool_json = project / ".hotdocs-tool.json"
    assert tool_json.is_file(), ".hotdocs-tool.json not present after first run"

    before = _snapshot(project)
    time.sleep(1.1)

    rc2, lines2 = _run(project, tool_root, tmp_path)
    assert rc2 not in (1, 2), "second init run failed with exit code %r; output: %r" % (rc2, lines2)

    after = _snapshot(project)
    assert set(after) == set(before), \
        "file set changed: added %r, removed %r" % (
            sorted(set(after) - set(before)), sorted(set(before) - set(after)))
    for rel, (kind, data, mtime) in before.items():
        a_kind, a_data, a_mtime = after[rel]
        assert a_kind == kind, "%s changed kind" % rel
        if kind == "file":
            assert a_data == data, "%s bytes changed on second run" % rel
            assert a_mtime == mtime, "%s modification time changed on second run" % rel

    assert before[".hotdocs-tool.json"][1] == after[".hotdocs-tool.json"][1]
    assert before[".hotdocs-tool.json"][2] == after[".hotdocs-tool.json"][2]

    for p in ALL_PATHS:
        assert (p + ": skipped (exists)") in lines2, \
            "expected output line %r; got %r" % (p + ": skipped (exists)", lines2)
        assert (p + ": created") not in lines2, \
            "unexpected %r on second run" % (p + ": created")


def test_ac_init_001_existing_files_preserved(tmp_path):
    log_path = tmp_path / "fake_llm_calls.log"
    tool_root = _make_tool_root(tmp_path, log_path)
    project = tmp_path / "project"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "glossary.md").write_text("mine", encoding="utf-8")
    (project / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")

    rc, lines = _run(project, tool_root, tmp_path)
    assert rc not in (1, 2), "init failed with exit code %r; output: %r" % (rc, lines)

    assert (project / "specs" / "glossary.md").read_text(encoding="utf-8") == "mine"
    assert "specs/glossary.md: skipped (exists)" in lines

    gi_lines = (project / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert gi_lines.count("/.hotdocs/") == 1, \
        ".gitignore holds /.hotdocs/ %d times" % gi_lines.count("/.hotdocs/")
    for line in ["__pycache__/", "*.pyc", ".venv/"]:
        assert gi_lines.count(line) == 1, \
            ".gitignore holds %r %d times" % (line, gi_lines.count(line))