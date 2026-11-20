# hotdocs-criterion: sha256:c1793b492e989eb9dfb21bf6be6d8c001a378324a71be3af133ecdb767af3bcc
import importlib.metadata
import json
from pathlib import Path

import hotdocs_init


FAKE_ENDPOINT_BODY = '''
import json
from pathlib import Path


def _log(name, **kwargs):
    entry = {"call": name}
    entry.update(kwargs)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\\n")


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
        out.append({
            "provider": name,
            "available": name == "openai",
            "reason": "fake",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _strip_llm(text):
    kept = []
    in_llm = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = stripped == "[llm]"
            if in_llm:
                continue
        if not in_llm:
            kept.append(line)
    return "\\n".join(kept).strip()


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider,
         model=model)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model:
        raise ValueError("model required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    rest = _strip_llm(existing)
    lines = ["[llm]", "provider = " + json.dumps(provider),
             "model = " + json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    text = ""
    if rest:
        text = rest + "\\n\\n"
    text += "\\n".join(lines) + "\\n"
    path.write_text(text, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    if config_path is None:
        return None
    path = Path(config_path)
    if not path.exists():
        return None
    result = {"provider": None, "model": None, "base_url": None,
              "api_key_env": None, "timeout_seconds": None, "auth": None}
    in_llm = False
    found = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = stripped == "[llm]"
            found = found or in_llm
            continue
        if in_llm and "=" in stripped:
            key, value = stripped.split("=", 1)
            key = key.strip()
            if key in result:
                result[key] = json.loads(value.strip())
    if not found:
        return None
    return result
'''

EXAMPLE_TEXT = "# Slugs\n\nExample product spec for slugify.\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_tool_root(base, log_path, with_endpoint=True):
    root = base
    root.mkdir(parents=True, exist_ok=True)
    if with_endpoint:
        ep = root / "gen" / "llm-endpoint"
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "llm_endpoint.py").write_text(
            "LOG = " + repr(str(log_path)) + "\n" + FAKE_ENDPOINT_BODY,
            encoding="utf-8",
        )
    other = root / "gen" / "slugify"
    other.mkdir(parents=True, exist_ok=True)
    (other / "slugify.py").write_text(
        "def slugify(text):\n    return " + repr("x") + "\n", encoding="utf-8"
    )
    ex = root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True, exist_ok=True)
    (ex / "slugs.md").write_text(EXAMPLE_TEXT, encoding="utf-8")
    (root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n",
        encoding="utf-8",
    )
    return root


def setup(tmp_path, with_endpoint=True, name="tool"):
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / (name + "-calls.log")
    tool_root = make_tool_root(tmp_path / name, log_path, with_endpoint)
    return tool_root, log_path


class Out:
    def __init__(self):
        self.chunks = []

    def __call__(self, *args, **kwargs):
        sep = kwargs.get("sep", " ")
        self.chunks.append(sep.join(str(a) for a in args))

    def text(self):
        return "\n".join(self.chunks)

    def lines(self):
        return self.text().splitlines()


def do_run(argv, tool_root, tmp_path):
    out = Out()
    rc = hotdocs_init.run(
        argv,
        tool_root=tool_root,
        input_fn=lambda prompt: "",
        output_fn=out,
        env={},
        cwd=tmp_path,
    )
    return rc, out


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


