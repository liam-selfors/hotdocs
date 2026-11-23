"""hotdocs init: set up a project skeleton, check prerequisites, configure a provider."""

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
    "usage: hotdocs init [<dir>] [--example] [--reconfigure] [--provider <name>] "
    "[--model <name>] [--base-url <url>] [--api-key-env <NAME>] "
    "[--auth <login|key>] [--no-test] [--yes]"
)

VALUE_FLAGS = ("--provider", "--model", "--base-url", "--api-key-env", "--auth")
BOOL_FLAGS = ("--example", "--reconfigure", "--no-test", "--yes")

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
    "This file defines the canonical terms every spec in this project uses.\n"
)
GITIGNORE_LINES = ("/.hotdocs/", "__pycache__/", "*.pyc", ".venv/")
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class _UsageError(Exception):
    pass


class _Options:
    def __init__(self):
        self.dir = "."
        self.provider = None
        self.model = None
        self.base_url = None
        self.api_key_env = None
        self.auth = None
        self.example = False
        self.reconfigure = False
        self.no_test = False
        self.yes = False


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _parse(argv):
    opts = _Options()
    positional = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        i += 1
        if tok.startswith("-"):
            name, eq, value = tok.partition("=")
            if name in VALUE_FLAGS:
                if not eq:
                    if i >= len(argv):
                        raise _UsageError(f"{name} needs a value")
                    value = argv[i]
                    i += 1
                setattr(opts, name[2:].replace("-", "_"), value)
            elif tok in BOOL_FLAGS:
                setattr(opts, tok[2:].replace("-", "_"), True)
            else:
                raise _UsageError(f"unknown argument: {tok}")
        else:
            positional.append(tok)
            if len(positional) > 1:
                raise _UsageError("only one <dir> argument is allowed")
    if positional:
        opts.dir = positional[0]
    if opts.auth is not None and opts.auth not in ("login", "key"):
        raise _UsageError("--auth must be login or key")
    if opts.api_key_env is not None and not ENV_NAME_RE.fullmatch(opts.api_key_env):
        raise _UsageError(
            "--api-key-env must be an environment variable name "
            "(letters, digits, _, not starting with a digit)"
        )
    return opts


def _usage(cause):
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def _provider_usage_error(opts, providers):
    name = opts.provider
    if name not in providers:
        return "--provider must be one of: " + ", ".join(providers)
    info = _get(providers, name)
    if name == "claude-cli" and (opts.base_url is not None or opts.api_key_env is not None):
        return "--base-url and --api-key-env do not apply to claude-cli"
    if opts.auth is not None and name != "claude-cli":
        return "--auth applies only to claude-cli"
    if not _get(info, "suggested_model") and not opts.model:
        return f"--provider {name} needs --model"
    if _get(info, "needs_base_url") and not opts.base_url:
        return f"--provider {name} needs --base-url"
    return None


def _load_endpoint(tool_root):
    base = Path(tool_root) / "gen" / "llm-endpoint"
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
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _tool_version(tool_root):
    try:
        with open(Path(tool_root) / "pyproject.toml", "rb") as fh:
            data = tomllib.load(fh)
        version = data["project"]["version"]
        if isinstance(version, str) and version:
            return version
    except Exception:
        pass
    return "unknown"


def _ask(input_fn, text):
    return input_fn(text + " ").strip()


def _ask_default(input_fn, label, default):
    while True:
        text = f"{label} [{default}]:" if default else f"{label}:"
        answer = _ask(input_fn, text)
        if answer:
            return answer
        if default:
            return default


