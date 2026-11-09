import importlib.metadata
import json

import hotdocs_init


LLM_ENDPOINT_TEMPLATE = '''
import json
import pathlib

PROVIDERS = {
    "openai": {
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4o-mini",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
}

_LOG_PATH = "__LOG_PATH__"


def _log(name, info):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps({"call": name, "info": info}, default=str) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"env": env, "probe_ollama": probe_ollama})
    return [
        {
            "provider": "openai",
            "available": True,
            "reason": None,
            "suggested_model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
        }
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection", {"provider": provider, "model": model})
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config", {"config_path": str(config_path), "provider": provider, "model": model})
    path = pathlib.Path(config_path)
    existing = path.read_text() if path.exists() else ""
    kept = []
    in_llm = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped == "[llm]":
            in_llm = True
            continue
        if in_llm and stripped.startswith("[") and stripped != "[llm]":
            in_llm = False
        if not in_llm:
            kept.append(line)
    lines = list(kept)
    lines.append("[llm]")
    lines.append('provider = "' + provider + '"')
    lines.append('model = "' + model + '"')
    if base_url is not None:
        lines.append('base_url = "' + base_url + '"')
    if api_key_env is not None:
        lines.append('api_key_env = "' + api_key_env + '"')
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(timeout_seconds))
    path.write_text("\\n".join(lines) + "\\n")


def load_config(config_path=None):
    _log("load_config", {"config_path": str(config_path) if config_path else None})
    if config_path is None:
        return None
    path = pathlib.Path(config_path)
    if not path.exists():
        return None
    text = path.read_text()
    if "[llm]" not in text:
        return None
    result = {
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
    }
    in_llm = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[llm]":
            in_llm = True
            continue
        if in_llm and stripped.startswith("[") and stripped != "[llm]":
            break
        if in_llm and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            if key == "timeout_seconds":
                result[key] = int(value) if value else None
            else:
                result[key] = value if value else None
    return result
'''


def write_fake_llm_endpoint(dest_path, log_path):
    content = LLM_ENDPOINT_TEMPLATE.replace(
        "__LOG_PATH__", str(log_path).replace("\\", "\\\\")
    )
    dest_path.write_text(content)


def build_fake_tool_root(tool_root, log_path, include_llm_endpoint=True):
    tool_root.mkdir(parents=True, exist_ok=True)
    if include_llm_endpoint:
        llm_dir = tool_root / "gen" / "llm-endpoint"
        llm_dir.mkdir(parents=True, exist_ok=True)
        write_fake_llm_endpoint(llm_dir / "llm_endpoint.py", log_path)
    example_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    example_dir.mkdir(parents=True, exist_ok=True)
    (example_dir / "slugs.md").write_text(
        '# Example slugs\n\nslugify("Hello World") -> "hello-world"\n'
    )
    requirements_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + requirements_version + "\n"
    )
    return tool_root


def snapshot(root):
    result = {}
    for path in root.rglob("*"):
        if path.is_file():
            result[str(path.relative_to(root))] = path.read_bytes()
    return result


def changed_paths(before, after):
    changed = set()
    for key in before.keys() | after.keys():
        if before.get(key) != after.get(key):
            changed.add(key)
    return changed


def read_log(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def test_example_copies_slugs_and_ends_with_full_next_steps(tmp_path):
    tool_root = build_fake_tool_root(tmp_path / "tool_root", tmp_path / "calls.log")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--example", "--yes"],
        tool_root=str(tool_root),
        input_fn=lambda prompt: "",
        output_fn=outputs.append,
        env={},
    )

    slugs_path = project_dir / "specs" / "product" / "slugs.md"
    example_path = tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    assert slugs_path.exists()
    assert slugs_path.read_text() == example_path.read_text()
    assert not (project_dir / "examples").exists()

    full_output = "\n".join(outputs)
    idx_lint = full_output.find("hotdocs lint")
    idx_generate = full_output.find("hotdocs generate comp-slugify")
    idx_verify = full_output.find("hotdocs verify")
    idx_quickstart = full_output.find("QUICKSTART.md")
    assert idx_lint != -1
    assert idx_generate != -1
    assert idx_verify != -1
    assert idx_quickstart != -1
    assert idx_lint < idx_generate < idx_verify < idx_quickstart


def test_example_never_overwrites_existing_file(tmp_path):
    tool_root = build_fake_tool_root(tmp_path / "tool_root", tmp_path / "calls.log")
    project_dir = tmp_path / "project"
    (project_dir / "specs" / "product").mkdir(parents=True)
    custom_content = "custom pre-existing content\n"
    (project_dir / "specs" / "product" / "slugs.md").write_text(custom_content)

    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--example", "--yes"],
        tool_root=str(tool_root),
        input_fn=lambda prompt: "",
        output_fn=outputs.append,
        env={},
    )

    assert (
        project_dir / "specs" / "product" / "slugs.md"
    ).read_text() == custom_content


def test_no_example_next_steps_omit_comp_slugify(tmp_path):
    tool_root = build_fake_tool_root(tmp_path / "tool_root", tmp_path / "calls.log")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    outputs = []
    hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=str(tool_root),
        input_fn=lambda prompt: "",
        output_fn=outputs.append,
        env={},
    )

    full_output = "\n".join(outputs)
    assert "comp-slugify" not in full_output


def test_reconfigure_changes_only_hotdocs_toml(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = build_fake_tool_root(tmp_path / "tool_root", log_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".hotdocs-tool.json").write_text('{"version": "1"}\n')
    (project_dir / "hotdocs.toml").write_text('[project]\nname = "demo"\n')
    specs_dir = project_dir / "specs"
    specs_dir.mkdir()
    (specs_dir / "note.md").write_text("unrelated content\n")

    before = snapshot(project_dir)

    hotdocs_init.main(
        [str(project_dir), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=str(tool_root),
        input_fn=lambda prompt: "",
        output_fn=lambda *a, **k: None,
        env={},
    )

    after = snapshot(project_dir)
    assert changed_paths(before, after) == {"hotdocs.toml"}

    records = read_log(log_path)
    save_calls = [r for r in records if r.get("call") == "save_config"]
    assert any(
        r["info"].get("provider") == "openai" and r["info"].get("model") == "m"
        for r in save_calls
    )


def test_reconfigure_fails_without_llm_endpoint_module(tmp_path):
    tool_root_missing = build_fake_tool_root(
        tmp_path / "tool_root_missing",
        tmp_path / "calls_missing.log",
        include_llm_endpoint=False,
    )
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".hotdocs-tool.json").write_text('{"version": "1"}\n')
    (project_dir / "hotdocs.toml").write_text('[project]\nname = "demo"\n')

    result = hotdocs_init.main(
        [str(project_dir), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=str(tool_root_missing),
        input_fn=lambda prompt: "",
        output_fn=lambda *a, **k: None,
        env={},
    )

    assert result == 1


def test_reconfigure_on_uninitialised_project_returns_1_and_writes_nothing(tmp_path):
    tool_root = build_fake_tool_root(tmp_path / "tool_root", tmp_path / "calls.log")
    project_dir = tmp_path / "project"
    (project_dir / "specs").mkdir(parents=True)
    (project_dir / "specs" / "placeholder.md").write_text("x\n")

    before = snapshot(project_dir)

    result = hotdocs_init.main(
        [str(project_dir), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=str(tool_root),
        input_fn=lambda prompt: "",
        output_fn=lambda *a, **k: None,
        env={},
    )

    after = snapshot(project_dir)
    assert result == 1
    assert before == after