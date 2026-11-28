# hotdocs-criterion: sha256:6a2aead3e9daea4ada07589b85f9f177374e1433cf18c1e7555189add3e5a673
import json
import os
import time
from pathlib import Path

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
GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/", "/dist/"]


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


FAKE_BODY = '''
import json
import os
import tomllib
from pathlib import Path


def _log(name, **kwargs):
    Path(LOG).parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": kwargs}, default=str) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    out = []
    for name, info in PROVIDERS.items():
        available = name == "claude-cli"
        out.append({
            "provider": name,
            "available": available,
            "reason": "found" if available else "not configured",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
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
        raise ValueError("unknown provider: " + str(provider))
    if not isinstance(model, str):
        raise ValueError("invalid model")
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
    lines.append("[llm]")
    lines.append("provider = " + _q(provider))
    lines.append("model = " + _q(model))
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
    _log("load_config", config_path=None if config_path is None else str(config_path))
    path = Path(config_path) if config_path is not None else Path.cwd() / "hotdocs.toml"
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("invalid config") from exc
    llm = data.get("llm")
    if llm is None:
        return None
    if not isinstance(llm, dict) or llm.get("provider") not in PROVIDERS:
        raise ValueError("invalid config")
    return {
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "base_url": llm.get("base_url"),
        "api_key_env": llm.get("api_key_env"),
        "timeout_seconds": llm.get("timeout_seconds"),
        "auth": llm.get("auth"),
    }
'''


def make_tool_root(base, log_path):
    root = base / "toolroot"
    llm_dir = root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    source = (
        "LOG = " + repr(str(log_path)) + "\n"
        + "PROVIDERS = " + repr(PROVIDERS) + "\n"
        + FAKE_BODY
    )
    (llm_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    slug = root / "examples" / "slugify" / "specs" / "product"
    slug.mkdir(parents=True)
    (slug / "slugs.md").write_text("# Slugs\n\nAn example product spec.\n", encoding="utf-8")

    import importlib.metadata

    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8"
    )
    return root


def call_run(project, tool_root, workdir):
    lines = []

    def output_fn(*args, **kwargs):
        text = " ".join(str(a) for a in args)
        lines.extend(text.splitlines() if text else [text])

    def input_fn(prompt=""):
        return ""

    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(workdir)}
    code = hotdocs_init.run(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=workdir,
    )
    return code, lines


def snapshot(project):
    result = {}
    for p in sorted(project.rglob("*")):
        rel = p.relative_to(project).as_posix()
        if p.is_file():
            st = p.stat()
            result[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
        elif p.is_dir():
            result[rel] = ("dir",)
    return result


def gitignore_lines(project):
    return (project / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_ac_init_001_fresh_then_second_run(tmp_path):
    log_path = tmp_path / "logs" / "llm.log"
    tool_root = make_tool_root(tmp_path, log_path)
    workdir = tmp_path / "work"
    workdir.mkdir()
    project = tmp_path / "project"
    project.mkdir()

    code, lines = call_run(project, tool_root, workdir)
    assert code in (0, 3), (code, lines)

    for d in DIRS:
        assert (project / d).is_dir(), d
    for g in GITKEEPS:
        assert (project / g).is_file(), g
        assert (project / g).read_bytes() == b"", g
    glossary = (project / "specs" / "glossary.md").read_text(encoding="utf-8")
    assert glossary.startswith("# Glossary")
    assert (project / ".secret-allowlist.json").is_file()
    gi = gitignore_lines(project)
    for line in GITIGNORE_LINES:
        assert gi.count(line) == 1, (line, gi)

    for path in ALL_PATHS:
        expected = path + ": created"
        assert expected in lines, (expected, lines)

    before = snapshot(project)
    assert ".hotdocs-tool.json" in before, sorted(before)

    time.sleep(0.05)
    code2, lines2 = call_run(project, tool_root, workdir)
    assert code2 in (0, 3), (code2, lines2)

    after = snapshot(project)
    assert after == before

    for path in ALL_PATHS:
        expected = path + ": skipped (exists)"
        assert expected in lines2, (expected, lines2)
        assert (path + ": created") not in lines2, (path, lines2)


def test_ac_init_001_keeps_existing_files(tmp_path):
    log_path = tmp_path / "logs" / "llm.log"
    tool_root = make_tool_root(tmp_path, log_path)
    workdir = tmp_path / "work"
    workdir.mkdir()
    project = tmp_path / "project"
    (project / "specs").mkdir(parents=True)
    (project / "specs" / "glossary.md").write_bytes(b"mine")
    (project / ".gitignore").write_text("/.hotdocs/\n", encoding="utf-8")

    code, lines = call_run(project, tool_root, workdir)
    assert code in (0, 3), (code, lines)

    assert (project / "specs" / "glossary.md").read_bytes() == b"mine"
    gi = gitignore_lines(project)
    assert gi[0] == "/.hotdocs/"
    assert gi.count("/.hotdocs/") == 1, gi
    for line in GITIGNORE_LINES[1:]:
        assert gi.count(line) == 1, (line, gi)