def _configure(ep, opts, toml_path, input_fn, output_fn, env_arg):
    """Run the provider step. Returns (chosen provider or None, save_ok)."""
    providers = _get(ep, "PROVIDERS")
    interactive = False
    if opts.provider is not None:
        name = opts.provider
        info = _get(providers, name)
        model = opts.model or _get(info, "suggested_model")
        base_url = opts.base_url
        api_key_env = opts.api_key_env or _get(info, "default_api_key_env")
    else:
        detect = _get(ep, "detect_providers")
        entries = list(detect() if env_arg is None else detect(env=env_arg))
        if opts.yes:
            available = [e for e in entries if _get(e, "available")]
            if not available:
                output_fn("no provider available: nothing saved")
                return None, True
            entry = available[0]
            name = _get(entry, "provider")
            info = _get(providers, name)
            model = _get(entry, "suggested_model")
            base_url = _get(info, "default_base_url")
            api_key_env = _get(info, "default_api_key_env")
        else:
            interactive = True
            names = [_get(e, "provider") for e in entries]
            output_fn("Providers:")
            for number, e in enumerate(entries, 1):
                if _get(e, "available"):
                    status = "available"
                else:
                    status = f"not available: {_get(e, 'reason')}"
                output_fn(f"  {number}. {_get(e, 'provider')} ({status})")
            available = [n for n, e in zip(names, entries) if _get(e, "available")]
            default = (available or names)[0]
            while True:
                answer = _ask(input_fn, f"Provider [{default}]:")
                if not answer:
                    name = default
                    break
                if answer.isdigit() and 1 <= int(answer) <= len(names):
                    name = names[int(answer) - 1]
                    break
                if answer in names:
                    name = answer
                    break
            entry = entries[names.index(name)]
            info = _get(providers, name)
            model = _ask_default(input_fn, "Model", _get(entry, "suggested_model"))
            base_url = None
            if _get(info, "needs_base_url"):
                base_url = _ask_default(input_fn, "Base URL", _get(info, "default_base_url"))
            api_key_env = None
            if name != "claude-cli":
                default_env = _get(info, "default_api_key_env")
                if default_env:
                    text = f"API key environment variable name [{default_env}]:"
                else:
                    text = "API key environment variable name (empty for none):"
                api_key_env = _ask(input_fn, text) or default_env
    if not _get(info, "needs_base_url"):
        base_url = None

    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key_env:
        kwargs["api_key_env"] = api_key_env
    if opts.auth:
        kwargs["auth"] = opts.auth

    if not opts.no_test:
        try:
            result = _get(ep, "check_connection")(name, model, **kwargs)
            ok = _get(result, "ok")
            if ok:
                output_fn("connection ok")
            else:
                error = _get(result, "error")
                output_fn(
                    f"connection failed: {_get(error, 'category')}: {_get(error, 'message')}"
                )
        except ValueError as exc:
            ok = False
            output_fn(f"connection failed: invalid: {exc}")
        if not ok:
            if interactive:
                answer = _ask(input_fn, "Save anyway? [y/N]").lower()
                if answer not in ("y", "yes"):
                    output_fn("nothing saved")
                    return name, True
            else:
                output_fn("warning: saving although the connection test failed")

    try:
        _get(ep, "save_config")(toml_path, name, model, **kwargs)
    except ValueError as exc:
        print(f"could not save: {exc}", file=sys.stderr)
        return name, False
    output_fn("hotdocs.toml: saved")
    return name, True


def _report(output_fn, rel, existed):
    output_fn(f"{rel}: skipped (exists)" if existed else f"{rel}: created")


def _write_new(target, rel, data, output_fn):
    path = target / rel
    existed = path.exists()
    if not existed:
        path.write_bytes(data)
    _report(output_fn, rel, existed)


def _skeleton(target, output_fn):
    target.mkdir(parents=True, exist_ok=True)
    for rel in SKELETON_DIRS:
        path = target / rel
        existed = path.exists()
        if not existed:
            path.mkdir(parents=True)
        _report(output_fn, rel, existed)
    for rel in GITKEEP_DIRS:
        _write_new(target, f"{rel}/.gitkeep", b"", output_fn)
    _write_new(target, "specs/glossary.md", GLOSSARY_TEXT.encode("utf-8"), output_fn)
    allowlist = json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
    _write_new(target, ".secret-allowlist.json", allowlist.encode("utf-8"), output_fn)
    gitignore = target / ".gitignore"
    existed = gitignore.exists()
    text = gitignore.read_text(encoding="utf-8") if existed else ""
    present = set(text.splitlines())
    to_add = [line for line in GITIGNORE_LINES if line not in present]
    if to_add:
        prefix = "\n" if text and not text.endswith("\n") else ""
        with gitignore.open("a", encoding="utf-8") as fh:
            fh.write(prefix + "\n".join(to_add) + "\n")
    _report(output_fn, ".gitignore", existed)


