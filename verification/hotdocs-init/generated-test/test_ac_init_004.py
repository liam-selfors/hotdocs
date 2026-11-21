# hotdocs-criterion: sha256:18fe0a3deda679ad73bf32cca8d35ad98a2e0b1d51cb66483c3e6e28ae39aaf6
import importlib.metadata
import json
import os
import stat
from pathlib import Path

import hotdocs_init


FAKE_BODY = '''

def _log(name, **data):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": data}, default=str) + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", probe_ollama=probe_ollama, env_given=env is not None)
    return [dict(d) for d in _DETECTED]


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _strip_llm(text):
    kept = []
    in_llm = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            in_llm = line == "[llm]"
            if in_llm:
                continue
        if not in_llm:
            kept.append(raw)
    return kept


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model:
        raise ValueError("model required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = _strip_llm(path.read_text(encoding="utf-8")) if path.is_file() else []
    lines = [l for l in kept if l.strip()]
    lines.append("[llm]")
    for key, value in (("provider", provider), ("model", model),
                       ("base_url", base_url), ("api_key_env", api_key_env),
                       ("timeout_seconds", timeout_seconds), ("auth", auth)):
        if value is not None:
            lines.append(key + " = " + json.dumps(value))
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=None if config_path is None else str(config_path))
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.is_file():
        return None
    result = {"provider": None, "model": None, "base_url": None,
              "api_key_env": None, "timeout_seconds": None, "auth": None}
    in_llm = False
    found = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("["):
            in_llm = line == "[llm]"
            found = found or in_llm
            continue
        if in_llm and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key in result:
                try:
                    result[key] = json.loads(value)
                except ValueError:
                    result[key] = value.strip('"')
    return result if found else None
'''


OPENAI_PROVIDERS = {
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.2",
    },
    "openai": {
        "default_base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-x",
    },
}

OPENAI_DETECTED = [
    {
        "provider": "ollama",
        "available": False,
        "reason": "not running",
        "suggested_model": "llama3.2",
        "api_key_env": None,
    },
    {
        "provider": "openai",
        "available": True,
        "reason": "key present",
        "suggested_model": "gpt-x",
        "api_key_env": "OPENAI_API_KEY",
    },
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def build_tool_root(tmp_path, providers, detected, with_endpoint=True):
    tool = tmp_path / "tool"
    log = tmp_path / "logs" / "calls.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True, exist_ok=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nExample spec.\n", encoding="utf-8")
    (tool / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n", encoding="utf-8"
    )
    if with_endpoint:
        ep = tool / "gen" / "llm-endpoint"
        ep.mkdir(parents=True, exist_ok=True)
        src = (
            "import json\n"
            "from pathlib import Path\n"
            "LOG = " + repr(str(log)) + "\n"
            "PROVIDERS = " + repr(providers) + "\n"
            "_DETECTED = " + repr(detected) + "\n"
            + FAKE_BODY
        )
        (ep / "llm_endpoint.py").write_text(src, encoding="utf-8")
    else:
        (tool / "gen").mkdir(parents=True, exist_ok=True)
    return tool, log


def make_env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return {"PATH": str(bindir)}


def read_calls(log):
    if not log.is_file():
        return []
    return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]


def save_calls(log):
    return [c["args"] for c in read_calls(log) if c["call"] == "save_config"]


def kind(question):
    q = question.lower()
    if "url" in q:
        return "url"
    if "key" in q:
        return "key"
    if "model" in q:
        return "model"
    if "provider" in q:
        return "provider"
    return "other"


def run_init(tmp_path, argv_extra, answers, providers, detected,
             with_endpoint=True, prepare_project=None):
    tool, log = build_tool_root(tmp_path, providers, detected, with_endpoint)
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    if prepare_project is not None:
        prepare_project(project)
    env = make_env(tmp_path)
    questions = []
    outputs = []
    queue = list(answers)

    def input_fn(prompt=""):
        questions.append(prompt)
        if len(questions) > 30:
            raise RuntimeError("too many questions")
        return queue.pop(0) if queue else ""

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    old_cwd = os.getcwd()
    os.chdir(project)
    try:
        code = hotdocs_init.run(
            [str(project)] + list(argv_extra),
            tool_root=tool,
            input_fn=input_fn,
            output_fn=output_fn,
            env=env,
            cwd=project,
        )
    finally:
        os.chdir(old_cwd)
    return code, questions, outputs, log, project