def test_example_copies_slugs_and_prints_next_steps(tmp_path, capsys):
    tool_root, _ = setup(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    rc, out = do_run([str(project), "--example", "--yes"], tool_root, tmp_path)
    assert rc in (0, 3), rc

    copied = project / "specs" / "product" / "slugs.md"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == EXAMPLE_TEXT
    assert not (project / "examples").exists()

    # the tool's own example is untouched
    assert (tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md").read_text(
        encoding="utf-8"
    ) == EXAMPLE_TEXT

    lines = out.lines()
    lint_idx = [i for i, l in enumerate(lines) if "hotdocs lint" in l]
    assert lint_idx, out.text()
    tail = "\n".join(lines[lint_idx[-1]:])
    for needle in ("hotdocs lint", "hotdocs generate comp-slugify", "hotdocs verify", "QUICKSTART.md"):
        assert needle in tail, (needle, out.text())


def test_example_never_overwrites_existing_file(tmp_path):
    tool_root, _ = setup(tmp_path)
    project = tmp_path / "project"
    target = project / "specs" / "product" / "slugs.md"
    target.parent.mkdir(parents=True)
    mine = "# My own slugs\n"
    target.write_text(mine, encoding="utf-8")

    rc, out = do_run([str(project), "--example", "--yes"], tool_root, tmp_path)
    assert rc != 2, out.text()
    assert target.read_text(encoding="utf-8") == mine
    assert not (project / "examples").exists()


def test_no_example_next_steps_omit_comp_slugify(tmp_path, capsys):
    tool_root, _ = setup(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    rc, out = do_run([str(project), "--yes"], tool_root, tmp_path)
    assert rc in (0, 3), rc
    captured = capsys.readouterr()
    assert "comp-slugify" not in out.text()
    assert "comp-slugify" not in captured.out
    assert "hotdocs lint" in out.text()
    assert "hotdocs verify" in out.text()
    assert "QUICKSTART.md" in out.text()
    assert not (project / "specs" / "product" / "slugs.md").exists()


def test_reconfigure_changes_only_hotdocs_toml(tmp_path):
    tool_root, log_path = setup(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    rc, out = do_run(
        [str(project), "--yes", "--provider", "openai", "--model", "m0", "--no-test"],
        tool_root,
        tmp_path,
    )
    assert rc in (0, 3), (rc, out.text())
    assert (project / ".hotdocs-tool.json").is_file()
    assert (project / "hotdocs.toml").is_file()

    before = snapshot(project)
    before_tool = snapshot(tool_root)
    log_lines_before = len(read_log(log_path))

    rc, out = do_run(
        [str(project), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root,
        tmp_path,
    )
    assert rc == 0, (rc, out.text())

    after = snapshot(project)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed == {"hotdocs.toml"}, changed
    assert snapshot(tool_root) == before_tool

    new_calls = read_log(log_path)[log_lines_before:]
    saves = [c for c in new_calls if c["call"] == "save_config"]
    assert saves, new_calls
    assert saves[-1]["provider"] == "openai"
    assert saves[-1]["model"] == "m"
    assert Path(saves[-1]["config_path"]).resolve() == (project / "hotdocs.toml").resolve()


def test_reconfigure_without_llm_endpoint_returns_1(tmp_path):
    tool_root, _ = setup(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    rc, out = do_run(
        [str(project), "--yes", "--provider", "openai", "--model", "m0", "--no-test"],
        tool_root,
        tmp_path,
    )
    assert rc in (0, 3), (rc, out.text())
    assert (project / ".hotdocs-tool.json").is_file()
    assert (project / "hotdocs.toml").is_file()

    bare_root, _ = setup(tmp_path, with_endpoint=False, name="bare-tool")
    assert not (bare_root / "gen" / "llm-endpoint" / "llm_endpoint.py").exists()
    assert not (bare_root / "gen" / "llm-endpoint" / "llm_endpoint" / "__init__.py").exists()

    rc, out = do_run(
        [str(project), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        bare_root,
        tmp_path,
    )
    assert rc == 1, (rc, out.text())


def test_reconfigure_on_uninitialised_dir_returns_1_and_writes_nothing(tmp_path):
    tool_root, _ = setup(tmp_path)
    project = tmp_path / "project"
    (project / "specs").mkdir(parents=True)

    before = snapshot(project)
    before_tool = snapshot(tool_root)

    rc, out = do_run(
        [str(project), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root,
        tmp_path,
    )
    assert rc == 1, (rc, out.text())
    assert snapshot(project) == before
    assert snapshot(tool_root) == before_tool
    assert not (project / "hotdocs.toml").exists()
    assert not (project / ".hotdocs-tool.json").exists()