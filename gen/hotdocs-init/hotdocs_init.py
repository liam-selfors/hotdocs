"""hotdocs init: set up a new project for the tool.

Creates the project skeleton, reports missing prerequisites, and chooses
and tests a language-model provider through ``llm-endpoint``.
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

USAGE = (
    "usage: hotdocs init [<dir>] [--example] [--reconfigure] [--provider <name>] "
    "[--model <name>] [--base-url <url>] [--api-key-env <NAME>] "
    "[--auth <login|key>] [--no-test] [--yes]"
)

_VALUE_FLAGS = ("--provider", "--model", "--base-url", "--api-key-env", "--auth")
_BOOL_FLAGS = ("--example", "--reconfigure", "--no-test", "--yes")
_DIRS = ("specs/product", "specs/components", "specs/decisions", "gen", "verification")
_GITKEEP_DIRS = ("specs/product", "specs/components", "specs/decisions", "verification")
_GITIGNORE_LINES = ("/.hotdocs/", "__pycache__/", "*.pyc", ".venv/")
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_GLOSSARY = (
    "# Glossary\n"
    "\n"
    "This file defines the project's canonical vocabulary, which every spec "
    "uses as defined here.\n"
)


class _UsageError(Exception):
    pass


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _usage(exc):
    print(f"usage error: {exc}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _parse(argv):
    opts = {
        "dir": None,
        "example": False,
        "reconfigure": False,
        "no_test": False,
        "yes": False,
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "auth": None,
    }
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-"):
            name, eq, value = tok.partition("=")
            if name in _VALUE_FLAGS:
                if not eq:
                    if i + 1 >= len(argv):
                        raise _UsageError(f"{name} needs a value")
                    i += 1
                    value = argv[i]
                opts[name[2:].replace("-", "_")] = value
            elif tok in _BOOL_FLAGS:
                opts[tok[2:].replace("-", "_")] = True
            else:
                raise _UsageError(f"unknown argument: {tok}")
        else:
            if opts["dir"] is not None:
                raise _UsageError("only one <dir> may be given")
            opts["dir"] = tok
        i += 1

    provider = opts["provider"]
    if opts["api_key_env"] is not None and not _ENV_NAME.fullmatch(opts["api_key_env"]):
        raise _UsageError(
            "--api-key-env must be an environment-variable name "
            "(letters, digits, _, not starting with a digit)"
        )
    if opts["auth"] is not None and opts["auth"] not in ("login", "key"):
        raise _UsageError("--auth must be login or key")
    if provider == "claude-cli" and (
        opts["base_url"] is not None or opts["api_key_env"] is not None
    ):
        raise _UsageError("--base-url and --api-key-env do not apply to claude-cli")
    if opts["auth"] is not None and provider is not None and provider != "claude-cli":
        raise _UsageError("--auth applies only to claude-cli")
    return opts


def _check_provider_flags(endpoint, opts):
    providers = _get(endpoint, "PROVIDERS")
    provider = opts["provider"]
    if provider not in providers:
        raise _UsageError("unknown --provider; choose one of: " + ", ".join(providers))
    info = _get(providers, provider)
    if not _get(info, "suggested_model") and opts["model"] is None:
        raise _UsageError(f"--provider {provider} needs --model")
    if _get(info, "needs_base_url") and opts["base_url"] is None:
        raise _UsageError(f"--provider {provider} needs --base-url")


def _collisions(project, tool):
    project_gen = project / "gen"
    if not project_gen.is_dir():
        return []
    return [
        f"gen/{child.name}"
        for child in sorted(project_gen.iterdir())
        if child.is_dir() and (tool / "gen" / child.name).is_dir()
    ]


def _load_endpoint(tool):
    base = tool / "gen" / "llm-endpoint"
    path = base / "llm_endpoint.py"
    search = None
    if not path.is_file():
        path = base / "llm_endpoint" / "__init__.py"
        search = [str(path.parent)]
        if not path.is_file():
            return None
    spec = importlib.util.spec_from_file_location(
        "llm_endpoint", path, submodule_search_locations=search
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    spec.loader.exec_module(module)
    return module


def _report(output_fn, rel, created):
    output_fn(f"{rel}: {'created' if created else 'skipped (exists)'}")


def _create_file(project, rel, data, output_fn):
    path = project / rel
    created = not path.exists()
    if created:
        path.write_bytes(data)
    _report(output_fn, rel, created)


def _skeleton(project, output_fn):
    project.mkdir(parents=True, exist_ok=True)
    for rel in _DIRS:
        path = project / rel
        created = not path.exists()
        path.mkdir(parents=True, exist_ok=True)
        _report(output_fn, rel, created)
        if rel in _GITKEEP_DIRS:
            _create_file(project, f"{rel}/.gitkeep", b"", output_fn)
    _create_file(project, "specs/glossary.md", _GLOSSARY.encode("utf-8"), output_fn)
    allowlist = json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
    _create_file(project, ".secret-allowlist.json", allowlist.encode("utf-8"), output_fn)

    gitignore = project / ".gitignore"
    created = not gitignore.exists()
    text = "" if created else gitignore.read_text(encoding="utf-8")
    present = text.splitlines()
    add = [line for line in _GITIGNORE_LINES if line not in present]
    if add:
        prefix = "\n" if text and not text.endswith("\n") else ""
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(prefix + "\n".join(add) + "\n")
    _report(output_fn, ".gitignore", created)

    marker = json.dumps({"tool_version": TOOL_VERSION}, indent=2) + "\n"
    _create_file(project, ".hotdocs-tool.json", marker.encode("utf-8"), output_fn)


def _copy_example(tool, project, output_fn):
    src = tool / "examples" / "slugify"
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src)
        target = project / rel
        created = not target.exists()
        if created:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        _report(output_fn, rel.as_posix(), created)


def _ask(input_fn, label, default, required=True):
    prompt = f"{label} [{default}]:" if default else f"{label}:"
    while True:
        answer = input_fn(prompt + " ").strip()
        if answer:
            return answer
        if default or not required:
            return default


def _ask_provider(entries, input_fn, output_fn):
    names = [_get(entry, "provider") for entry in entries]
    available = [name for entry, name in zip(entries, names) if _get(entry, "available")]
    default = (available or names)[0]
    output_fn("providers:")
    for number, (entry, name) in enumerate(zip(entries, names), 1):
        if _get(entry, "available"):
            status = "available"
        else:
            status = f"not available: {_get(entry, 'reason')}"
        output_fn(f"  {number}. {name} ({status})")
    while True:
        answer = input_fn(f"Provider [{default}]: ").strip()
        if not answer:
            return entries[names.index(default)]
        if answer in names:
            return entries[names.index(answer)]
        if answer.isdecimal() and 1 <= int(answer) <= len(entries):
            return entries[int(answer) - 1]


def _test_connection(endpoint, name, model, kwargs, output_fn):
    try:
        result = _get(endpoint, "check_connection")(name, model, **kwargs)
    except ValueError as exc:
        output_fn(f"connection failed: invalid: {exc}")
        return False
    if _get(result, "ok"):
        output_fn("connection ok")
        return True
    error = _get(result, "error")
    output_fn(f"connection failed: {_get(error, 'category')}: {_get(error, 'message')}")
    return False


def _provider_step(endpoint, opts, project, input_fn, output_fn, env):
    """Choose, test and save a provider. Returns (provider chosen, save did not fail)."""
    providers = _get(endpoint, "PROVIDERS")
    interactive = opts["provider"] is None and not opts["yes"]
    if opts["provider"] is not None:
        name = opts["provider"]
        suggested = _get(_get(providers, name), "suggested_model")
    else:
        detect = _get(endpoint, "detect_providers")
        entries = detect() if env is None else detect(env=env)
        if interactive:
            entry = _ask_provider(entries, input_fn, output_fn)
        else:
            available = [e for e in entries if _get(e, "available")]
            if not available:
                output_fn("no provider is available: nothing saved")
                return None, True
            entry = available[0]
        name = _get(entry, "provider")
        suggested = _get(entry, "suggested_model")

    info = _get(providers, name)
    needs_base_url = _get(info, "needs_base_url")
    model = opts["model"] or suggested
    base_url = None
    if needs_base_url:
        base_url = opts["base_url"] or _get(info, "default_base_url")
    api_key_env = opts["api_key_env"] or _get(info, "default_api_key_env")
    if interactive:
        model = _ask(input_fn, "Model", model)
        if needs_base_url:
            base_url = _ask(input_fn, "Base URL", base_url)
        if name != "claude-cli":
            api_key_env = _ask(
                input_fn, "API-key environment variable name", api_key_env, required=False
            )

    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key_env:
        kwargs["api_key_env"] = api_key_env
    if opts["auth"] is not None:
        kwargs["auth"] = opts["auth"]

    if not opts["no_test"]:
        if not _test_connection(endpoint, name, model, kwargs, output_fn):
            if interactive:
                answer = input_fn("Save anyway? [y/N] ").strip().lower()
                if answer not in ("y", "yes"):
                    output_fn("nothing saved")
                    return name, True
            else:
                output_fn("warning: the connection test failed; saving anyway")
    try:
        _get(endpoint, "save_config")(project / "hotdocs.toml", name, model, **kwargs)
    except ValueError as exc:
        print(f"could not save: {exc}", file=sys.stderr)
        return name, False
    output_fn(f"saved provider {name} to hotdocs.toml")
    return name, True


def _prerequisites(tool_root, provider, env, output_fn):
    missing = []
    if sys.version_info < (3, 11):
        missing.append(("Python 3.11 or newer", "install Python 3.11 or newer"))
    requirements = Path(tool_root) / "requirements.txt"
    for line in requirements.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "==" not in line:
            continue
        try:
            importlib.metadata.version(line.split("==", 1)[0].strip())
        except importlib.metadata.PackageNotFoundError:
            missing.append((line, f"pip install -r {tool_root}/requirements.txt"))
    if provider == "claude-cli" and shutil.which("claude", path=env.get("PATH")) is None:
        missing.append(("claude on PATH", "install Claude Code and sign in"))
    for what, fix in missing:
        output_fn(f"missing: {what}")
        output_fn(f"  fix: {fix}")
    return bool(missing)


def _next_steps(example, output_fn):
    output_fn("next steps:")
    output_fn("  hotdocs lint")
    if example:
        output_fn("  hotdocs generate comp-slugify")
    output_fn("  hotdocs verify")
    output_fn("  read QUICKSTART.md")


def run(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None):
    input_fn = input if input_fn is None else input_fn
    output_fn = print if output_fn is None else output_fn
    env_map = os.environ if env is None else env
    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        return _usage(exc)

    base = Path(os.getcwd() if cwd is None else cwd)
    project = base / opts["dir"] if opts["dir"] is not None else base
    tool = Path(tool_root)

    if project.resolve() == tool.resolve():
        print(f"init: refusing: {project} is the tool's own repository", file=sys.stderr)
        return 1
    clashes = _collisions(project, tool)
    if clashes:
        print(
            "init: refusing: these project components would shadow the tool's:",
            file=sys.stderr,
        )
        for clash in clashes:
            print(f"  {clash}", file=sys.stderr)
        return 1
    if opts["reconfigure"] and not (project / ".hotdocs-tool.json").is_file():
        print(
            f"init: --reconfigure: {project} is not an initialised project "
            "(no .hotdocs-tool.json)",
            file=sys.stderr,
        )
        return 1

    endpoint = _load_endpoint(tool)
    if endpoint is not None and opts["provider"] is not None:
        try:
            _check_provider_flags(endpoint, opts)
        except _UsageError as exc:
            return _usage(exc)

    if opts["reconfigure"]:
        if endpoint is None:
            print("provider not configured: gen/llm-endpoint is missing", file=sys.stderr)
            return 1
        _, saved = _provider_step(endpoint, opts, project, input_fn, output_fn, env)
        return 0 if saved else 1

    _skeleton(project, output_fn)
    if opts["example"]:
        _copy_example(tool, project, output_fn)

    config_path = project / "hotdocs.toml"
    provider = None
    if config_path.exists():
        output_fn("hotdocs.toml: skipped (exists)")
        if endpoint is not None:
            provider = _get(_get(endpoint, "load_config")(config_path), "provider")
    elif endpoint is None:
        output_fn("provider not configured: gen/llm-endpoint is missing")
    else:
        provider, _ = _provider_step(endpoint, opts, project, input_fn, output_fn, env)

    missing = _prerequisites(tool_root, provider, env_map, output_fn)
    _next_steps(opts["example"], output_fn)
    return 3 if missing else 0


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def main(argv=None):
    return run(sys.argv[1:] if argv is None else argv, tool_root=_tool_root())
