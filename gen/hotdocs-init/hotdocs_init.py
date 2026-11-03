"""Project initializer for the hotdocs pipeline tool."""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path


class UsageError(Exception):
    pass


TOOL_VERSION = "0.1.0"

GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]

GLOSSARY_CONTENT = (
    "# Glossary\n\n"
    "This file collects the vocabulary shared across this project's specs.\n"
)

ALLOWLIST_CONTENT = b'{"version": 1, "entries": []}'

FLAGS_NO_VALUE = {"--example", "--reconfigure", "--no-test", "--yes"}
FLAGS_WITH_VALUE = {"--provider", "--model", "--base-url", "--api-key-env"}


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_llm_endpoint(path):
    path = Path(path)
    name = "_hotdocs_init_vendored_llm_endpoint_" + hashlib.sha256(
        str(path.resolve()).encode("utf-8")
    ).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    old_dont_write = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old_dont_write
    return module


def _parse_args(argv):
    opts = {
        "example": False,
        "reconfigure": False,
        "no_test": False,
        "yes": False,
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "dir": None,
    }
    positionals = []
    i = 0
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok.startswith("--"):
            if "=" in tok:
                flag, _, value = tok.partition("=")
            else:
                flag, value = tok, None
            if flag in FLAGS_NO_VALUE:
                if value is not None:
                    raise UsageError(f"unknown flag: {tok}")
                key = flag[2:].replace("-", "_")
                opts[key] = True
                i += 1
            elif flag in FLAGS_WITH_VALUE:
                key = flag[2:].replace("-", "_")
                if value is not None:
                    opts[key] = value
                    i += 1
                else:
                    if i + 1 >= n:
                        raise UsageError(f"{flag} requires a value")
                    opts[key] = argv[i + 1]
                    i += 2
            else:
                raise UsageError(f"unknown flag: {flag}")
        else:
            positionals.append(tok)
            i += 1
    if len(positionals) > 1:
        raise UsageError(f"unexpected extra argument: {positionals[1]}")
    if positionals:
        opts["dir"] = positionals[0]
    return opts


def _try_load_providers(tool_root_path):
    path = tool_root_path / "gen" / "llm-endpoint" / "llm_endpoint.py"
    if not path.exists():
        return {}
    try:
        module = _load_llm_endpoint(path)
    except Exception:
        return {}
    providers = getattr(module, "PROVIDERS", {})
    if isinstance(providers, dict):
        return providers
    try:
        return dict(providers)
    except Exception:
        return {}


def _validate(opts, providers):
    if opts["provider"] is not None and providers and opts["provider"] not in providers:
        raise UsageError(
            "--provider must be one of: " + ", ".join(sorted(providers.keys()))
        )
    if opts["api_key_env"] is not None:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", opts["api_key_env"]):
            raise UsageError("--api-key-env must be a valid environment variable name")
    if opts["provider"] == "claude-cli":
        if opts["base_url"] is not None:
            raise UsageError("--base-url is not valid with --provider claude-cli")
        if opts["api_key_env"] is not None:
            raise UsageError("--api-key-env is not valid with --provider claude-cli")
    if opts["provider"] is not None and providers and opts["provider"] in providers:
        info = providers[opts["provider"]]
        suggested = _get(info, "suggested_model")
        if not suggested and opts["model"] is None:
            raise UsageError(
                f"--provider {opts['provider']} has no suggested model; --model is required"
            )
        if _get(info, "needs_base_url") and opts["base_url"] is None:
            raise UsageError(f"--provider {opts['provider']} requires --base-url")


def _ensure_dir(dir_path, rel, output_fn):
    p = dir_path / rel
    existed = p.exists()
    if not existed:
        p.mkdir(parents=True, exist_ok=True)
    output_fn(f"{rel}: created" if not existed else f"{rel}: skipped (exists)")


def _ensure_file(dir_path, rel, content, output_fn):
    p = dir_path / rel
    existed = p.exists()
    if not existed:
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            p.write_text(content)
        else:
            p.write_bytes(content)
    output_fn(f"{rel}: created" if not existed else f"{rel}: skipped (exists)")


def _ensure_gitignore(dir_path, output_fn):
    p = dir_path / ".gitignore"
    existed = p.exists()
    existing_text = p.read_text() if existed else ""
    existing_lines = existing_text.splitlines()
    to_append = [l for l in GITIGNORE_LINES if l not in existing_lines]
    if to_append:
        with p.open("a") as f:
            if existing_text and not existing_text.endswith("\n"):
                f.write("\n")
            f.write("\n".join(to_append) + "\n")
    output_fn(".gitignore: created" if not existed else ".gitignore: skipped (exists)")


