"""hotdocs init: set up a new hotdocs project.

Creates the project skeleton, records the tool version, configures and
tests a language-model provider through ``llm-endpoint``, and reports the
prerequisites the machine still lacks.
"""

import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import sys
import tomllib
from pathlib import Path

USAGE = (
    "usage: hotdocs init [<dir>] [--example] [--reconfigure] "
    "[--provider <name>] [--model <name>] [--base-url <url>] "
    "[--api-key-env <NAME>] [--auth <login|key>] [--no-test] [--yes]"
)

_BOOL_FLAGS = {
    "--example": "example",
    "--reconfigure": "reconfigure",
    "--no-test": "no_test",
    "--yes": "yes",
}
_VALUE_FLAGS = {
    "--provider": "provider",
    "--model": "model",
    "--base-url": "base_url",
    "--api-key-env": "api_key_env",
    "--auth": "auth",
}
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SKELETON_DIRS = (
    "specs/product",
    "specs/components",
    "specs/decisions",
    "gen",
    "verification",
)
_GITKEEP_DIRS = ("specs/product", "specs/components", "specs/decisions", "verification")
_GITIGNORE_LINES = ("/.hotdocs/", "__pycache__/", "*.pyc", ".venv/", "/dist/")
_GLOSSARY = (
    "# Glossary\n"
    "\n"
    "This file defines, once, each term this project's specs use, and the "
    "specs use every term as defined here.\n"
)
_ENDPOINT_MISSING = "provider not configured: gen/llm-endpoint is missing"


