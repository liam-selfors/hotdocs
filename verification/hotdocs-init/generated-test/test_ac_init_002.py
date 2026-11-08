import importlib.metadata
import json
import os
from pathlib import Path

import hotdocs_init


def _write_fake_llm_endpoint(path, log_path):
    content = (
        "import json\n"
        "from pathlib import Path\n\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n\n\n"
        "def _log(name):\n"
        "    with open(LOG_PATH, \"a\", encoding=\"utf-8\") as f:\n"
        "        f.write(name + \"\\n\")\n\n\n"
        "PROVIDERS = {\n"
        "    \"openai-compatible\": {\n"
        "        \"default_base_url\": None,\n"
        "        \"default_api_key_env\": None,\n"
        "        \"needs_base_url\": True,\n"
        "        \"suggested_model\": \"\",\n"
        "    },\n"
        "}\n\n\n"
        "def detect_providers(env=None, probe_ollama=True):\n"
        "    _log(\"detect_providers\")\n"
        "    return []\n\n\n"
        "def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):\n"
        "    _log(\"check_connection\")\n"
        "    return {\"ok\": True, \"error\": None}\n\n\n"
        "def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):\n"
        "    _log(\"save_config\")\n"
        "    Path(config_path).write_text(\"[llm]\\n\", encoding=\"utf-8\")\n\n\n"
        "def load_config(config_path=None):\n"
        "    _log(\"load_config\")\n"
        "    return None\n"
    )
    path.write_text(content, encoding="utf-8")


def _make_fake_tool_root(base, log_path):
    tool_root = base / "tool_root"
    (tool_root / "gen" / "llm-endpoint").mkdir(parents=True)
    _write_fake_llm_endpoint(
        tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py", log_path
    )

    (tool_root / "gen" / "a-b").mkdir(parents=True)
    (tool_root / "gen" / "a-b" / "a_b.py").write_text(
        "# fake a-b module\n", encoding="utf-8"
    )

    (tool_root / "examples" / "slugify" / "specs" / "product").mkdir(parents=True)
    (tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md").write_text(
        "# Slugs\n\nFake example fixture content.\n", encoding="utf-8"
    )

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + pytest_version + "\n", encoding="utf-8"
    )

    return tool_root


def _snapshot(root):
    entries = set()
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            entries.add(os.path.relpath(os.path.join(dirpath, name), root))
    return entries


def _assert_no_pycache(root):
    for dirpath, dirnames, filenames in os.walk(root):
        assert "__pycache__" not in dirnames


def _no_input(prompt):
    raise AssertionError("init should not prompt before refusing")


def _permissive_input(prompt):
    return ""


def test_fresh_init_creates_empty_gen_and_marker_then_rerun_is_idempotent(tmp_path):
    log_path = tmp_path / "llm_calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)
    target = tmp_path / "project"
    target.mkdir()

    exit_code_1 = hotdocs_init.main(
        [str(target), "--yes", "--no-test"],
        tool_root=tool_root,
        input_fn=_permissive_input,
        output_fn=lambda msg: None,
        env={},
        cwd=str(target),
    )

    gen_dir = target / "gen"
    assert gen_dir.is_dir()
    assert os.listdir(gen_dir) == []
    assert not (target / "pipeline").exists()

    marker_path = target / ".hotdocs-tool.json"
    assert marker_path.is_file()
    with open(marker_path, "r", encoding="utf-8") as f:
        marker = json.load(f)
    assert marker == {"tool_version": "0.1.0"}
    assert exit_code_1 in (0, 3)

    first_bytes = marker_path.read_bytes()
    first_mtime = marker_path.stat().st_mtime

    exit_code_2 = hotdocs_init.main(
        [str(target), "--yes", "--no-test"],
        tool_root=tool_root,
        input_fn=_permissive_input,
        output_fn=lambda msg: None,
        env={},
        cwd=str(target),
    )

    second_bytes = marker_path.read_bytes()
    second_mtime = marker_path.stat().st_mtime
    assert second_bytes == first_bytes
    assert second_mtime == first_mtime

    assert gen_dir.is_dir()
    assert os.listdir(gen_dir) == []
    assert exit_code_2 in (0, 3)


def test_gen_collision_refuses_names_colliding_dir_only_and_writes_nothing(
    tmp_path, capsys
):
    log_path = tmp_path / "llm_calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)

    target = tmp_path / "project"
    (target / "gen" / "a-b").mkdir(parents=True)
    (target / "gen" / "a-b" / "placeholder.txt").write_text(
        "existing\n", encoding="utf-8"
    )
    (target / "gen" / "mine").mkdir(parents=True)
    (target / "gen" / "mine" / "placeholder.txt").write_text(
        "mine\n", encoding="utf-8"
    )

    before = _snapshot(target)

    exit_code = hotdocs_init.main(
        [str(target), "--yes", "--no-test"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=lambda msg: None,
        env={},
        cwd=str(target),
    )

    stderr_text = capsys.readouterr().err

    assert exit_code == 1
    assert "gen/a-b" in stderr_text
    assert "gen/mine" not in stderr_text

    after = _snapshot(target)
    assert after == before

    assert not (target / ".hotdocs-tool.json").exists()
    assert not (target / "hotdocs.toml").exists()
    assert not log_path.exists()

    _assert_no_pycache(target)
    _assert_no_pycache(tool_root)


def test_target_is_tool_root_refuses_and_writes_nothing(tmp_path):
    log_path = tmp_path / "llm_calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)

    before = _snapshot(tool_root)

    exit_code = hotdocs_init.main(
        [str(tool_root), "--yes", "--no-test"],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=lambda msg: None,
        env={},
        cwd=str(tool_root),
    )

    assert exit_code == 1

    after = _snapshot(tool_root)
    assert after == before

    assert not (tool_root / ".hotdocs-tool.json").exists()
    assert not (tool_root / "hotdocs.toml").exists()
    assert not log_path.exists()

    _assert_no_pycache(tool_root)