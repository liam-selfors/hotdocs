"""hotdocs init: set up a new project for the tool.

Creates the project skeleton, reports missing prerequisites (never installing
anything), and chooses and tests a language-model provider through
`llm-endpoint`, loaded from the tool root.
"""

import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

TOOL_VERSION = "0.1.0"

_VALUE_FLAGS = {
    "--provider": "provider",
    "--model": "model",
    "--base-url": "base_url",
    "--api-key-env": "api_key_env",
    "--auth": "auth",
}
_BOOL_FLAGS = {
    "--example": "example",
    "--reconfigure": "reconfigure",
    "--no-test": "no_test",
    "--yes": "yes",
}
_SKELETON_DIRS = (
    "specs/product",
    "specs/components",
    "specs/decisions",
    "gen",
    "verification",
)
_GITKEEP_DIRS = ("specs/product", "specs/components", "specs/decisions", "verification")
_GITIGNORE_LINES = ("/.hotdocs/", "__pycache__/", "*.pyc", ".venv/")
_GLOSSARY = (
    "# Glossary\n\n"
    "This file defines the canonical vocabulary every spec in this project uses.\n"
)
_ALLOWLIST = json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class _UsageError(Exception):
    pass


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _parse(argv):
    opts = {name: None for name in _VALUE_FLAGS.values()}
    opts.update({name: False for name in _BOOL_FLAGS.values()})
    dir_arg = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("-"):
            name, eq, value = arg.partition("=")
            if name in _VALUE_FLAGS:
                if not eq:
                    i += 1
                    if i >= len(argv):
                        raise _UsageError(f"{name} needs a value")
                    value = argv[i]
                opts[_VALUE_FLAGS[name]] = value
            elif arg in _BOOL_FLAGS:
                opts[_BOOL_FLAGS[arg]] = True
            else:
                raise _UsageError(f"unknown flag {name}")
        else:
            if dir_arg is not None:
                raise _UsageError("only one directory may be given")
            dir_arg = arg
        i += 1

    if opts["api_key_env"] is not None and not _ENV_NAME.fullmatch(opts["api_key_env"]):
        raise _UsageError(
            "--api-key-env must be the NAME of an environment variable "
            "(letters, digits, _, not starting with a digit)"
        )
    if opts["provider"] == "claude-cli" and (
        opts["base_url"] is not None or opts["api_key_env"] is not None
    ):
        raise _UsageError("--base-url and --api-key-env cannot be used with claude-cli")
    if opts["auth"] is not None and opts["auth"] not in ("login", "key"):
        raise _UsageError("--auth must be login or key")
    if opts["auth"] is not None and opts["provider"] != "claude-cli":
        raise _UsageError("--auth is only for --provider claude-cli")
    return opts, dir_arg


def _check_provider_usage(opts, providers):
    provider = opts["provider"]
    if provider not in providers:
        raise _UsageError(
            f"unknown provider {provider!r}; choose one of: {', '.join(providers)}"
        )
    entry = providers[provider]
    if not _get(entry, "suggested_model") and opts["model"] is None:
        raise _UsageError(f"--provider {provider} needs --model")
    if _get(entry, "needs_base_url") and opts["base_url"] is None:
        raise _UsageError(f"--provider {provider} needs --base-url")


def _refusal(target, tool_root):
    tool = tool_root.resolve()
    if target.resolve() == tool:
        return [f"refusing: {target} is the tool's own repository"]
    project_gen = target / "gen"
    if not project_gen.is_dir():
        return None
    clashes = sorted(
        child.name
        for child in project_gen.iterdir()
        if child.is_dir() and (tool / "gen" / child.name).is_dir()
    )
    if not clashes:
        return None
    return ["refusing: these project components would shadow the tool's own:"] + [
        f"  gen/{name}" for name in clashes
    ]


