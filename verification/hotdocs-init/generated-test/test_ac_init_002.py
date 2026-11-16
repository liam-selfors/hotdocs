import importlib.metadata
import json
import os
from pathlib import Path

import pytest

import hotdocs_init


TOOL_VERSION = "0.1.0"


FAKE_LLM_ENDPOINT_TEMPLATE = r'''
import json
import os

_LOG_PATH = __LOG_PATH__


def _log(name, **kwargs):
    record = {"call": name}
    for key, value in kwargs.items():
        record[key] = repr(value)
    with open(_LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


_log("import")


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
    result = []
    for name, info in PROVIDERS.items():
        available = name == "ollama"
        result.append({
            "provider": name,
            "available": available,
            "reason": "reachable" if available else "not configured",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30):
    _log("check_connection", provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("provider %s needs a base_url" % provider)
    return {"ok": True, "error": None}


def _quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None):
    _log("save_config", config_path=str(config_path), provider=provider,
         model=model, base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    if not model:
        raise ValueError("model is required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("provider %s needs a base_url" % provider)
    path = os.fspath(config_path)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    kept = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            in_llm = False
            for line in handle.read().splitlines():
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_llm = stripped == "[llm]"
                    if in_llm:
                        continue
                if not in_llm:
                    kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    lines = list(kept)
    if lines:
        lines.append("")
    lines.append("[llm]")
    lines.append("provider = " + _quote(provider))
    lines.append("model = " + _quote(model))
    if base_url is not None:
        lines.append("base_url = " + _quote(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + _quote(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def load_config(config_path=None):
    _log("load_config", config_path=None if config_path is None else str(config_path))
    path = os.fspath(config_path) if config_path is not None else os.path.join(os.getcwd(), "hotdocs.toml")
    if not os.path.exists(path):
        return None
    values = {}
    found = False
    in_llm = False
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                in_llm = stripped == "[llm]"
                if in_llm:
                    found = True
                continue
            if in_llm and "=" in stripped:
                key, raw = stripped.split("=", 1)
                key = key.strip()
                raw = raw.strip()
                if raw.startswith('"') and raw.endswith('"'):
                    values[key] = raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                else:
                    try:
                        values[key] = int(raw)
                    except ValueError:
                        raise ValueError("invalid value for %s" % key)
    if not found:
        return None
    return {
        "provider": values.get("provider"),
        "model": values.get("model"),
        "base_url": values.get("base_url"),
        "api_key_env": values.get("api_key_env"),
        "timeout_seconds": values.get("timeout_seconds"),
    }
'''


def _build_tool_root(base: Path) -> tuple[Path, Path]:
    tool_root = base / "tool"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "llm_endpoint_calls.log"

    endpoint_dir = tool_root / "gen" / "llm-endpoint"
    endpoint_dir.mkdir(parents=True)
    (endpoint_dir / "llm_endpoint.py").write_text(
        FAKE_LLM_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path))),
        encoding="utf-8",
    )

    ab_dir = tool_root / "gen" / "a-b"
    ab_dir.mkdir(parents=True)
    (ab_dir / "a_b.py").write_text(
        "def a_b():\n    return 'a-b'\n", encoding="utf-8"
    )

    other_dir = tool_root / "gen" / "other-tool"
    other_dir.mkdir(parents=True)
    (other_dir / "other_tool.py").write_text(
        "def other_tool():\n    return 'other'\n", encoding="utf-8"
    )

    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text(
        "# Slugs\n\nTurn titles into URL slugs.\n", encoding="utf-8"
    )

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + pytest_version + "\n", encoding="utf-8"
    )
    return tool_root, log_path


def _snapshot(root: Path) -> dict:
    snap = {}
    root = Path(root)
    st = os.stat(root)
    snap["."] = ("dir", None, st.st_mtime_ns)
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            snap[rel] = ("dir", None, os.stat(full).st_mtime_ns)
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            snap[rel] = ("file", full.read_bytes(), os.stat(full).st_mtime_ns)
    return snap


def _log_lines(log_path: Path) -> list:
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


class _Runner:
    def __init__(self, tool_root: Path, cwd: Path):
        self.tool_root = tool_root
        self.cwd = cwd
        self.output = []
        self.questions = []

    def input_fn(self, prompt=""):
        self.questions.append(prompt)
        if len(self.questions) > 50:
            raise AssertionError("init asked too many questions: %r" % self.questions[-5:])
        return ""

    def output_fn(self, *args, **kwargs):
        self.output.append(" ".join(str(a) for a in args))

    def run(self, argv):
        env = {"PATH": os.environ.get("PATH", "")}
        return hotdocs_init.main(
            argv,
            tool_root=self.tool_root,
            input_fn=self.input_fn,
            output_fn=self.output_fn,
            env=env,
            cwd=str(self.cwd),
        )


def _init_args(target: Path) -> list:
    return [
        str(target),
        "--provider",
        "ollama",
        "--model",
        "llama3.2",
        "--no-test",
        "--yes",
    ]


