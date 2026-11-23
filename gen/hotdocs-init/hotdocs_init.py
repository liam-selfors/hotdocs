"""hotdocs init: set up a project skeleton, report prerequisites, and
choose and test a language-model provider."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

USAGE = (
    "usage: hotdocs init [<dir>] [--example] [--reconfigure] [--provider <name>] "
    "[--model <name>] [--base-url <url>] [--api-key-env <NAME>] "
    "[--auth <login|key>] [--no-test] [--yes]"
)

VALUE_FLAGS = {
    "--provider": "provider",
    "--model": "model",
    "--base-url": "base_url",
    "--api-key-env": "api_key_env",
    "--auth": "auth",
}
BOOL_FLAGS = {
    "--example": "example",
    "--reconfigure": "reconfigure",
    "--no-test": "no_test",
    "--yes": "yes",
}

SKELETON_DIRS = (
    "specs/product",
    "specs/components",
    "specs/decisions",
    "gen",
    "verification",
)
GITKEEP_DIRS = (
    "specs/product",
    "specs/components",
    "specs/decisions",
    "verification",
)
GLOSSARY_TEXT = (
    "# Glossary\n"
    "\n"
    "This file defines the terms the specs in this project use.\n"
)
GITIGNORE_LINES = ("/.hotdocs/", "__pycache__/", "*.pyc", ".venv/", "/dist/")
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class _UsageError(Exception):
    pass


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _err(message):
    print(message, file=sys.stderr)


def _usage(cause):
    _err(f"usage error: {cause}")
    _err(USAGE)
    return 2


def _parse(argv):
    opts = SimpleNamespace(dir=None, **{v: None for v in VALUE_FLAGS.values()},
                           **{v: False for v in BOOL_FLAGS.values()})
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("-"):
            name, eq, value = token.partition("=")
            if name in VALUE_FLAGS:
                if not eq:
                    if i + 1 >= len(argv):
                        raise _UsageError(f"{name} needs a value")
                    i += 1
                    value = argv[i]
                setattr(opts, VALUE_FLAGS[name], value)
            elif name in BOOL_FLAGS and not eq:
                setattr(opts, BOOL_FLAGS[name], True)
            else:
                raise _UsageError(f"unknown argument: {name}")
        elif opts.dir is None:
            opts.dir = token
        else:
            raise _UsageError("more than one directory given")
        i += 1

    if opts.api_key_env is not None and not ENV_NAME_RE.fullmatch(opts.api_key_env):
        raise _UsageError(
            "--api-key-env must be an environment-variable name "
            "(letters, digits and _, not starting with a digit), not a key"
        )
    if opts.auth is not None and opts.auth not in ("login", "key"):
        raise _UsageError("--auth must be one of: login, key")
    if opts.provider == "claude-cli":
        if opts.base_url is not None:
            raise _UsageError("--base-url cannot be used with claude-cli")
        if opts.api_key_env is not None:
            raise _UsageError("--api-key-env cannot be used with claude-cli")
    if opts.auth is not None and opts.provider is not None and opts.provider != "claude-cli":
        raise _UsageError("--auth can only be used with claude-cli")
    return opts


def _provider_usage(providers, opts):
    if opts.provider not in providers:
        return (f"unknown provider {opts.provider!r}; expected one of: "
                f"{', '.join(providers)}")
    info = providers[opts.provider]
    if not _get(info, "suggested_model") and not opts.model:
        return f"--provider {opts.provider} needs --model"
    if _get(info, "needs_base_url") and not opts.base_url:
        return f"--provider {opts.provider} needs --base-url"
    return None


def _refusal(target, tool):
    if target.resolve() == tool.resolve():
        return [f"refusing: {target} is the tool's own repository"]
    project_gen = target / "gen"
    if not project_gen.is_dir():
        return []
    tool_gen = tool / "gen"
    clashes = sorted(
        p.name for p in project_gen.iterdir()
        if p.is_dir() and (tool_gen / p.name).is_dir()
    )
    if clashes:
        return ["refusing: these project components would shadow the tool's:"] + [
            f"  gen/{name}" for name in clashes
        ]
    return []


def _load_endpoint(tool):
    base = tool / "gen" / "llm-endpoint"
    path = base / "llm_endpoint.py"
    locations = None
    if not path.is_file():
        path = base / "llm_endpoint" / "__init__.py"
        locations = [str(path.parent)]
        if not path.is_file():
            return None
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


def _tool_version(tool):
    try:
        with open(tool / "pyproject.toml", "rb") as fh:
            data = tomllib.load(fh)
        version = data["project"]["version"]
    except Exception:
        return "unknown"
    if isinstance(version, str) and version:
        return version
    return "unknown"


def _report(output_fn, rel, existed):
    output_fn(f"{rel}: {'skipped (exists)' if existed else 'created'}")


def _write_new(path, data, rel, output_fn):
    existed = path.exists()
    if not existed:
        path.write_bytes(data)
    _report(output_fn, rel, existed)


def _skeleton(target, output_fn):
    target.mkdir(parents=True, exist_ok=True)
    for rel in SKELETON_DIRS:
        path = target / rel
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        _report(output_fn, rel, existed)
    for rel in GITKEEP_DIRS:
        _write_new(target / rel / ".gitkeep", b"", f"{rel}/.gitkeep", output_fn)
    _write_new(target / "specs" / "glossary.md", GLOSSARY_TEXT.encode("utf-8"),
               "specs/glossary.md", output_fn)
    allowlist = json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
    _write_new(target / ".secret-allowlist.json", allowlist.encode("utf-8"),
               ".secret-allowlist.json", output_fn)

    gitignore = target / ".gitignore"
    existed = gitignore.exists()
    text = gitignore.read_text(encoding="utf-8") if existed else ""
    present = set(text.splitlines())
    missing = [line for line in GITIGNORE_LINES if line not in present]
    if missing:
        prefix = "" if not text or text.endswith("\n") else "\n"
        with open(gitignore, "a", encoding="utf-8") as fh:
            fh.write(prefix + "\n".join(missing) + "\n")
    _report(output_fn, ".gitignore", existed)


def _write_marker(target, tool, output_fn):
    content = json.dumps({"tool_version": _tool_version(tool)}, indent=2) + "\n"
    _write_new(target / ".hotdocs-tool.json", content.encode("utf-8"),
               ".hotdocs-tool.json", output_fn)


def _copy_example(target, tool, output_fn):
    source = tool / "examples" / "slugify"
    for src in sorted(p for p in source.rglob("*") if p.is_file()):
        rel = src.relative_to(source).as_posix()
        dest = target / rel
        existed = dest.exists()
        if not existed:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        _report(output_fn, rel, existed)


def _ask(input_fn, text, default):
    prompt = f"{text} [{default}]: " if default else f"{text}: "
    while True:
        answer = input_fn(prompt).strip()
        if answer:
            return answer
        if default:
            return default


def _fill(info, model, base_url, api_key_env):
    model = model or _get(info, "suggested_model")
    if base_url is None and _get(info, "needs_base_url"):
        base_url = _get(info, "default_base_url")
    if api_key_env is None:
        api_key_env = _get(info, "default_api_key_env")
    return model, base_url, api_key_env


def _interactive(providers, entries, input_fn, output_fn):
    names = [_get(e, "provider") for e in entries]
    output_fn("providers:")
    for number, entry in enumerate(entries, 1):
        state = "available" if _get(entry, "available") else "not available"
        output_fn(f"  {number}. {_get(entry, 'provider')}: {state} ({_get(entry, 'reason')})")
    available = [n for n, e in zip(names, entries) if _get(e, "available")]
    default = (available or names)[0]
    while True:
        answer = input_fn(f"Provider (name or number) [{default}]: ").strip()
        if not answer:
            name = default
            break
        if answer in names:
            name = answer
            break
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            name = names[int(answer) - 1]
            break
    info = providers[name]
    model = _ask(input_fn, "Model", _get(info, "suggested_model"))
    base_url = None
    if _get(info, "needs_base_url"):
        base_url = _ask(input_fn, "Base URL", _get(info, "default_base_url"))
    api_key_env = None
    if name != "claude-cli":
        default_env = _get(info, "default_api_key_env")
        if default_env:
            prompt = f"API key environment variable NAME (not the key) [{default_env}]: "
        else:
            prompt = "API key environment variable NAME (not the key; empty for none): "
        api_key_env = input_fn(prompt).strip() or default_env
    return name, model, base_url, api_key_env


def _configure(ep, opts, target, input_fn, output_fn, env):
    """Run the provider step. Returns (provider, save_failed)."""
    providers = ep.PROVIDERS
    interactive = opts.provider is None and not opts.yes
    if opts.provider is not None:
        name = opts.provider
        model, base_url, api_key_env = _fill(
            providers[name], opts.model, opts.base_url, opts.api_key_env)
    else:
        entries = list(ep.detect_providers() if env is None
                       else ep.detect_providers(env=env))
        if interactive:
            name, model, base_url, api_key_env = _interactive(
                providers, entries, input_fn, output_fn)
        else:
            available = [e for e in entries if _get(e, "available")]
            if not available:
                output_fn("no provider is available: provider not configured")
                return None, False
            name = _get(available[0], "provider")
            model, base_url, api_key_env = _fill(
                providers[name], opts.model, opts.base_url, opts.api_key_env)

    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key_env:
        kwargs["api_key_env"] = api_key_env
    if opts.auth:
        kwargs["auth"] = opts.auth

    save = True
    if not opts.no_test:
        try:
            result = ep.check_connection(name, model, **kwargs)
            ok = bool(_get(result, "ok"))
            if ok:
                output_fn("connection ok")
            else:
                error = _get(result, "error")
                output_fn(f"connection failed: {_get(error, 'category')}: "
                          f"{_get(error, 'message')}")
        except ValueError as exc:
            ok = False
            output_fn(f"connection failed: invalid: {exc}")
        if not ok:
            if interactive:
                answer = input_fn("Save anyway? [y/N] ").strip().lower()
                save = answer in ("y", "yes")
            else:
                output_fn("warning: the connection test failed; saving the configuration anyway")

    if not save:
        output_fn("provider not saved")
        return name, False
    try:
        ep.save_config(target / "hotdocs.toml", name, model, **kwargs)
    except ValueError as exc:
        _err(f"could not save: {exc}")
        return name, True
    output_fn(f"hotdocs.toml: provider {name} saved (model {model})")
    return name, False


def _prerequisites(tool_root, tool, provider, run_env, output_fn):
    missing = False
    if sys.version_info < (3, 11):
        output_fn("missing: Python 3.11 or newer")
        output_fn("  fix: install Python 3.11 or newer")
        missing = True
    requirements = tool / "requirements.txt"
    if requirements.is_file():
        for raw in requirements.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if "==" not in line:
                continue
            name = line.split("==", 1)[0].strip()
            try:
                importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                output_fn(f"missing: {line}")
                output_fn(f"  fix: pip install -r {tool_root}/requirements.txt")
                missing = True
    if provider == "claude-cli" and shutil.which("claude", path=run_env.get("PATH")) is None:
        output_fn("missing: claude on PATH")
        output_fn("  fix: install Claude Code and sign in")
        missing = True
    return missing


def run(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None) -> int:
    input_fn = input if input_fn is None else input_fn
    output_fn = print if output_fn is None else output_fn
    run_env = os.environ if env is None else env
    base = Path.cwd() if cwd is None else Path(cwd)
    tool = Path(tool_root)

    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        return _usage(str(exc))

    target = base / opts.dir if opts.dir is not None else base

    refusal = _refusal(target, tool)
    if refusal:
        for line in refusal:
            _err(line)
        return 1

    ep = _load_endpoint(tool)
    if ep is not None and opts.provider is not None:
        cause = _provider_usage(ep.PROVIDERS, opts)
        if cause:
            return _usage(cause)

    if opts.reconfigure:
        if not (target / ".hotdocs-tool.json").is_file():
            _err(f"not an initialised project: {target} has no .hotdocs-tool.json "
                 "(run hotdocs init first)")
            return 1
        if ep is None:
            _err("cannot reconfigure: gen/llm-endpoint is missing")
            return 1
        _, save_failed = _configure(ep, opts, target, input_fn, output_fn, env)
        return 1 if save_failed else 0

    _skeleton(target, output_fn)
    _write_marker(target, tool, output_fn)
    if opts.example:
        _copy_example(target, tool, output_fn)

    provider = None
    config_path = target / "hotdocs.toml"
    if ep is None:
        output_fn("provider not configured: gen/llm-endpoint is missing")
    elif config_path.exists():
        output_fn("hotdocs.toml: skipped (exists)")
        provider = _get(ep.load_config(config_path), "provider")
    else:
        provider, _ = _configure(ep, opts, target, input_fn, output_fn, env)

    missing = _prerequisites(tool_root, tool, provider, run_env, output_fn)

    output_fn("next steps:")
    output_fn("  hotdocs lint")
    if opts.example:
        output_fn("  hotdocs generate comp-slugify")
    output_fn("  hotdocs verify")
    output_fn(f"  guide: {tool_root}/QUICKSTART.md")

    return 3 if missing else 0


def _own_tool_root():
    here = Path(__file__).resolve()
    return next(p.parent for p in here.parents if p.name == "gen")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    return run(argv, tool_root=_own_tool_root())


if __name__ == "__main__":
    raise SystemExit(main())
