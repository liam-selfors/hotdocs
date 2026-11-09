import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

TOOL_VERSION = "0.1.0"

GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]

GLOSSARY_CONTENT = (
    b"# Glossary\n\n"
    b"This glossary defines the terms used across this project's specs.\n"
)

ALLOWLIST_CONTENT = (json.dumps({"version": 1, "entries": []}, indent=2) + "\n").encode("utf-8")

BOOL_FLAGS = {"--example", "--reconfigure", "--no-test", "--yes"}
VALUE_FLAGS = {"--provider", "--model", "--base-url", "--api-key-env"}

ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UsageError(Exception):
    pass


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class _Args:
    def __init__(self):
        self.dir = None
        self.example = False
        self.reconfigure = False
        self.provider = None
        self.model = None
        self.base_url = None
        self.api_key_env = None
        self.no_test = False
        self.yes = False


def _parse_args(argv):
    args = _Args()
    i = 0
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok.startswith("--"):
            if "=" in tok:
                flag, _, val = tok.partition("=")
            else:
                flag, val = tok, None
            if flag in BOOL_FLAGS:
                setattr(args, flag[2:].replace("-", "_"), True)
                i += 1
                continue
            if flag in VALUE_FLAGS:
                if val is None:
                    if i + 1 >= n:
                        raise UsageError(f"{flag} requires a value")
                    val = argv[i + 1]
                    i += 2
                else:
                    i += 1
                setattr(args, flag[2:].replace("-", "_"), val)
                continue
            raise UsageError(f"unknown flag: {flag}")
        else:
            if args.dir is not None:
                raise UsageError(f"unexpected argument: {tok}")
            args.dir = tok
            i += 1
    return args


def _validate_syntax(args):
    if args.api_key_env is not None and not ENV_NAME_RE.match(args.api_key_env):
        raise UsageError("invalid --api-key-env name")
    if args.provider == "claude-cli" and (args.base_url is not None or args.api_key_env is not None):
        raise UsageError("--base-url and --api-key-env are not valid with claude-cli")


def _validate_with_providers(args, providers):
    if args.provider is None:
        return
    if args.provider not in providers:
        keys = ", ".join(sorted(providers.keys()))
        raise UsageError(f"--provider must be one of: {keys}")
    info = providers[args.provider]
    suggested = _get(info, "suggested_model")
    needs_base = _get(info, "needs_base_url")
    if not suggested and args.model is None:
        raise UsageError(f"--provider {args.provider} requires --model")
    if needs_base and args.base_url is None:
        raise UsageError(f"--provider {args.provider} requires --base-url")


def _refusal_check(dir_path, tool_root_path):
    messages = []
    if dir_path.resolve() == tool_root_path.resolve():
        messages.append(f"refusing: {dir_path} is the tool's own repository")
        return messages
    dir_gen = dir_path / "gen"
    tool_gen = tool_root_path / "gen"
    if dir_gen.is_dir() and tool_gen.is_dir():
        dir_names = {p.name for p in dir_gen.iterdir() if p.is_dir()}
        tool_names = {p.name for p in tool_gen.iterdir() if p.is_dir()}
        for name in sorted(dir_names & tool_names):
            messages.append(f"refusing: gen/{name} would shadow the tool's own component")
    return messages