def test_init_writes_empty_gen_and_tool_version_without_copying_tool(tmp_path):
    tool_root, log_path = _build_tool_root(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    target = tmp_path / "proj"
    target.mkdir()

    runner = _Runner(tool_root, work)
    code = runner.run(_init_args(target))
    assert code in (0, 3), "unexpected exit code %r; output=%r" % (code, runner.output)

    gen = target / "gen"
    assert gen.is_dir(), "<dir>/gen must exist as a directory"
    assert list(gen.iterdir()) == [], "<dir>/gen must be empty, got %r" % [
        p.name for p in gen.iterdir()
    ]
    assert not (gen / "a-b").exists()
    assert not (gen / "llm-endpoint").exists()

    assert not (target / "pipeline").exists(), "no pipeline directory may exist"

    others = [
        p.name for p in target.iterdir() if p.name not in ("gen", ".hotdocs-tool.json")
    ]
    assert others, "R-INIT-001's other entries must exist beside gen/"

    tool_file = target / ".hotdocs-tool.json"
    assert tool_file.is_file()
    assert json.loads(tool_file.read_bytes().decode("utf-8")) == {
        "tool_version": TOOL_VERSION
    }

    assert not any(
        p.name == "a_b.py" for p in target.rglob("a_b.py")
    ), "tool components must not be copied into the project"
    assert not any(
        p.name == "llm_endpoint.py" for p in target.rglob("llm_endpoint.py")
    ), "tool components must not be copied into the project"


def test_second_run_leaves_tool_file_byte_for_byte(tmp_path):
    tool_root, log_path = _build_tool_root(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    target = tmp_path / "proj"
    target.mkdir()

    runner = _Runner(tool_root, work)
    first = runner.run(_init_args(target))
    assert first in (0, 3), "unexpected exit code %r; output=%r" % (first, runner.output)

    tool_file = target / ".hotdocs-tool.json"
    assert tool_file.is_file()

    old_ns = 1_000_000_000 * 1_000_000_000
    os.utime(tool_file, ns=(old_ns, old_ns))
    before_bytes = tool_file.read_bytes()
    before_mtime = os.stat(tool_file).st_mtime_ns
    assert before_mtime == old_ns

    runner2 = _Runner(tool_root, work)
    second = runner2.run(_init_args(target))
    assert second != 2, "second run must not be a usage error; output=%r" % runner2.output

    assert tool_file.is_file()
    assert tool_file.read_bytes() == before_bytes
    assert os.stat(tool_file).st_mtime_ns == before_mtime


def test_refuses_when_project_gen_shadows_tool_component(tmp_path, capsys):
    tool_root, log_path = _build_tool_root(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    target = tmp_path / "proj"
    (target / "gen" / "a-b").mkdir(parents=True)
    (target / "gen" / "a-b" / "a_b.py").write_text(
        "def a_b():\n    return 'project'\n", encoding="utf-8"
    )
    (target / "gen" / "mine").mkdir(parents=True)
    (target / "gen" / "mine" / "mine.py").write_text(
        "def mine():\n    return 'mine'\n", encoding="utf-8"
    )

    capsys.readouterr()
    before_target = _snapshot(target)
    before_tool = _snapshot(tool_root)
    before_work = _snapshot(work)
    before_log = _log_lines(log_path)

    runner = _Runner(tool_root, work)
    code = runner.run(_init_args(target))
    captured = capsys.readouterr()

    assert code == 1, "expected exit 1, got %r" % code

    messages = "\n".join(runner.output) + "\n" + captured.err + "\n" + captured.out
    assert "gen/a-b" in messages, "refusal must name gen/a-b; got %r" % messages
    assert "gen/mine" not in messages, "refusal must not name gen/mine; got %r" % messages

    assert _snapshot(target) == before_target, "nothing may be written to the target"
    assert _snapshot(tool_root) == before_tool, "nothing may be written to the tool root"
    assert _snapshot(work) == before_work, "nothing may be written to the cwd"
    assert not (target / ".hotdocs-tool.json").exists()
    assert _log_lines(log_path) == before_log, "llm-endpoint must not be loaded or called"


def test_refuses_when_target_is_tool_root(tmp_path, capsys):
    tool_root, log_path = _build_tool_root(tmp_path)
    work = tmp_path / "work"
    work.mkdir()

    capsys.readouterr()
    before_tool = _snapshot(tool_root)
    before_work = _snapshot(work)
    before_log = _log_lines(log_path)

    runner = _Runner(tool_root, work)
    code = runner.run(_init_args(tool_root))
    capsys.readouterr()

    assert code == 1, "expected exit 1, got %r" % code
    assert _snapshot(tool_root) == before_tool, "nothing may be written to the tool root"
    assert _snapshot(work) == before_work, "nothing may be written to the cwd"
    assert not (tool_root / ".hotdocs-tool.json").exists()
    assert _log_lines(log_path) == before_log, "llm-endpoint must not be loaded or called"