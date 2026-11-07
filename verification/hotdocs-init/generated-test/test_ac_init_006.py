import importlib.metadata
from pathlib import Path

import hotdocs_init


LLM_ENDPOINT_TEMPLATE = '''import json
from pathlib import Path

LOG_PATH = "__LOG_PATH__"


def _log(call, data):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        record = {"call": call}
        record.update(data)
        f.write(json.dumps(record) + "\\n")


PROVIDERS = {
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.1:8b",
    },
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4o-mini",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"env_given": env is not None, "probe_ollama": probe_ollama})
    return [
        {
            "provider": "ollama",
            "available": True,
            "reason": "local server found",
            "suggested_model": "llama3.1:8b",
            "api_key_env": None,
        },
        {
            "provider": "openai",
            "available": False,
            "reason": "OPENAI_API_KEY not set",
            "suggested_model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
        },
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url is required for " + str(provider))
    _log("check_connection", {"provider": provider, "model": model})
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    path = Path(config_path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "[llm]":
            start = i
            end = len(lines)
            for j in range(i + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped.startswith("[") and stripped != "[llm]":
                    end = j
                    break
            break
    new_block = ["[llm]", 'provider = "' + provider + '"', 'model = "' + model + '"']
    if base_url is not None:
        new_block.append('base_url = "' + base_url + '"')
    if api_key_env is not None:
        new_block.append('api_key_env = "' + api_key_env + '"')
    if timeout_seconds is not None:
        new_block.append("timeout_seconds = " + str(int(timeout_seconds)))
    if start is None:
        lines = lines + new_block
    else:
        lines = lines[:start] + new_block + lines[end:]
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    _log("save_config", {"provider": provider, "model": model})


def load_config(config_path=None):
    path = Path(config_path) if config_path else Path("hotdocs.toml")
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    result = None
    for i, line in enumerate(lines):
        if line.strip() == "[llm]":
            result = {
                "provider": None,
                "model": None,
                "base_url": None,
                "api_key_env": None,
                "timeout_seconds": None,
            }
            for j in range(i + 1, len(lines)):
                candidate = lines[j].strip()
                if candidate.startswith("[") and candidate != "[llm]":
                    break
                if not candidate or "=" not in candidate:
                    continue
                key, _, value = candidate.partition("=")
                key = key.strip()
                value = value.strip().strip('"')
                if key == "timeout_seconds" and value:
                    result[key] = int(value)
                elif key in result:
                    result[key] = value
            break
    _log("load_config", {"config_path": str(path)})
    return result
'''


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _snapshot(base: Path) -> dict:
    snap = {}
    for p in base.rglob("*"):
        if p.is_file():
            snap[p.relative_to(base)] = p.read_bytes()
    return snap


def _make_tool_root(root_dir: Path, log_path: Path) -> Path:
    tool_root = root_dir / "tool_root"
    module_src = LLM_ENDPOINT_TEMPLATE.replace(
        "__LOG_PATH__", str(log_path).replace("\\", "\\\\")
    )
    _write(tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py", module_src)
    _write(
        tool_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "# fake criterion-compiler fixture, unused by this test\n",
    )
    _write(
        tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md",
        "# Slugify example\n\nCanonical example product spec for comp-slugify.\n",
    )
    version = importlib.metadata.version("pytest")
    _write(tool_root / "requirements.txt", "pytest==" + version + "\n")
    return tool_root


def _make_output_collector():
    lines = []

    def output_fn(*args):
        lines.append(" ".join(str(a) for a in args))

    return lines, output_fn


def _deny_input(prompt):
    raise AssertionError("init should not prompt when --yes is given: " + repr(prompt))


def test_example_flag_copies_slugs_and_next_steps_mention_generate(tmp_path):
    tool_root = _make_tool_root(tmp_path, tmp_path / "call_log_1.jsonl")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    output_lines, output_fn = _make_output_collector()

    rc = hotdocs_init.main(
        [str(project_dir), "--example", "--yes"],
        tool_root=str(tool_root),
        input_fn=_deny_input,
        output_fn=output_fn,
        env={},
        cwd=str(project_dir),
    )

    assert rc == 0

    slugs_path = project_dir / "specs" / "product" / "slugs.md"
    example_path = tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    assert slugs_path.exists()
    assert slugs_path.read_text(encoding="utf-8") == example_path.read_text(encoding="utf-8")
    assert not (project_dir / "examples").exists()

    tail = "\n".join(output_lines[-15:])
    for needle in ("hotdocs lint", "hotdocs generate comp-slugify", "hotdocs verify", "QUICKSTART.md"):
        assert needle in tail, "expected %r near the end of output, got: %r" % (needle, tail)


def test_example_never_overwrites_existing_file(tmp_path):
    tool_root = _make_tool_root(tmp_path, tmp_path / "call_log_2.jsonl")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    slugs_path = project_dir / "specs" / "product" / "slugs.md"
    slugs_path.parent.mkdir(parents=True)
    sentinel = "MY PRE-EXISTING PRODUCT SPEC\n"
    slugs_path.write_text(sentinel, encoding="utf-8")
    _, output_fn = _make_output_collector()

    rc = hotdocs_init.main(
        [str(project_dir), "--example", "--yes"],
        tool_root=str(tool_root),
        input_fn=_deny_input,
        output_fn=output_fn,
        env={},
        cwd=str(project_dir),
    )

    assert rc == 0
    assert slugs_path.read_text(encoding="utf-8") == sentinel
    assert (project_dir / "gen" / "llm-endpoint" / "llm_endpoint.py").exists()


def test_no_example_next_steps_omit_comp_slugify(tmp_path):
    tool_root = _make_tool_root(tmp_path, tmp_path / "call_log_3.jsonl")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    output_lines, output_fn = _make_output_collector()

    rc = hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=str(tool_root),
        input_fn=_deny_input,
        output_fn=output_fn,
        env={},
        cwd=str(project_dir),
    )

    assert rc == 0
    output = "\n".join(output_lines)
    assert "comp-slugify" not in output


def test_reconfigure_changes_only_toml_and_requires_llm_endpoint(tmp_path):
    tool_root = _make_tool_root(tmp_path, tmp_path / "call_log_4.jsonl")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _, setup_output_fn = _make_output_collector()

    rc_setup = hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=str(tool_root),
        input_fn=_deny_input,
        output_fn=setup_output_fn,
        env={},
        cwd=str(project_dir),
    )
    assert rc_setup == 0
    assert (project_dir / "gen" / "llm-endpoint" / "llm_endpoint.py").exists()

    before = _snapshot(project_dir)

    _, reconfig_output_fn = _make_output_collector()
    rc = hotdocs_init.main(
        [str(project_dir), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=str(tool_root),
        input_fn=_deny_input,
        output_fn=reconfig_output_fn,
        env={},
        cwd=str(project_dir),
    )
    assert rc == 0

    after = _snapshot(project_dir)
    changed = {rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel)}
    assert changed == {Path("hotdocs.toml")}

    toml_text = (project_dir / "hotdocs.toml").read_text(encoding="utf-8")
    assert 'provider = "openai"' in toml_text
    assert 'model = "m"' in toml_text

    bare_dir = tmp_path / "bare"
    bare_dir.mkdir()
    _, bare_output_fn = _make_output_collector()
    rc_missing = hotdocs_init.main(
        [str(bare_dir), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=str(tool_root),
        input_fn=_deny_input,
        output_fn=bare_output_fn,
        env={},
        cwd=str(bare_dir),
    )
    assert rc_missing == 1