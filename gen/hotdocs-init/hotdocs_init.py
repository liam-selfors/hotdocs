"""hotdocs init: set up a new project for the tool.

Creates the project skeleton, reports missing prerequisites (never installs
anything), and chooses and tests a language-model provider through the
tool's own ``llm-endpoint`` component, loaded from ``tool_root``.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import itertools
import json
import os
import re
import shutil
import sys
from pathlib import Path

TOOL_VERSION = "0.1.0"

_VALUE_FLAGS = ("--provider", "--model", "--base-url", "--api-key-env")
_BOOL_FLAGS = ("--example", "--reconfigure", "--no-test", "--yes")
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_DIRS = ("specs/product", "specs/components", "specs/decisions", "gen", "verification")
_GITKEEP_DIRS = ("specs/product", "specs/components", "specs/decisions", "verification")
_IGNORE_LINES = ("/.hotdocs/", "__pycache__/", "*.pyc", ".venv/")
_GLOSSARY = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for this project's specs: every spec uses these terms as defined here.\n"
)
_ENDPOINT_MISSING = "provider not configured: gen/llm-endpoint is missing"
_USAGE = (
    "usage: hotdocs init [<dir>] [--example] [--reconfigure] [--provider <name>] "
    "[--model <name>] [--base-url <url>] [--api-key-env <NAME>] [--no-test] [--yes]"
)

_load_counter = itertools.count()


class _UsageError(Exception):
    pass


def _get(obj, key):
    """Read ``key`` from a dict or as an attribute."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _err(message):
    print(message, file=sys.stderr)


def _usage(exc):
    _err(f"hotdocs init: {exc}")
    _err(_USAGE)
    return 2


# ---------------------------------------------------------------- arguments


def _parse(argv):
    values, flags, positional = {}, set(), []
    args = list(argv)
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        name, eq, value = arg.partition("=")
        if arg in _BOOL_FLAGS:
            flags.add(arg)
        elif name in _VALUE_FLAGS:
            if not eq:
                if i >= len(args):
                    raise _UsageError(f"{name} needs a value")
                value = args[i]
                i += 1
            values[name] = value
        elif arg.startswith("-"):
            raise _UsageError(f"unknown flag: {name}")
        elif positional:
            raise _UsageError("only one <dir> argument is allowed")
        else:
            positional.append(arg)
    env_name = values.get("--api-key-env")
    if env_name is not None and not _ENV_NAME.fullmatch(env_name):
        raise _UsageError(
            "--api-key-env takes the NAME of an environment variable (letters, digits, _, "
            "not starting with a digit), never the key itself"
        )
    if values.get("--provider") == "claude-cli" and (
        "--base-url" in values or "--api-key-env" in values
    ):
        raise _UsageError("--base-url and --api-key-env do not apply to claude-cli")
    return values, flags, positional


def _check_provider_flags(values, providers):
    provider = values["--provider"]
    if provider not in providers:
        raise _UsageError("unknown --provider; choose one of: " + ", ".join(providers))
    spec = providers[provider]
    if not _get(spec, "suggested_model") and not values.get("--model"):
        raise _UsageError(f"--provider {provider} needs --model")
    if _get(spec, "needs_base_url") and not values.get("--base-url"):
        raise _UsageError(f"--provider {provider} needs --base-url")


# ---------------------------------------------------------------- refusal


def _refusal(target, tool_root):
    if target.resolve() == tool_root.resolve():
        return [f"refusing: {target} is the tool's own repository; init a separate project directory"]
    project_gen = target / "gen"
    clashes = sorted(
        child.name
        for child in (project_gen.iterdir() if project_gen.is_dir() else ())
        if child.is_dir() and (tool_root / "gen" / child.name).is_dir()
    )
    if clashes:
        return ["refusing: these project components would shadow the tool's own:"] + [
            f"  gen/{name}" for name in clashes
        ]
    return []


# ---------------------------------------------------------------- llm-endpoint


def _load_endpoint(tool_root):
    base = tool_root / "gen" / "llm-endpoint"
    flat = base / "llm_endpoint.py"
    package = base / "llm_endpoint" / "__init__.py"
    if flat.is_file():
        path, locations = flat, None
    elif package.is_file():
        path, locations = package, [str(package.parent)]
    else:
        return None
    name = f"_hotdocs_init_llm_endpoint_{next(_load_counter)}"
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=locations)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# ---------------------------------------------------------------- skeleton