def _load_llm_endpoint(tool_root):
    base = Path(tool_root) / "gen" / "llm-endpoint"
    path = base / "llm_endpoint.py"
    locations = None
    if not path.is_file():
        path = base / "llm_endpoint" / "__init__.py"
        if not path.is_file():
            return None
        locations = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(
        "llm_endpoint", path, submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _report_dir(target, rel, out):
    path = target / rel
    if path.exists():
        out(f"{rel}: skipped (exists)")
    else:
        path.mkdir(parents=True)
        out(f"{rel}: created")


def _report_file(target, rel, data, out):
    path = target / rel
    if path.exists():
        out(f"{rel}: skipped (exists)")
    else:
        path.write_bytes(data)
        out(f"{rel}: created")


def _gitignore(target, out):
    path = target / ".gitignore"
    if path.exists():
        text = path.read_bytes().decode("utf-8")
        present = set(text.splitlines())
        missing = [line for line in _GITIGNORE_LINES if line not in present]
        if missing:
            prefix = "" if text == "" or text.endswith("\n") else "\n"
            with open(path, "ab") as handle:
                handle.write((prefix + "\n".join(missing) + "\n").encode("utf-8"))
        out(".gitignore: skipped (exists)")
    else:
        path.write_bytes(("\n".join(_GITIGNORE_LINES) + "\n").encode("utf-8"))
        out(".gitignore: created")


def _skeleton(target, out):
    for rel in _SKELETON_DIRS:
        _report_dir(target, rel, out)
        if rel in _GITKEEP_DIRS:
            _report_file(target, f"{rel}/.gitkeep", b"", out)
    _report_file(target, "specs/glossary.md", _GLOSSARY.encode("utf-8"), out)
    _report_file(target, ".secret-allowlist.json", _ALLOWLIST.encode("utf-8"), out)
    _gitignore(target, out)


def _copy_example(tool_root, target):
    src = Path(tool_root) / "examples" / "slugify"
    for path in sorted(src.rglob("*")):
        if path.is_file():
            dest = target / path.relative_to(src)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)


def _ask_value(input_fn, label, default, required):
    prompt = f"{label} [{default}]: " if default else f"{label}: "
    while True:
        answer = input_fn(prompt).strip() or default
        if answer or not required:
            return answer or None


def _ask(detected, providers, input_fn, out):
    names = [_get(entry, "provider") for entry in detected]
    out("Providers:")
    for number, entry in enumerate(detected, 1):
        status = "available" if _get(entry, "available") else "not available"
        out(f"  {number}. {names[number - 1]}: {status}")
    default = next(
        (name for name, entry in zip(names, detected) if _get(entry, "available")),
        names[0],
    )
    while True:
        answer = input_fn(f"Provider [{default}]: ").strip() or default
        if answer in names:
            provider = answer
            break
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            provider = names[int(answer) - 1]
            break
    entry = providers[provider]
    model = _ask_value(input_fn, "Model", _get(entry, "suggested_model"), True)
    base_url = None
    if _get(entry, "needs_base_url"):
        base_url = _ask_value(input_fn, "Base URL", _get(entry, "default_base_url"), True)
    api_key_env = None
    if provider != "claude-cli":
        api_key_env = _ask_value(
            input_fn,
            "API-key environment variable name",
            _get(entry, "default_api_key_env"),
            False,
        )
    return provider, model, base_url, api_key_env


def _test_connection(llm, provider, model, kwargs, out):
    try:
        result = _get(llm, "check_connection")(provider, model, **kwargs)
    except ValueError as exc:
        out(f"connection failed: invalid: {exc}")
        return False
    if _get(result, "ok"):
        out("connection ok")
        return True
    error = _get(result, "error")
    out(f"connection failed: {_get(error, 'category')}: {_get(error, 'message')}")
    return False