class _UsageError(Exception):
    pass


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _usage(exc):
    print(f"usage error: {exc}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _parse(argv):
    opts = {name: False for name in _BOOL_FLAGS.values()}
    opts.update({name: None for name in _VALUE_FLAGS.values()})
    opts["dir"] = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        i += 1
        if tok.startswith("-"):
            if tok in _BOOL_FLAGS:
                opts[_BOOL_FLAGS[tok]] = True
                continue
            flag, eq, value = tok.partition("=")
            if flag not in _VALUE_FLAGS:
                raise _UsageError(f"unknown argument: {flag}")
            if not eq:
                if i >= len(argv):
                    raise _UsageError(f"{flag} needs a value")
                value = argv[i]
                i += 1
            opts[_VALUE_FLAGS[flag]] = value
        elif opts["dir"] is None:
            opts["dir"] = tok
        else:
            raise _UsageError(f"unexpected argument: {tok}")

    if opts["api_key_env"] is not None and not _ENV_NAME.fullmatch(opts["api_key_env"]):
        raise _UsageError(
            "--api-key-env must be an environment-variable name "
            "(letters, digits and _, not starting with a digit)"
        )
    if opts["auth"] is not None and opts["auth"] not in ("login", "key"):
        raise _UsageError("--auth must be login or key")
    if opts["provider"] == "claude-cli":
        for key, flag in (("base_url", "--base-url"), ("api_key_env", "--api-key-env")):
            if opts[key] is not None:
                raise _UsageError(f"{flag} cannot be used with claude-cli")
    elif opts["provider"] is not None and opts["auth"] is not None:
        raise _UsageError("--auth can only be used with claude-cli")
    return opts


def _check_provider(opts, providers):
    provider = opts["provider"]
    if provider is None:
        return
    if provider not in providers:
        raise _UsageError(
            f"unknown provider {provider!r}; expected one of: {', '.join(providers)}"
        )
    entry = providers[provider]
    if not _get(entry, "suggested_model") and not opts["model"]:
        raise _UsageError(f"--provider {provider} needs --model")
    if _get(entry, "needs_base_url") and not opts["base_url"]:
        raise _UsageError(f"--provider {provider} needs --base-url")


def _tool_version(tool_root):
    try:
        with open(Path(tool_root) / "pyproject.toml", "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, ValueError):
        return "unknown"
    project = data.get("project")
    if not isinstance(project, dict):
        return "unknown"
    version = project.get("version")
    if isinstance(version, str) and version:
        return version
    return "unknown"


def _refusal(target, tool_root):
    root = Path(tool_root)
    if target.resolve() == root.resolve():
        return [f"refused: {target} is the tool's own repository"]
    gen = target / "gen"
    if gen.is_dir():
        names = sorted(
            child.name
            for child in gen.iterdir()
            if child.is_dir() and (root / "gen" / child.name).is_dir()
        )
        if names:
            return ["refused: these project components would shadow the tool's own:"] + [
                f"  gen/{name}" for name in names
            ]
    return []


def _load_endpoint(tool_root):
    base = Path(tool_root) / "gen" / "llm-endpoint"
    module_file = base / "llm_endpoint.py"
    package_init = base / "llm_endpoint" / "__init__.py"
    if module_file.is_file():
        spec = importlib.util.spec_from_file_location("llm_endpoint", module_file)
    elif package_init.is_file():
        spec = importlib.util.spec_from_file_location(
            "llm_endpoint",
            package_init,
            submodule_search_locations=[str(package_init.parent)],
        )
    else:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    spec.loader.exec_module(module)
    return module


def _create_file(target, rel, content, out):
    path = target / rel
    if path.exists():
        out(f"{rel}: skipped (exists)")
    else:
        path.write_bytes(content)
        out(f"{rel}: created")


def _update_gitignore(target, out):
    path = target / ".gitignore"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        out(".gitignore: skipped (exists)")
    else:
        text = ""
        out(".gitignore: created")
    present = set(text.splitlines())
    missing = [line for line in _GITIGNORE_LINES if line not in present]
    if missing:
        prefix = "\n" if text and not text.endswith("\n") else ""
        with path.open("a", encoding="utf-8") as handle:
            handle.write(prefix + "".join(line + "\n" for line in missing))


def _setup(target, tool_root, out):
    target.mkdir(parents=True, exist_ok=True)
    for rel in _SKELETON_DIRS:
        path = target / rel
        if path.exists():
            out(f"{rel}: skipped (exists)")
        else:
            path.mkdir(parents=True)
            out(f"{rel}: created")
        if rel in _GITKEEP_DIRS:
            _create_file(target, f"{rel}/.gitkeep", b"", out)
    _create_file(target, "specs/glossary.md", _GLOSSARY.encode("utf-8"), out)
    _create_file(
        target,
        ".secret-allowlist.json",
        (json.dumps({"version": 1, "entries": []}, indent=2) + "\n").encode("utf-8"),
        out,
    )
    _update_gitignore(target, out)
    marker = target / ".hotdocs-tool.json"
    if not marker.exists():
        marker.write_text(
            json.dumps({"tool_version": _tool_version(tool_root)}, indent=2) + "\n",
            encoding="utf-8",
        )


def _copy_example(target, tool_root):
    source = Path(tool_root) / "examples" / "slugify"
    for path in sorted(source.rglob("*")):
        if path.is_file():
            dest = target / path.relative_to(source)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)


def _ask_value(input_fn, label, default, required):
    prompt = f"{label} [{default}] " if default else f"{label} "
    while True:
        value = input_fn(prompt).strip() or default or None
        if value or not required:
            return value


def _ask(detected, providers, input_fn, out):
    names = [_get(entry, "provider") for entry in detected]
    out("providers:")
    for number, entry in enumerate(detected, 1):
        state = "available" if _get(entry, "available") else "not available"
        reason = _get(entry, "reason")
        detail = f": {reason}" if reason else ""
        out(f"  {number}. {names[number - 1]} ({state}{detail})")
    default = next(
        (name for name, entry in zip(names, detected) if _get(entry, "available")),
        names[0],
    )
    provider = None
    while provider is None:
        answer = input_fn(f"Provider [{default}] ").strip()
        if not answer:
            provider = default
        elif answer in names:
            provider = answer
        elif answer.isdigit() and 1 <= int(answer) <= len(names):
            provider = names[int(answer) - 1]
    choice = detected[names.index(provider)]
    entry = providers[provider]
    model = _ask_value(input_fn, "Model", _get(choice, "suggested_model"), True)
    base_url = None
    if _get(entry, "needs_base_url"):
        base_url = _ask_value(input_fn, "Base URL", _get(entry, "default_base_url"), True)
    api_key_env = None
    if provider != "claude-cli":
        api_key_env = _ask_value(
            input_fn,
            "API key environment variable name",
            _get(entry, "default_api_key_env"),
            False,
        )
    return provider, model, base_url, api_key_env


def _from_flags(entry, opts, suggested_model):
    model = opts["model"] or suggested_model
    base_url = None
    if _get(entry, "needs_base_url"):
        base_url = opts["base_url"] or _get(entry, "default_base_url")
    api_key_env = opts["api_key_env"] or _get(entry, "default_api_key_env")
    return model, base_url, api_key_env


def _provider_step(endpoint, target, opts, input_fn, out, env):
    """Configure, test and save the provider. Returns (provider, save_failed)."""
    providers = endpoint.PROVIDERS
    interactive = False
    if opts["provider"] is not None:
        provider = opts["provider"]
        entry = providers[provider]
        model, base_url, api_key_env = _from_flags(
            entry, opts, _get(entry, "suggested_model")
        )
    else:
        if env is None:
            detected = endpoint.detect_providers()
        else:
            detected = endpoint.detect_providers(env=env)
        if opts["yes"]:
            available = [entry for entry in detected if _get(entry, "available")]
            if not available:
                out("provider not configured: no provider is available")
                return None, False
            choice = available[0]
            provider = _get(choice, "provider")
            model, base_url, api_key_env = _from_flags(
                providers[provider], opts, _get(choice, "suggested_model")
            )
        else:
            interactive = True
            provider, model, base_url, api_key_env = _ask(
                detected, providers, input_fn, out
            )

    kwargs = {
        key: value
        for key, value in (
            ("base_url", base_url),
            ("api_key_env", api_key_env),
            ("auth", opts["auth"]),
        )
        if value
    }

    if not opts["no_test"]:
        try:
            result = endpoint.check_connection(provider, model, **kwargs)
        except ValueError as exc:
            out(f"connection failed: invalid: {exc}")
            ok = False
        else:
            ok = _get(result, "ok")
            if ok:
                out("connection ok")
            else:
                error = _get(result, "error")
                out(
                    f"connection failed: {_get(error, 'category')}: "
                    f"{_get(error, 'message')}"
                )
        if not ok:
            if interactive:
                answer = input_fn("Save anyway? [y/N] ").strip().lower()
                if answer not in ("y", "yes"):
                    out("provider not saved")
                    return provider, False
            else:
                out("warning: saving the provider although the connection test failed")

    try:
        endpoint.save_config(target / "hotdocs.toml", provider, model, **kwargs)
    except ValueError as exc:
        print(f"could not save: {exc}", file=sys.stderr)
        return provider, True
    out(f"provider saved: {provider} ({model}) in hotdocs.toml")
    return provider, False


def _prerequisites(tool_root, provider, env, out):
    missing = []
    if sys.version_info < (3, 11):
        missing.append(("Python 3.11 or newer", "install Python 3.11 or newer"))
    requirements = Path(tool_root) / "requirements.txt"
    if requirements.is_file():
        for raw in requirements.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if "==" not in line or line.startswith("#"):
                continue
            try:
                importlib.metadata.version(line.split("==", 1)[0].strip())
            except importlib.metadata.PackageNotFoundError:
                missing.append((line, f"pip install -r {tool_root}/requirements.txt"))
    if provider == "claude-cli" and shutil.which("claude", path=env.get("PATH")) is None:
        missing.append(("claude on PATH", "install Claude Code and sign in"))
    for what, fix in missing:
        out(f"missing: {what}")
        out(f"  fix: {fix}")
    return bool(missing)


def _reconfigure(endpoint, target, opts, input_fn, out, env):
    marker = target / ".hotdocs-tool.json"
    if not marker.exists():
        print(
            f"not an initialised project: {marker} does not exist; run hotdocs init first",
            file=sys.stderr,
        )
        return 1
    if endpoint is None:
        print(_ENDPOINT_MISSING, file=sys.stderr)
        return 1
    _, failed = _provider_step(endpoint, target, opts, input_fn, out, env)
    return 1 if failed else 0


def run(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None):
    input_fn = input if input_fn is None else input_fn
    out = print if output_fn is None else output_fn

    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        return _usage(exc)

    base = Path(os.getcwd() if cwd is None else cwd)
    target = base / (opts["dir"] if opts["dir"] is not None else ".")

    refusal = _refusal(target, tool_root)
    if refusal:
        for line in refusal:
            print(line, file=sys.stderr)
        return 1

    endpoint = _load_endpoint(tool_root)
    if endpoint is not None:
        try:
            _check_provider(opts, endpoint.PROVIDERS)
        except _UsageError as exc:
            return _usage(exc)

    if opts["reconfigure"]:
        return _reconfigure(endpoint, target, opts, input_fn, out, env)

    if opts["example"]:
        target.mkdir(parents=True, exist_ok=True)
        _copy_example(target, tool_root)
    _setup(target, tool_root, out)

    provider = None
    toml_path = target / "hotdocs.toml"
    if toml_path.exists():
        out("hotdocs.toml: skipped (exists)")
        if endpoint is not None:
            provider = _get(endpoint.load_config(toml_path), "provider")
    elif endpoint is None:
        out(_ENDPOINT_MISSING)
    else:
        provider, _ = _provider_step(endpoint, target, opts, input_fn, out, env)

    missing = _prerequisites(
        tool_root, provider, os.environ if env is None else env, out
    )

    out("next steps:")
    out("  hotdocs lint")
    if opts["example"]:
        out("  hotdocs generate comp-slugify")
    out("  hotdocs verify")
    out(f"  read {tool_root}/QUICKSTART.md")

    return 3 if missing else 0


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def main(argv=None):
    return run(sys.argv[1:] if argv is None else argv, tool_root=_tool_root())