def _create_file(target, rel, data, output_fn):
    dest = target / rel
    if dest.exists():
        output_fn(f"{rel}: skipped (exists)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    output_fn(f"{rel}: created")


def _gitignore(target, output_fn):
    path = target / ".gitignore"
    existed = path.exists()
    text = path.read_text(encoding="utf-8") if existed else ""
    present = text.splitlines()
    add = [line for line in _IGNORE_LINES if line not in present]
    if add:
        prefix = "\n" if text and not text.endswith("\n") else ""
        with open(path, "a", encoding="utf-8", newline="") as handle:
            handle.write(prefix + "\n".join(add) + "\n")
    output_fn(f".gitignore: {'skipped (exists)' if existed else 'created'}")


def _skeleton(target, output_fn):
    for rel in _DIRS:
        path = target / rel
        if path.exists():
            output_fn(f"{rel}: skipped (exists)")
        else:
            path.mkdir(parents=True)
            output_fn(f"{rel}: created")
    for rel in _GITKEEP_DIRS:
        _create_file(target, f"{rel}/.gitkeep", b"", output_fn)
    _create_file(target, "specs/glossary.md", _GLOSSARY.encode("utf-8"), output_fn)
    allowlist = json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
    _create_file(target, ".secret-allowlist.json", allowlist.encode("utf-8"), output_fn)
    _gitignore(target, output_fn)
    marker = json.dumps({"tool_version": TOOL_VERSION}, indent=2) + "\n"
    _create_file(target, ".hotdocs-tool.json", marker.encode("utf-8"), output_fn)


def _copy_example(tool_root, target, output_fn):
    source = tool_root / "examples" / "slugify"
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        rel = path.relative_to(source).as_posix()
        _create_file(target, rel, path.read_bytes(), output_fn)


# ---------------------------------------------------------------- provider


def _ask(input_fn, question):
    return input_fn(question + " ").strip()


def _ask_value(input_fn, label, default, required):
    question = f"{label} [{default}]:" if default else f"{label}:"
    value = None
    while value is None:
        value = _ask(input_fn, question) or default or (None if required else "")
    return value or None


def _ask_provider(detected, providers, input_fn, output_fn):
    names = [_get(entry, "provider") for entry in detected]
    output_fn("Providers:")
    for number, entry in enumerate(detected, 1):
        status = "available" if _get(entry, "available") else "not available"
        output_fn(f"  {number}. {_get(entry, 'provider')} ({status}: {_get(entry, 'reason')})")
    available = [name for name, entry in zip(names, detected) if _get(entry, "available")]
    default = (available or names)[0]
    choices = {"": default}
    choices.update({str(number): name for number, name in enumerate(names, 1)})
    choices.update({name: name for name in names})
    answer = None
    while answer not in choices:
        answer = _ask(input_fn, f"Provider [{default}]:")
    provider = choices[answer]
    entry = detected[names.index(provider)]
    spec = providers[provider]
    model = _ask_value(input_fn, "Model", _get(entry, "suggested_model"), True)
    base_url = (
        _ask_value(input_fn, "Base URL", _get(spec, "default_base_url"), True)
        if _get(spec, "needs_base_url")
        else None
    )
    api_key_env = (
        _ask_value(
            input_fn,
            "API key environment variable NAME (not the key)",
            _get(spec, "default_api_key_env"),
            False,
        )
        if provider != "claude-cli"
        else None
    )
    return provider, model, base_url, api_key_env


def _connection_ok(endpoint, provider, model, kwargs, output_fn):
    try:
        result = _get(endpoint, "check_connection")(provider, model, **kwargs)
    except ValueError as exc:
        output_fn(f"connection failed: invalid: {exc}")
        return False
    if _get(result, "ok"):
        output_fn("connection ok")
        return True
    error = _get(result, "error")
    output_fn(f"connection failed: {_get(error, 'category')}: {_get(error, 'message')}")
    return False


def _provider_step(endpoint, values, flags, toml, input_fn, output_fn, detect_kwargs):
    """Choose, test and save a provider. Returns (provider chosen, save failed)."""
    providers = _get(endpoint, "PROVIDERS")
    interactive = "--provider" not in values and "--yes" not in flags
    if "--provider" in values:
        provider = values["--provider"]
        spec = providers[provider]
        model = values.get("--model") or _get(spec, "suggested_model")
        base_url = values.get("--base-url")
        api_key_env = values.get("--api-key-env") or _get(spec, "default_api_key_env")
    else:
        detected = list(_get(endpoint, "detect_providers")(**detect_kwargs))
        if interactive:
            provider, model, base_url, api_key_env = _ask_provider(
                detected, providers, input_fn, output_fn
            )
        else:
            available = [entry for entry in detected if _get(entry, "available")]
            if not available:
                output_fn("no provider is available: nothing saved")
                return None, False
            entry = available[0]
            provider = _get(entry, "provider")
            spec = providers[provider]
            model = _get(entry, "suggested_model")
            base_url = _get(spec, "default_base_url") if _get(spec, "needs_base_url") else None
            api_key_env = _get(spec, "default_api_key_env")
    kwargs = {
        key: value
        for key, value in (("base_url", base_url), ("api_key_env", api_key_env))
        if value
    }
    if "--no-test" not in flags and not _connection_ok(endpoint, provider, model, kwargs, output_fn):
        if interactive:
            if _ask(input_fn, "Save anyway? [y/N]").lower() not in ("y", "yes"):
                output_fn("nothing saved")
                return provider, False
        else:
            output_fn("warning: the connection test failed; saving anyway")
    try:
        _get(endpoint, "save_config")(toml, provider, model, **kwargs)
    except ValueError as exc:
        _err(f"could not save: {exc}")
        return provider, True
    output_fn(f"saved provider {provider} to hotdocs.toml")
    return provider, False


# ---------------------------------------------------------------- prerequisites


def _prerequisites(tool_root, provider, env, output_fn):
    missing = []
    if sys.version_info < (3, 11):
        missing.append(("Python 3.11 or newer", "install Python 3.11 or newer"))
    requirements = f"{tool_root}/requirements.txt"
    for line in Path(requirements).read_text(encoding="utf-8").splitlines():
        name, sep, _ = line.strip().partition("==")
        if sep:
            try:
                importlib.metadata.version(name.strip())
            except importlib.metadata.PackageNotFoundError:
                missing.append((line.strip(), f"pip install -r {requirements}"))
    if provider == "claude-cli" and shutil.which("claude", path=env.get("PATH")) is None:
        missing.append(("claude on PATH", "install Claude Code and sign in"))
    for what, fix in missing:
        output_fn(f"missing: {what}")
        output_fn(f"  fix: {fix}")
    return bool(missing)


def _next_steps(example, output_fn):
    output_fn("Next steps:")
    output_fn("  hotdocs lint")
    if example:
        output_fn("  hotdocs generate comp-slugify")
    output_fn("  hotdocs verify")
    output_fn("  read QUICKSTART.md")


# ---------------------------------------------------------------- entry point


def main(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None) -> int:
    input_fn = input_fn or input
    output_fn = output_fn or print
    detect_kwargs = {"env": env} if env is not None else {}
    env = env if env is not None else os.environ
    cwd = cwd if cwd is not None else os.getcwd()

    try:
        values, flags, positional = _parse(argv)
    except _UsageError as exc:
        return _usage(exc)

    tool = Path(tool_root)
    target = Path(cwd) / (positional[0] if positional else ".")

    refusal = _refusal(target, tool)
    if refusal:
        for line in refusal:
            _err(line)
        return 1

    endpoint = _load_endpoint(tool)
    if endpoint is not None and "--provider" in values:
        try:
            _check_provider_flags(values, _get(endpoint, "PROVIDERS"))
        except _UsageError as exc:
            return _usage(exc)

    toml = target / "hotdocs.toml"

    if "--reconfigure" in flags:
        if not (target / ".hotdocs-tool.json").is_file():
            _err(f"not an initialised project: {target} has no .hotdocs-tool.json; run hotdocs init first")
            return 1
        if endpoint is None:
            _err(_ENDPOINT_MISSING)
            return 1
        _, failed = _provider_step(endpoint, values, flags, toml, input_fn, output_fn, detect_kwargs)
        return 1 if failed else 0

    target.mkdir(parents=True, exist_ok=True)
    _skeleton(target, output_fn)
    if "--example" in flags:
        _copy_example(tool, target, output_fn)

    if toml.exists():
        output_fn("hotdocs.toml: skipped (exists)")
        config = _get(endpoint, "load_config")(toml) if endpoint is not None else None
        provider = _get(config, "provider")
    elif endpoint is None:
        output_fn(_ENDPOINT_MISSING)
        provider = None
    else:
        provider, _ = _provider_step(
            endpoint, values, flags, toml, input_fn, output_fn, detect_kwargs
        )

    missing = _prerequisites(tool_root, provider, env, output_fn)
    _next_steps("--example" in flags, output_fn)
    return 3 if missing else 0