def _provider_step(llm, opts, config_path, input_fn, out, detect_env):
    """Return (chosen provider or None, whether saving failed)."""
    providers = _get(llm, "PROVIDERS")
    interactive = opts["provider"] is None and not opts["yes"]
    auth = None
    if opts["provider"] is not None:
        provider = opts["provider"]
        entry = providers[provider]
        model = opts["model"] or _get(entry, "suggested_model")
        base_url = opts["base_url"]
        api_key_env = opts["api_key_env"] or _get(entry, "default_api_key_env")
        auth = opts["auth"]
    else:
        detect = _get(llm, "detect_providers")
        detected = detect(env=detect_env) if detect_env is not None else detect()
        if interactive:
            provider, model, base_url, api_key_env = _ask(detected, providers, input_fn, out)
        else:
            available = [entry for entry in detected if _get(entry, "available")]
            if not available:
                out("no provider is available; provider not configured")
                return None, False
            provider = _get(available[0], "provider")
            entry = providers[provider]
            model = _get(entry, "suggested_model")
            base_url = None
            api_key_env = _get(entry, "default_api_key_env")

    kwargs = {
        key: value
        for key, value in (("base_url", base_url), ("api_key_env", api_key_env), ("auth", auth))
        if value
    }
    if not opts["no_test"] and not _test_connection(llm, provider, model, kwargs, out):
        if interactive:
            if input_fn("Save anyway? [y/N] ").strip().lower() != "y":
                out("provider not saved")
                return provider, False
        else:
            out("warning: saving although the connection test failed")
    try:
        _get(llm, "save_config")(config_path, provider, model, **kwargs)
    except ValueError as exc:
        print(f"could not save: {exc}", file=sys.stderr)
        return provider, True
    out(f"saved provider {provider} (model {model}) to hotdocs.toml")
    return provider, False


def _prerequisites(tool_root, provider, env, out):
    missing = False
    if sys.version_info < (3, 11):
        out("missing: Python 3.11 or newer")
        out("  fix: install Python 3.11 or newer")
        missing = True
    requirements = Path(tool_root) / "requirements.txt"
    for line in requirements.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "==" not in line:
            continue
        try:
            importlib.metadata.version(line.split("==", 1)[0].strip())
        except importlib.metadata.PackageNotFoundError:
            out(f"missing: {line}")
            out(f"  fix: pip install -r {tool_root}/requirements.txt")
            missing = True
    if provider == "claude-cli" and shutil.which("claude", path=env.get("PATH")) is None:
        out("missing: claude on PATH")
        out("  fix: install Claude Code and sign in")
        missing = True
    return missing


def _next_steps(example, out):
    out("Next steps:")
    out("  hotdocs lint")
    if example:
        out("  hotdocs generate comp-slugify")
    out("  hotdocs verify")
    out("  read QUICKSTART.md")


def main(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None):
    input_fn = input if input_fn is None else input_fn
    out = print if output_fn is None else output_fn
    detect_env = env
    env = os.environ if env is None else env

    try:
        opts, dir_arg = _parse(list(argv))
    except _UsageError as exc:
        print(f"hotdocs init: {exc}", file=sys.stderr)
        return 2

    base = Path(os.getcwd() if cwd is None else cwd)
    target = base / dir_arg if dir_arg is not None else base

    refusal = _refusal(target, Path(tool_root))
    if refusal:
        for line in refusal:
            print(line, file=sys.stderr)
        return 1

    llm = _load_llm_endpoint(tool_root)
    if llm is not None and opts["provider"] is not None:
        try:
            _check_provider_usage(opts, _get(llm, "PROVIDERS"))
        except _UsageError as exc:
            print(f"hotdocs init: {exc}", file=sys.stderr)
            return 2

    config_path = target / "hotdocs.toml"

    if opts["reconfigure"]:
        if not (target / ".hotdocs-tool.json").is_file():
            print(
                f"hotdocs init: {target} is not an initialised project "
                "(no .hotdocs-tool.json); run hotdocs init first",
                file=sys.stderr,
            )
            return 1
        if llm is None:
            print("provider not configured: gen/llm-endpoint is missing", file=sys.stderr)
            return 1
        _, failed = _provider_step(llm, opts, config_path, input_fn, out, detect_env)
        return 1 if failed else 0

    target.mkdir(parents=True, exist_ok=True)
    _skeleton(target, out)
    tool_json = target / ".hotdocs-tool.json"
    if not tool_json.exists():
        tool_json.write_bytes(
            (json.dumps({"tool_version": TOOL_VERSION}) + "\n").encode("utf-8")
        )
    if opts["example"]:
        _copy_example(tool_root, target)

    provider = None
    if config_path.exists():
        out("hotdocs.toml: skipped (exists)")
        if llm is not None:
            provider = _get(_get(llm, "load_config")(config_path), "provider")
    elif llm is None:
        out("provider not configured: gen/llm-endpoint is missing")
    else:
        provider, _ = _provider_step(llm, opts, config_path, input_fn, out, detect_env)

    missing = _prerequisites(tool_root, provider, env, out)
    _next_steps(opts["example"], out)
    return 3 if missing else 0