def _load_llm_endpoint(tool_root_path):
    mod_path = tool_root_path / "gen" / "llm-endpoint" / "llm_endpoint.py"
    if not mod_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("llm_endpoint", mod_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    spec.loader.exec_module(module)
    return module


def _ensure_dir(path, rel, output_fn):
    if path.exists():
        output_fn(f"{rel}: skipped (exists)")
    else:
        path.mkdir(parents=True, exist_ok=True)
        output_fn(f"{rel}: created")


def _ensure_file(path, rel, content_bytes, output_fn):
    if path.exists():
        output_fn(f"{rel}: skipped (exists)")
    else:
        path.write_bytes(content_bytes)
        output_fn(f"{rel}: created")


def _setup_gitignore(dir_path, output_fn):
    path = dir_path / ".gitignore"
    if path.exists():
        content = path.read_text()
        lines = content.splitlines()
        to_add = [line for line in GITIGNORE_LINES if line not in lines]
        if to_add:
            needs_newline = content != "" and not content.endswith("\n")
            with path.open("a") as f:
                if needs_newline:
                    f.write("\n")
                for line in to_add:
                    f.write(line + "\n")
        output_fn(".gitignore: skipped (exists)")
    else:
        path.write_text("\n".join(GITIGNORE_LINES) + "\n")
        output_fn(".gitignore: created")


def _setup_skeleton(dir_path, output_fn):
    dir_names = ["specs/product", "specs/components", "specs/decisions", "gen", "verification"]
    for d in dir_names:
        _ensure_dir(dir_path / d, d, output_fn)

    gitkeep_dirs = ["specs/product", "specs/components", "specs/decisions", "verification"]
    for d in gitkeep_dirs:
        rel = f"{d}/.gitkeep"
        _ensure_file(dir_path / d / ".gitkeep", rel, b"", output_fn)

    _ensure_file(dir_path / "specs" / "glossary.md", "specs/glossary.md", GLOSSARY_CONTENT, output_fn)
    _ensure_file(dir_path / ".secret-allowlist.json", ".secret-allowlist.json", ALLOWLIST_CONTENT, output_fn)
    _setup_gitignore(dir_path, output_fn)


def _write_tool_marker(dir_path):
    path = dir_path / ".hotdocs-tool.json"
    if not path.exists():
        path.write_text(json.dumps({"tool_version": TOOL_VERSION}, indent=2) + "\n")


def _copy_example(tool_root_path, dir_path):
    src_root = tool_root_path / "examples" / "slugify"
    if not src_root.exists():
        return
    for src in sorted(src_root.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(src_root)
        dest = dir_path / rel
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())


def _detect(llm_endpoint_mod, env, env_given):
    if env_given:
        return llm_endpoint_mod.detect_providers(env=env)
    return llm_endpoint_mod.detect_providers()


def _test_connection(llm_endpoint_mod, provider, model, base_url, api_key_env, output_fn):
    try:
        result = llm_endpoint_mod.check_connection(provider, model, base_url=base_url, api_key_env=api_key_env)
    except ValueError as e:
        output_fn(f"connection failed: invalid: {e}")
        return False
    ok = _get(result, "ok")
    if ok:
        output_fn("connection ok")
        return True
    err = _get(result, "error")
    category = _get(err, "category")
    message = _get(err, "message")
    output_fn(f"connection failed: {category}: {message}")
    return False


def _ask_provider(detected, providers, input_fn, output_fn):
    output_fn("Available providers:")
    for i, p in enumerate(detected, 1):
        name = _get(p, "provider")
        available = _get(p, "available")
        reason = _get(p, "reason")
        status = "available" if available else f"unavailable ({reason})"
        output_fn(f"  {i}. {name} - {status}")

    name_to_entry = {_get(p, "provider"): p for p in detected}
    available_names = [_get(p, "provider") for p in detected if _get(p, "available")]
    default_name = available_names[0] if available_names else _get(detected[0], "provider")

    while True:
        answer = input_fn(f"Provider [{default_name}]:" + " ").strip()
        if answer == "":
            chosen = default_name
            break
        if answer in name_to_entry:
            chosen = answer
            break
        try:
            idx = int(answer)
        except ValueError:
            idx = None
        if idx is not None and 1 <= idx <= len(detected):
            chosen = _get(detected[idx - 1], "provider")
            break
        output_fn(f"unrecognised provider: {answer}")

    info = providers[chosen]
    chosen_entry = name_to_entry.get(chosen)
    suggested_model = (_get(chosen_entry, "suggested_model") if chosen_entry else None) or _get(info, "suggested_model")

    while True:
        prompt = f"Model [{suggested_model}]:" if suggested_model else "Model:"
        answer = input_fn(prompt + " ").strip()
        if answer:
            model = answer
            break
        if suggested_model:
            model = suggested_model
            break
        output_fn("a model is required")

    base_url = None
    if _get(info, "needs_base_url"):
        default_base = _get(info, "default_base_url")
        while True:
            prompt = f"Base URL [{default_base}]:" if default_base else "Base URL:"
            answer = input_fn(prompt + " ").strip()
            if answer:
                base_url = answer
                break
            if default_base:
                base_url = default_base
                break
            output_fn("a base URL is required")

    api_key_env = None
    if chosen != "claude-cli":
        default_key_env = _get(info, "default_api_key_env")
        prompt = f"API key environment variable [{default_key_env}]:" if default_key_env else "API key environment variable:"
        answer = input_fn(prompt + " ").strip()
        api_key_env = answer if answer else default_key_env

    return chosen, model, base_url, api_key_env


def _run_provider_step(dir_path, args, llm_endpoint_mod, env, env_given, input_fn, output_fn):
    if llm_endpoint_mod is None:
        output_fn("provider not configured: gen/llm-endpoint is missing")
        return None, True

    providers = llm_endpoint_mod.PROVIDERS

    provider = model = base_url = api_key_env = None
    interactive = False

    if args.provider is not None:
        provider = args.provider
        info = providers[provider]
        model = args.model if args.model is not None else _get(info, "suggested_model")
        if _get(info, "needs_base_url"):
            base_url = args.base_url if args.base_url is not None else _get(info, "default_base_url")
        if provider != "claude-cli":
            api_key_env = args.api_key_env if args.api_key_env is not None else _get(info, "default_api_key_env")
    elif args.yes:
        detected = _detect(llm_endpoint_mod, env, env_given)
        available = [p for p in detected if _get(p, "available")]
        if not available:
            output_fn("no provider available: nothing configured")
            return None, False
        chosen = available[0]
        provider = _get(chosen, "provider")
        info = providers[provider]
        model = _get(chosen, "suggested_model") or _get(info, "suggested_model")
        if _get(info, "needs_base_url"):
            base_url = _get(info, "default_base_url")
        if provider != "claude-cli":
            api_key_env = _get(chosen, "api_key_env")
    else:
        interactive = True
        detected = _detect(llm_endpoint_mod, env, env_given)
        if not detected:
            output_fn("no provider available: nothing configured")
            return None, False
        provider, model, base_url, api_key_env = _ask_provider(detected, providers, input_fn, output_fn)

    if not args.no_test:
        ok = _test_connection(llm_endpoint_mod, provider, model, base_url, api_key_env, output_fn)
    else:
        ok = True

    if not ok:
        if interactive:
            answer = input_fn("Save anyway? [y/N] ").strip().lower()
            save_anyway = answer == "y"
        else:
            output_fn("warning: saving despite failed connection test")
            save_anyway = True
        if not save_anyway:
            return provider, False

    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key_env:
        kwargs["api_key_env"] = api_key_env

    try:
        llm_endpoint_mod.save_config(dir_path / "hotdocs.toml", provider, model, **kwargs)
    except ValueError as e:
        print(f"could not save: {e}", file=sys.stderr)
        return provider, True

    return provider, False


def _check_prereqs(tool_root_arg, tool_root_path, final_provider, env, output_fn):
    missing = []

    if sys.version_info < (3, 11):
        missing.append(("Python 3.11 or newer", "install Python 3.11 or newer"))

    req_file = tool_root_path / "requirements.txt"
    if req_file.exists():
        for raw_line in req_file.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            name = line.split("==")[0].strip()
            try:
                importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                missing.append((line, f"pip install -r {tool_root_arg}/requirements.txt"))

    if final_provider == "claude-cli":
        if shutil.which("claude", path=env.get("PATH")) is None:
            missing.append(("claude on PATH", "install Claude Code and sign in"))

    for item, fix in missing:
        output_fn(f"missing: {item}")
        output_fn(f"  fix: {fix}")

    return missing


def _print_next_steps(args, output_fn):
    output_fn("Next steps:")
    output_fn("  hotdocs lint")
    if args.example:
        output_fn("  hotdocs generate comp-slugify")
    output_fn("  hotdocs verify")
    output_fn("  QUICKSTART.md")


def _do_reconfigure(dir_path, tool_root_arg, tool_root_path, args, llm_endpoint_mod, env, env_given, input_fn, output_fn):
    marker = dir_path / ".hotdocs-tool.json"
    if not marker.exists():
        print(f"not an initialized project: {dir_path} has no .hotdocs-tool.json", file=sys.stderr)
        return 1

    if llm_endpoint_mod is None:
        print("provider not configured: gen/llm-endpoint is missing", file=sys.stderr)
        return 1

    provider, failed = _run_provider_step(dir_path, args, llm_endpoint_mod, env, env_given, input_fn, output_fn)
    if failed:
        return 1

    missing = _check_prereqs(tool_root_arg, tool_root_path, provider, env, output_fn)
    _print_next_steps(args, output_fn)
    return 3 if missing else 0


def main(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None):
    if input_fn is None:
        input_fn = input
    if output_fn is None:
        output_fn = print

    env_given = env is not None
    if env is None:
        env = os.environ

    base_cwd = Path(cwd) if cwd is not None else Path.cwd()
    tool_root_arg = tool_root
    tool_root_path = Path(tool_root)

    try:
        args = _parse_args(argv)
        _validate_syntax(args)
    except UsageError as e:
        print(str(e), file=sys.stderr)
        return 2

    dir_arg = args.dir if args.dir is not None else "."
    dir_path = Path(dir_arg)
    if not dir_path.is_absolute():
        dir_path = base_cwd / dir_path

    refusal_messages = _refusal_check(dir_path, tool_root_path)
    if refusal_messages:
        for m in refusal_messages:
            print(m, file=sys.stderr)
        return 1

    llm_endpoint_mod = _load_llm_endpoint(tool_root_path)
    providers = llm_endpoint_mod.PROVIDERS if llm_endpoint_mod is not None else None

    if providers is not None:
        try:
            _validate_with_providers(args, providers)
        except UsageError as e:
            print(str(e), file=sys.stderr)
            return 2

    if args.reconfigure:
        return _do_reconfigure(
            dir_path, tool_root_arg, tool_root_path, args, llm_endpoint_mod, env, env_given, input_fn, output_fn
        )

    dir_path.mkdir(parents=True, exist_ok=True)
    _setup_skeleton(dir_path, output_fn)
    _write_tool_marker(dir_path)

    if args.example:
        _copy_example(tool_root_path, dir_path)

    config_path = dir_path / "hotdocs.toml"
    final_provider = None

    if config_path.exists():
        output_fn("hotdocs.toml: kept (exists)")
        if llm_endpoint_mod is not None:
            try:
                existing = llm_endpoint_mod.load_config(config_path)
            except ValueError:
                existing = None
            if existing is not None:
                final_provider = _get(existing, "provider")
    else:
        final_provider, _failed = _run_provider_step(
            dir_path, args, llm_endpoint_mod, env, env_given, input_fn, output_fn
        )

    missing = _check_prereqs(tool_root_arg, tool_root_path, final_provider, env, output_fn)

    _print_next_steps(args, output_fn)

    return 3 if missing else 0