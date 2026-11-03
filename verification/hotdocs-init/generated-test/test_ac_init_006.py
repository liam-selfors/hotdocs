import json
import os
from pathlib import Path

import hotdocs_init


_LLM_ENDPOINT_TEMPLATE = r'''
import json
import os

LOG_PATH = __LOG_PATH__

PROVIDERS = {
    "openai": {"default_base_url": "https://api.openai.com/v1", "default_api_key_env": "OPENAI_API_KEY", "needs_base_url": False, "suggested_model": "gpt-4"},
    "openai-compatible": {"default_base_url": "", "default_api_key_env": "", "needs_base_url": True, "suggested_model": ""},
    "ollama": {"default_base_url": "http://localhost:11434", "default_api_key_env": "", "needs_base_url": False, "suggested_model": "llama3.1:8b"},
}


def _log(call, **kwargs):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"call": call, "kwargs": {k: str(v) for k, v in kwargs.items()}}) + "\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", has_env=bool(env), probe_ollama=probe_ollama)
    return [
        {"provider": "openai", "available": True, "reason": "ok", "suggested_model": "gpt-4", "api_key_env": "OPENAI_API_KEY"},
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection", provider=provider, model=model)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required for " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config", provider=provider, model=model)
    config_path = str(config_path)
    existing_lines = []
    if os.path.exists(config_path):
        with open(config_path) as f:
            content = f.read()
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].strip() == "[llm]":
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("["):
                    i += 1
                continue
            existing_lines.append(lines[i])
            i += 1
    while existing_lines and existing_lines[-1].strip() == "":
        existing_lines.pop()
    new_section = [
        "[llm]",
        "provider = \"" + str(provider) + "\"",
        "model = \"" + str(model) + "\"",
        "base_url = \"" + str(base_url or "") + "\"",
        "api_key_env = \"" + str(api_key_env or "") + "\"",
        "timeout_seconds = " + str(timeout_seconds if timeout_seconds is not None else 0),
    ]
    out = existing_lines + ([""] if existing_lines else []) + new_section
    with open(config_path, "w") as f:
        f.write("\n".join(out) + "\n")


def load_config(config_path=None):
    _log("load_config")
    if config_path is None:
        return None
    config_path = str(config_path)
    if not os.path.exists(config_path):
        return None
    with open(config_path) as f:
        content = f.read()
    if "[llm]" not in content:
        return None
    lines = content.splitlines()
    result = {"provider": None, "model": None, "base_url": None, "api_key_env": None, "timeout_seconds": None}
    in_section = False
    for line in lines:
        s = line.strip()
        if s == "[llm]":
            in_section = True
            continue
        if in_section:
            if s.startswith("["):
                break
            if "=" in s:
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"')
                if k == "timeout_seconds":
                    result[k] = int(v) if v else None
                else:
                    result[k] = v if v else None
    return result
'''


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_fake_tool_root(base: Path, log_path: Path) -> Path:
    tool_root = base / "tool_root"
    module_source = _LLM_ENDPOINT_TEMPLATE.replace(
        "__LOG_PATH__", json.dumps(str(log_path))
    )
    _write(tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py", module_source)
    _write(
        tool_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "def compile_criterion(*args, **kwargs):\n    raise NotImplementedError\n",
    )
    _write(
        tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md",
        "# Example Slugs\n\nThis is the example slugs content.\n",
    )
    _write(tool_root / "requirements.txt", "pytest\n")
    return tool_root


def _collecting_output():
    lines = []

    def output_fn(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        lines.append(sep.join(str(a) for a in args))

    return lines, output_fn


def _snapshot(root: Path):
    snap = {}
    for p in root.rglob("*"):
        if p.is_file():
            snap[p.relative_to(root)] = p.read_bytes()
    return snap


def test_example_copies_slugs_and_next_steps_mention_everything(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    lines, output_fn = _collecting_output()
    rc = hotdocs_init.main(
        [str(project_dir), "--example", "--yes"],
        tool_root=tool_root,
        output_fn=output_fn,
        env={},
    )
    assert rc in (0, 3)

    slugs_path = project_dir / "specs" / "product" / "slugs.md"
    assert slugs_path.exists()
    example_source = tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    assert slugs_path.read_text() == example_source.read_text()

    assert not (project_dir / "examples").exists()

    full_output = "\n".join(lines)
    assert "hotdocs lint" in full_output
    assert "hotdocs generate comp-slugify" in full_output
    assert "hotdocs verify" in full_output
    assert "QUICKSTART.md" in full_output

    tail = "\n".join(lines[-12:])
    assert "hotdocs lint" in tail
    assert "hotdocs generate comp-slugify" in tail
    assert "hotdocs verify" in tail
    assert "QUICKSTART.md" in tail


def test_example_existing_file_never_overwritten(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    slugs_path = project_dir / "specs" / "product" / "slugs.md"
    sentinel = "SENTINEL CONTENT THAT MUST SURVIVE\n"
    _write(slugs_path, sentinel)

    _, output_fn = _collecting_output()
    rc = hotdocs_init.main(
        [str(project_dir), "--example", "--yes"],
        tool_root=tool_root,
        output_fn=output_fn,
        env={},
    )
    assert rc in (0, 3)
    assert slugs_path.read_text() == sentinel


def test_without_example_next_steps_omit_comp_slugify(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    lines, output_fn = _collecting_output()
    rc = hotdocs_init.main(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        output_fn=output_fn,
        env={},
    )
    assert rc in (0, 3)

    full_output = "\n".join(lines)
    assert "comp-slugify" not in full_output
    assert "hotdocs lint" in full_output
    assert "hotdocs verify" in full_output
    assert "QUICKSTART.md" in full_output


def test_reconfigure_changes_only_hotdocs_toml(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    _, setup_output_fn = _collecting_output()
    rc = hotdocs_init.main(
        [str(project_dir), "--yes", "--no-test"],
        tool_root=tool_root,
        output_fn=setup_output_fn,
        env={},
    )
    assert rc in (0, 3)

    toml_path = project_dir / "hotdocs.toml"
    assert toml_path.exists()

    before = _snapshot(project_dir)

    _, reconf_output_fn = _collecting_output()
    rc2 = hotdocs_init.main(
        [str(project_dir), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=tool_root,
        output_fn=reconf_output_fn,
        env={},
    )
    assert rc2 == 0

    after = _snapshot(project_dir)

    assert set(before.keys()) == set(after.keys())
    changed = {path for path in before if before[path] != after[path]}
    assert changed == {Path("hotdocs.toml")}

    new_toml_text = toml_path.read_text()
    assert "openai" in new_toml_text
    assert "m" in new_toml_text


def test_reconfigure_without_llm_endpoint_module_returns_1(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    _, setup_output_fn = _collecting_output()
    rc = hotdocs_init.main(
        [str(project_dir), "--yes", "--no-test"],
        tool_root=tool_root,
        output_fn=setup_output_fn,
        env={},
    )
    assert rc in (0, 3)

    llm_endpoint_module = project_dir / "gen" / "llm-endpoint" / "llm_endpoint.py"
    assert llm_endpoint_module.exists()
    llm_endpoint_module.unlink()

    _, reconf_output_fn = _collecting_output()
    rc2 = hotdocs_init.main(
        [str(project_dir), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=tool_root,
        output_fn=reconf_output_fn,
        env={},
    )
    assert rc2 == 1