def _create_skeleton(dir_path, output_fn):
    _ensure_dir(dir_path, "specs/product", output_fn)
    _ensure_file(dir_path, "specs/product/.gitkeep", b"", output_fn)
    _ensure_dir(dir_path, "specs/components", output_fn)
    _ensure_file(dir_path, "specs/components/.gitkeep", b"", output_fn)
    _ensure_dir(dir_path, "specs/decisions", output_fn)
    _ensure_file(dir_path, "specs/decisions/.gitkeep", b"", output_fn)
    _ensure_dir(dir_path, "gen", output_fn)
    _ensure_dir(dir_path, "pipeline", output_fn)
    _ensure_dir(dir_path, "verification", output_fn)
    _ensure_file(dir_path, "verification/.gitkeep", b"", output_fn)
    _ensure_file(dir_path, "specs/glossary.md", GLOSSARY_CONTENT, output_fn)
    _ensure_file(dir_path, ".secret-allowlist.json", ALLOWLIST_CONTENT, output_fn)
    _ensure_gitignore(dir_path, output_fn)


def _copytree_skip_pycache(src, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for entry in sorted(os.listdir(src)):
        if entry == "__pycache__":
            continue
        s = src / entry
        d = dst / entry
        if s.is_dir():
            _copytree_skip_pycache(s, d)
        else:
            shutil.copy2(s, d)


def _hash_entries(entries):
    h = hashlib.sha256()
    for rel, data in sorted(entries, key=lambda t: t[0]):
        h.update(rel.encode("utf-8"))
        h.update(data)
    return "sha256:" + h.hexdigest()


def _plan_vendor(dir_path, tool_root_path):
    stamp_path = dir_path / ".hotdocs-tool.json"
    existing_stamp = None
    if stamp_path.exists():
        try:
            existing_stamp = json.loads(stamp_path.read_text())
        except Exception:
            existing_stamp = None

    targets = []
    gen_src = tool_root_path / "gen"
    if gen_src.is_dir():
        for child in sorted(gen_src.iterdir(), key=lambda p: p.name):
            if child.is_dir() and child.name != "__pycache__":
                targets.append((f"gen/{child.name}", child))
    cc_src = tool_root_path / "pipeline" / "criterion-compiler"
    if cc_src.is_dir():
        targets.append(("pipeline/criterion-compiler", cc_src))

    vendored_list = existing_stamp.get("vendored", []) if existing_stamp else []

    collisions = []
    for rel, src in targets:
        target = dir_path / rel
        if target.exists() and rel not in vendored_list:
            collisions.append(rel)

    if collisions:
        msg = "refusing to vendor, colliding paths: " + ", ".join(sorted(collisions))
        return None, msg

    plan = {
        "targets": targets,
        "existing_stamp": existing_stamp,
        "vendored_list": vendored_list,
    }
    return plan, None


def _apply_vendor(dir_path, plan, output_fn):
    targets = plan["targets"]
    existing_stamp = plan["existing_stamp"]
    vendored_list = plan["vendored_list"]

    copied_rel_top = []
    for rel, src in targets:
        target = dir_path / rel
        if existing_stamp is not None and rel in vendored_list:
            output_fn(f"{rel}: skipped (vendored)")
            continue
        _copytree_skip_pycache(src, target)
        output_fn(f"{rel}: created")
        copied_rel_top.append(rel)

    if existing_stamp is None:
        file_entries = []
        for rel in copied_rel_top:
            base = dir_path / rel
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for f in files:
                    full = Path(root) / f
                    relpath = full.relative_to(dir_path).as_posix()
                    file_entries.append((relpath, full.read_bytes()))
        content_hash = _hash_entries(file_entries)
        stamp = {
            "tool_version": TOOL_VERSION,
            "vendored": sorted(copied_rel_top),
            "content_hash": content_hash,
        }
        (dir_path / ".hotdocs-tool.json").write_text(json.dumps(stamp, indent=2) + "\n")


def _copy_example(tool_root_path, dir_path, output_fn):
    src_root = tool_root_path / "examples" / "slugify"
    if not src_root.is_dir():
        return
    for root, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(files):
            full = Path(root) / f
            rel = full.relative_to(src_root)
            target = dir_path / rel
            existed = target.exists()
            if not existed:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(full, target)
            rel_str = rel.as_posix()
            output_fn(f"{rel_str}: created" if not existed else f"{rel_str}: skipped (exists)")


def _handle_failed_connection(interactive, input_fn, output_fn):
    if interactive:
        answer = (input_fn("Save anyway? [y/N]: ") or "").strip().lower()
        return answer == "y"
    output_fn("warning: saving despite failed connection test")
    return True


def _configure_and_save(opts, dir_path, llm_endpoint_path, output_fn, input_fn, env):
    module = _load_llm_endpoint(llm_endpoint_path)
    providers = getattr(module, "PROVIDERS", {})

    interactive = opts["provider"] is None and not opts["yes"]

    provider = None
    model = None
    base_url = None
    api_key_env = None
    have_choice = True

    if opts["provider"] is not None:
        provider = opts["provider"]
        info = providers.get(provider, {}) if isinstance(providers, dict) else {}
        model = opts["model"] or _get(info, "suggested_model")
        if _get(info, "needs_base_url"):
            base_url = opts["base_url"] or _get(info, "default_base_url")
        if provider != "claude-cli":
            api_key_env = (
                opts["api_key_env"]
                if opts["api_key_env"] is not None
                else _get(info, "default_api_key_env")
            )
    elif opts["yes"]:
        detected = module.detect_providers(env=env) if env is not None else module.detect_providers()
        available = [d for d in detected if _get(d, "available")]
        if not available:
            output_fn("no provider available: nothing saved")
            have_choice = False
        else:
            chosen = available[0]
            provider = _get(chosen, "provider")
            info = providers.get(provider, {}) if isinstance(providers, dict) else {}
            model = opts["model"] or _get(chosen, "suggested_model") or _get(info, "suggested_model")
            if _get(info, "needs_base_url"):
                base_url = opts["base_url"] or _get(info, "default_base_url")
            if provider != "claude-cli":
                api_key_env = (
                    opts["api_key_env"]
                    if opts["api_key_env"] is not None
                    else (_get(chosen, "api_key_env") or _get(info, "default_api_key_env"))
                )
    else:
        detected = module.detect_providers(env=env) if env is not None else module.detect_providers()
        output_fn("Available providers:")
        for idx, d in enumerate(detected, start=1):
            status = "available" if _get(d, "available") else (_get(d, "reason") or "unavailable")
            output_fn(f"  {idx}. {_get(d, 'provider')} ({status})")

        available = [d for d in detected if _get(d, "available")]
        provider_names = list(providers.keys()) if isinstance(providers, dict) else []
        if available:
            default_provider = _get(available[0], "provider")
        elif detected:
            default_provider = _get(detected[0], "provider")
        elif provider_names:
            default_provider = provider_names[0]
        else:
            default_provider = None

        while True:
            prompt = f"Provider [{default_provider}]: " if default_provider else "Provider: "
            answer = (input_fn(prompt) or "").strip()
            chosen_name = None
            if not answer:
                chosen_name = default_provider
            elif answer.isdigit() and 1 <= int(answer) <= len(detected):
                chosen_name = _get(detected[int(answer) - 1], "provider")
            elif isinstance(providers, dict) and answer in providers:
                chosen_name = answer
            if chosen_name:
                provider = chosen_name
                break
            output_fn("Unrecognised provider, please try again.")

        info = providers.get(provider, {}) if isinstance(providers, dict) else {}

        default_model = _get(info, "suggested_model") or None
        while True:
            prompt = f"Model [{default_model}]: " if default_model else "Model: "
            answer = (input_fn(prompt) or "").strip()
            model = answer or default_model
            if model:
                break
            output_fn("A model is required.")

        if _get(info, "needs_base_url"):
            default_base = _get(info, "default_base_url") or None
            while True:
                prompt = f"Base URL [{default_base}]: " if default_base else "Base URL: "
                answer = (input_fn(prompt) or "").strip()
                base_url = answer or default_base
                if base_url:
                    break
                output_fn("A base URL is required.")

        if provider != "claude-cli":
            default_key_env = _get(info, "default_api_key_env") or None
            prompt = (
                f"API key environment variable [{default_key_env}]: "
                if default_key_env
                else "API key environment variable: "
            )
            answer = (input_fn(prompt) or "").strip()
            api_key_env = answer or default_key_env

    if not have_choice:
        return {"provider": None, "save_error": None}

    do_save = True
    if not opts["no_test"]:
        try:
            result = module.check_connection(provider, model, base_url=base_url, api_key_env=api_key_env)
            ok = _get(result, "ok")
            if ok:
                output_fn("connection ok")
                do_save = True
            else:
                err = _get(result, "error")
                category = _get(err, "category")
                message = _get(err, "message")
                output_fn(f"connection failed: {category}: {message}")
                do_save = _handle_failed_connection(interactive, input_fn, output_fn)
        except ValueError as e:
            output_fn(f"connection failed: invalid: {e}")
            do_save = _handle_failed_connection(interactive, input_fn, output_fn)

    save_error = None
    if do_save:
        try:
            kwargs = {}
            if base_url:
                kwargs["base_url"] = base_url
            if api_key_env:
                kwargs["api_key_env"] = api_key_env
            module.save_config(dir_path / "hotdocs.toml", provider, model, **kwargs)
        except ValueError as e:
            print(f"could not save: {e}", file=sys.stderr)
            save_error = str(e)

    return {"provider": provider, "save_error": save_error}


def _do_reconfigure(opts, dir_path, output_fn, input_fn, env):
    llm_endpoint_path = dir_path / "gen" / "llm-endpoint" / "llm_endpoint.py"
    if not llm_endpoint_path.exists():
        print("cannot reconfigure: gen/llm-endpoint is missing", file=sys.stderr)
        return 1
    outcome = _configure_and_save(opts, dir_path, llm_endpoint_path, output_fn, input_fn, env)
    if outcome["save_error"] is not None:
        return 1
    return 0


def _importable(module_name):
    if not module_name:
        return False
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def _find_on_path(executable, path_str):
    if not path_str:
        return False
    for d in path_str.split(os.pathsep):
        if not d:
            continue
        if (Path(d) / executable).exists():
            return True
    return False


def _check_prerequisites(tool_root, tool_root_path, output_fn, env_to_use, provider_chosen, dir_path, llm_endpoint_path):
    missing = False

    if sys.version_info < (3, 10):
        output_fn("missing: Python 3.10 or newer")
        output_fn("  fix: install Python 3.10 or newer")
        missing = True

    req_path = tool_root_path / "requirements.txt"
    if req_path.exists():
        for raw_line in req_path.read_text().splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            name = line.split("==")[0].strip()
            module_name = name.replace("-", "_")
            if not _importable(module_name):
                output_fn(f"missing: {line}")
                output_fn(f"  fix: pip install -r {tool_root}/requirements.txt")
                missing = True

    effective_provider = provider_chosen
    if effective_provider is None and llm_endpoint_path.exists():
        try:
            module = _load_llm_endpoint(llm_endpoint_path)
            cfg = module.load_config(dir_path / "hotdocs.toml")
            if cfg is not None:
                effective_provider = _get(cfg, "provider")
        except ValueError:
            effective_provider = None

    if effective_provider == "claude-cli":
        path_str = env_to_use.get("PATH", "") if hasattr(env_to_use, "get") else ""
        if not _find_on_path("claude", path_str):
            output_fn("missing: claude on PATH")
            output_fn("  fix: install Claude Code and sign in")
            missing = True

    return missing


def _print_next_steps(opts, output_fn):
    output_fn("Next steps:")
    output_fn("  hotdocs lint")
    if opts["example"]:
        output_fn("  hotdocs generate comp-slugify")
    output_fn("  hotdocs verify")
    output_fn("  QUICKSTART.md")


def main(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None):
    input_fn = input_fn if input_fn is not None else input
    output_fn = output_fn if output_fn is not None else print
    env_given = env
    env_to_use = env if env is not None else os.environ
    cwd = cwd if cwd is not None else os.getcwd()

    tool_root_path = Path(tool_root)

    try:
        opts = _parse_args(argv)
        providers_for_validation = _try_load_providers(tool_root_path)
        _validate(opts, providers_for_validation)
    except UsageError as e:
        print(str(e), file=sys.stderr)
        return 2

    dir_path = Path(opts["dir"]) if opts["dir"] else Path(cwd)

    if opts["reconfigure"]:
        return _do_reconfigure(opts, dir_path, output_fn, input_fn, env_given)

    if dir_path.resolve() == tool_root_path.resolve():
        print(f"refusing to init: {dir_path} is the tool's own repository", file=sys.stderr)
        return 1

    plan, collision_error = _plan_vendor(dir_path, tool_root_path)
    if collision_error:
        print(collision_error, file=sys.stderr)
        return 1

    dir_path.mkdir(parents=True, exist_ok=True)
    _create_skeleton(dir_path, output_fn)
    _apply_vendor(dir_path, plan, output_fn)

    if opts["example"]:
        _copy_example(tool_root_path, dir_path, output_fn)

    llm_endpoint_path = dir_path / "gen" / "llm-endpoint" / "llm_endpoint.py"
    hotdocs_toml = dir_path / "hotdocs.toml"

    provider_chosen = None
    if hotdocs_toml.exists():
        output_fn("hotdocs.toml: skipped (exists)")
    elif not llm_endpoint_path.exists():
        output_fn("provider not configured: gen/llm-endpoint is missing")
    else:
        outcome = _configure_and_save(opts, dir_path, llm_endpoint_path, output_fn, input_fn, env_given)
        provider_chosen = outcome["provider"]

    missing = _check_prerequisites(
        tool_root, tool_root_path, output_fn, env_to_use, provider_chosen, dir_path, llm_endpoint_path
    )

    _print_next_steps(opts, output_fn)

    return 3 if missing else 0