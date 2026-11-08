import importlib.metadata
import os
import shutil
from pathlib import Path

import hotdocs_init


def _llm_endpoint_source(log_path):
    return f"""
LOG_PATH = {repr(str(log_path))}


def _log(name):
    with open(LOG_PATH, "a") as f:
        f.write(name + "\\n")


PROVIDERS = {{
    "openai": {{
        "default_base_url": None,
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-4",
    }},
}}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
    return [
        {{
            "provider": "openai",
            "available": True,
            "reason": "ok",
            "suggested_model": "gpt-4",
            "api_key_env": "OPENAI_API_KEY",
        }}
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection")
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    return {{"ok": True, "error": None}}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config")
    path = config_path
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    lines = content.splitlines(keepends=True)
    out = []
    in_llm = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = (stripped == "[llm]")
            if in_llm:
                continue
            out.append(line)
            continue
        if in_llm:
            continue
        out.append(line)
    out.append("[llm]\\n")
    out.append('provider = "' + str(provider) + '"\\n')
    out.append('model = "' + str(model) + '"\\n')
    if base_url is not None:
        out.append('base_url = "' + str(base_url) + '"\\n')
    if api_key_env is not None:
        out.append('api_key_env = "' + str(api_key_env) + '"\\n')
    if timeout_seconds is not None:
        out.append('timeout_seconds = ' + str(timeout_seconds) + '\\n')
    with open(path, "w") as f:
        f.writelines(out)


def load_config(config_path=None):
    _log("load_config")
    if config_path is None:
        return None
    try:
        with open(config_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return None
    if "[llm]" not in content:
        return None
    result = {{
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
    }}
    in_llm = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[llm]":
            in_llm = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = False
            continue
        if in_llm and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            if key == "timeout_seconds":
                try:
                    value = int(value)
                except ValueError:
                    pass
            if key in result:
                result[key] = value
    return result
"""


def _make_tool_root(tmp_path, log_path, name, include_llm_endpoint=True):
    tool_root = tmp_path / name
    gen_dir = tool_root / "gen"
    gen_dir.mkdir(parents=True)
    if include_llm_endpoint:
        module_dir = gen_dir / "llm-endpoint"
        module_dir.mkdir(parents=True)
        (module_dir / "llm_endpoint.py").write_text(_llm_endpoint_source(log_path))

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text("pytest==" + pytest_version + "\n")

    example_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    example_dir.mkdir(parents=True)
    (example_dir / "slugs.md").write_text("EXAMPLE SLUGS CONTENT\n")

    return tool_root


def _run(argv, tool_root, cwd):
    output_lines = []

    def output_fn(*args, **kwargs):
        output_lines.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        return "y"

    rc = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={"PATH": os.environ.get("PATH", "")},
        cwd=str(cwd),
    )
    return rc, "\n".join(output_lines)


def _snapshot(root):
    result = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(root))
            result[rel] = path.read_bytes()
    return result


def test_example_copies_slugs_never_overwrites_and_next_steps(tmp_path):
    log_path = tmp_path / "llm_calls_1.log"
    tool_root = _make_tool_root(tmp_path, log_path, "tool_root_1")

    project_dir = tmp_path / "project_fresh"
    project_dir.mkdir()
    rc, out_text = _run(
        [str(project_dir), "--example", "--yes"],
        tool_root=tool_root,
        cwd=project_dir,
    )
    assert rc == 0

    slugs_path = project_dir / "specs" / "product" / "slugs.md"
    assert slugs_path.exists()
    example_content = (
        tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    ).read_text()
    assert slugs_path.read_text() == example_content
    assert not (project_dir / "examples").exists()

    lint_idx = out_text.find("hotdocs lint")
    generate_idx = out_text.find("hotdocs generate comp-slugify")
    verify_idx = out_text.find("hotdocs verify")
    quickstart_idx = out_text.find("QUICKSTART.md")
    assert lint_idx != -1
    assert generate_idx != -1
    assert verify_idx != -1
    assert quickstart_idx != -1
    assert lint_idx < generate_idx < verify_idx < quickstart_idx

    non_empty_lines = [line for line in out_text.splitlines() if line.strip()]
    assert non_empty_lines, "expected some output"
    assert "QUICKSTART.md" in non_empty_lines[-1]

    project_dir2 = tmp_path / "project_preexisting"
    (project_dir2 / "specs" / "product").mkdir(parents=True)
    sentinel = "PRE-EXISTING SLUGS CONTENT\n"
    (project_dir2 / "specs" / "product" / "slugs.md").write_text(sentinel)

    rc2, _ = _run(
        [str(project_dir2), "--example", "--yes"],
        tool_root=tool_root,
        cwd=project_dir2,
    )
    assert rc2 == 0
    assert (project_dir2 / "specs" / "product" / "slugs.md").read_text() == sentinel


def test_no_example_next_steps_omit_comp_slugify(tmp_path):
    log_path = tmp_path / "llm_calls_2.log"
    tool_root = _make_tool_root(tmp_path, log_path, "tool_root_2")

    project_dir = tmp_path / "project_no_example"
    project_dir.mkdir()
    rc, out_text = _run(
        [str(project_dir), "--yes"],
        tool_root=tool_root,
        cwd=project_dir,
    )
    assert rc == 0
    assert "comp-slugify" not in out_text


def test_reconfigure_only_touches_hotdocs_toml_and_fails_without_llm_endpoint(tmp_path):
    log_path = tmp_path / "llm_calls_3.log"
    tool_root = _make_tool_root(tmp_path, log_path, "tool_root_3")

    project_dir = tmp_path / "project_init"
    project_dir.mkdir()

    rc, _ = _run(
        [str(project_dir), "--yes", "--no-test"],
        tool_root=tool_root,
        cwd=project_dir,
    )
    assert rc == 0

    project_dir_missing = tmp_path / "project_init_missing"
    shutil.copytree(project_dir, project_dir_missing)

    snapshot_before = _snapshot(project_dir)

    rc2, _ = _run(
        [str(project_dir), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=tool_root,
        cwd=project_dir,
    )
    assert rc2 == 0

    snapshot_after = _snapshot(project_dir)

    changed = set()
    for key in set(snapshot_before) | set(snapshot_after):
        if snapshot_before.get(key) != snapshot_after.get(key):
            changed.add(key)
    assert changed == {"hotdocs.toml"}

    log_path_missing = tmp_path / "llm_calls_missing.log"
    tool_root_missing = _make_tool_root(
        tmp_path, log_path_missing, "tool_root_missing", include_llm_endpoint=False
    )

    rc3, _ = _run(
        [str(project_dir_missing), "--reconfigure", "--provider", "openai", "--model", "m", "--no-test"],
        tool_root=tool_root_missing,
        cwd=project_dir_missing,
    )
    assert rc3 == 1