def _copy_example(tool_root, target):
    source = Path(tool_root) / "examples" / "slugify"
    for path in sorted(source.rglob("*")):
        if path.is_file():
            dest = target / path.relative_to(source)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)


def run(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None):
    input_fn = input if input_fn is None else input_fn
    output_fn = print if output_fn is None else output_fn
    path_env = os.environ if env is None else env
    try:
        opts = _parse(list(argv))
    except _UsageError as exc:
        return _usage(str(exc))

    root = Path(tool_root)
    target = Path(Path.cwd() if cwd is None else cwd) / opts.dir

    if target.resolve() == root.resolve():
        print(f"init refused: {target} is the tool's own repository", file=sys.stderr)
        return 1
    clashes = []
    if (target / "gen").is_dir():
        for child in sorted((target / "gen").iterdir()):
            if child.is_dir() and (root / "gen" / child.name).is_dir():
                clashes.append(f"gen/{child.name}")
    if clashes:
        print("init refused: project components would shadow the tool's:", file=sys.stderr)
        for clash in clashes:
            print(f"  {clash}", file=sys.stderr)
        return 1

    ep = _load_endpoint(root)
    if ep is not None and opts.provider is not None:
        error = _provider_usage_error(opts, _get(ep, "PROVIDERS"))
        if error:
            return _usage(error)

    toml_path = target / "hotdocs.toml"

    if opts.reconfigure:
        if not (target / ".hotdocs-tool.json").is_file():
            print(
                f"init --reconfigure: {target} is not an initialised project "
                "(no .hotdocs-tool.json); run hotdocs init first",
                file=sys.stderr,
            )
            return 1
        if ep is None:
            print("init --reconfigure: gen/llm-endpoint is missing", file=sys.stderr)
            return 1
        _chosen, save_ok = _configure(ep, opts, toml_path, input_fn, output_fn, env)
        return 0 if save_ok else 1

    _skeleton(target, output_fn)

    marker = target / ".hotdocs-tool.json"
    if not marker.exists():
        marker.write_text(
            json.dumps({"tool_version": _tool_version(root)}) + "\n", encoding="utf-8"
        )

    if opts.example:
        _copy_example(root, target)

    ran = False
    chosen = None
    if toml_path.exists():
        output_fn("hotdocs.toml: skipped (exists)")
    elif ep is None:
        output_fn("provider not configured: gen/llm-endpoint is missing")
    else:
        ran = True
        chosen, _save_ok = _configure(ep, opts, toml_path, input_fn, output_fn, env)
    if not ran and ep is not None:
        chosen = _get(_get(ep, "load_config")(toml_path), "provider")

    missing = []
    if sys.version_info < (3, 11):
        missing.append(("Python 3.11 or newer", "install Python 3.11 or newer"))
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    for line in requirements.splitlines():
        line = line.strip()
        if "==" not in line:
            continue
        dist = line.split("==", 1)[0].strip()
        try:
            importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            missing.append((line, f"pip install -r {tool_root}/requirements.txt"))
    if chosen == "claude-cli" and shutil.which("claude", path=path_env.get("PATH")) is None:
        missing.append(("claude on PATH", "install Claude Code and sign in"))
    for what, fix in missing:
        output_fn(f"missing: {what}")
        output_fn(f"  fix: {fix}")

    output_fn("next steps:")
    output_fn("  hotdocs lint")
    if opts.example:
        output_fn("  hotdocs generate comp-slugify")
    output_fn("  hotdocs verify")
    output_fn(f"  guide: {tool_root}/QUICKSTART.md")

    return 3 if missing else 0


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    return run(argv, tool_root=_tool_root())


if __name__ == "__main__":
    sys.exit(main())