def test_empty_answers_use_defaults_and_ask_in_order(tmp_path):
    code, questions, outputs, log, project = run_init(
        tmp_path, ["--no-test"], [], OPENAI_PROVIDERS, OPENAI_DETECTED
    )
    kinds = [kind(q) for q in questions]
    assert kinds == ["provider", "model", "key"], questions
    for q in questions:
        assert q.endswith(" ")
    text = "\n".join(outputs)
    assert "ollama" in text
    assert "openai" in text
    saves = save_calls(log)
    assert len(saves) == 1
    assert saves[0]["provider"] == "openai"
    assert saves[0]["model"] == "gpt-x"
    assert saves[0]["api_key_env"] == "OPENAI_API_KEY"


def test_unrecognised_provider_is_asked_again_and_number_selects(tmp_path):
    code, questions, outputs, log, project = run_init(
        tmp_path, ["--no-test"], ["bogus", "2"], OPENAI_PROVIDERS, OPENAI_DETECTED
    )
    kinds = [kind(q) for q in questions]
    assert kinds == ["provider", "provider", "model", "key"], questions
    saves = save_calls(log)
    assert len(saves) == 1
    assert saves[0]["provider"] == "openai"
    assert saves[0]["model"] == "gpt-x"


def test_openai_compatible_asks_again_for_empty_model_and_base_url(tmp_path):
    providers = {
        "openai-compatible": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": True,
            "suggested_model": "",
        },
    }
    detected = [
        {
            "provider": "openai-compatible",
            "available": True,
            "reason": "configurable",
            "suggested_model": "",
            "api_key_env": None,
        },
    ]
    answers = ["openai-compatible", "", "m", "", "http://h/v1", ""]
    code, questions, outputs, log, project = run_init(
        tmp_path, ["--no-test"], answers, providers, detected
    )
    kinds = [kind(q) for q in questions]
    assert kinds == ["provider", "model", "model", "url", "url", "key"], questions
    saves = save_calls(log)
    assert len(saves) == 1
    assert saves[0]["provider"] == "openai-compatible"
    assert saves[0]["model"] == "m"
    assert saves[0]["base_url"] == "http://h/v1"
    assert saves[0]["api_key_env"] is None


def test_claude_cli_asks_no_base_url_or_key_and_returns_zero(tmp_path):
    providers = {
        "claude-cli": {
            "default_base_url": None,
            "default_api_key_env": None,
            "needs_base_url": False,
            "suggested_model": "claude-sonnet-5",
        },
    }
    detected = [
        {
            "provider": "claude-cli",
            "available": True,
            "reason": "claude on PATH",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": None,
        },
    ]
    code, questions, outputs, log, project = run_init(
        tmp_path, ["--no-test"], [], providers, detected
    )
    kinds = [kind(q) for q in questions]
    assert "url" not in kinds, questions
    assert "key" not in kinds, questions
    assert kinds[:2] == ["provider", "model"], questions
    assert code == 0
    saves = save_calls(log)
    assert len(saves) == 1
    assert saves[0]["provider"] == "claude-cli"


def test_missing_llm_endpoint_reports_and_carries_on(tmp_path):
    code, questions, outputs, log, project = run_init(
        tmp_path, ["--yes"], [], OPENAI_PROVIDERS, OPENAI_DETECTED, with_endpoint=False
    )
    msg = "provider not configured: gen/llm-endpoint is missing"
    assert any(msg in o for o in outputs), outputs
    assert code == 0
    assert not (project / "hotdocs.toml").exists()


def test_existing_hotdocs_toml_is_kept(tmp_path):
    original = '[llm]\nprovider = "openai"\nmodel = "gpt-x"\n'

    def prepare(project):
        (project / "hotdocs.toml").write_text(original, encoding="utf-8")

    code, questions, outputs, log, project = run_init(
        tmp_path, ["--no-test"], [], OPENAI_PROVIDERS, OPENAI_DETECTED,
        prepare_project=prepare,
    )
    assert "provider" not in [kind(q) for q in questions], questions
    assert save_calls(log) == []
    assert (project / "hotdocs.toml").read_text(encoding="utf-8") == original
    assert any("hotdocs.toml" in o for o in outputs), outputs