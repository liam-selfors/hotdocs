"""hotdocs init: set up a new project for the tool.

Creates the project skeleton, reports missing prerequisites (never installing
anything), and configures and tests a language-model provider through
``llm-endpoint`` loaded from the tool root.
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
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]
_GLOSSARY = (
    "# Glossary\n"
    "\n"
    "Canonical vocabulary for this project's specs: each term is defined once "
    "here and used as defined.\n"
)


class _UsageError(Exception):
    pass


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _default_tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _parse(argv):
    opts = {key: None for key in _VALUE_FLAGS.values()}
    opts.update({key: False for key in _BOOL_FLAGS.values()})
    target = None
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
                opts[_VALUE_FLAGS[name]] = value
            elif tok in _BOOL_FLAGS:
                opts[_BOOL_FLAGS[tok]] = True
            else:
                raise _UsageError(f"unknown flag {name}")
        elif target is not None:
            raise _UsageError("unexpected second positional argument")
        else:
            target = tok
        i += 1
    return opts, target


def _check_flags(opts):
    if opts["api_key_env"] is not None and not _ENV_NAME.fullmatch(opts["api_key_env"]):
        raise _UsageError(
            "--api-key-env must be an environment-variable name "
            "(letters, digits, _, not starting with a digit)"
        )
    if opts["provider"] == "claude-cli" and (
        opts["base_url"] is not None or opts["api_key_env"] is not None
    ):
        raise _UsageError("--base-url and --api-key-env do not apply to claude-cli")
    if opts["auth"] is not None and opts["auth"] not in ("login", "key"):
        raise _UsageError("--auth must be one of: login, key")
    if opts["auth"] is not None and opts["provider"] != "claude-cli":
        raise _UsageError("--auth applies only to --provider claude-cli")


def _check_provider_flags(opts, providers):
    provider = opts["provider"]
    if provider is None:
        return
    if provider not in providers:
        raise _UsageError(
            "unknown provider; choose one of: " + ", ".join(providers.keys())
        )
    info = providers[provider]
    if not _get(info, "suggested_model") and not opts["model"]:
        raise _UsageError(f"--provider {provider} needs --model")
    if _get(info, "needs_base_url") and not opts["base_url"]:
        raise _UsageError(f"--provider {provider} needs --base-url")


def _usage(err):
    print(f"usage error: {err}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


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
            submodule_search_locations=[str(base / "llm_endpoint")],
        )
    else:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


class _Init:
    def __init__(self, opts, project, tool_root, endpoint, input_fn, output_fn, env):
        self.opts = opts
        self.project = project
        self.tool_root = tool_root
        self.endpoint = endpoint
        self.input_fn = input_fn
        self.out = output_fn
        self.env = env

    # -- skeleton -----------------------------------------------------------

    def _report(self, rel, existed):
        self.out(f"{rel}: skipped (exists)" if existed else f"{rel}: created")

    def _ensure_dir(self, rel):
        path = self.project / rel
        existed = path.exists()
        if not existed:
            path.mkdir(parents=True, exist_ok=True)
        self._report(rel, existed)

    def _ensure_file(self, rel, data):
        path = self.project / rel
        existed = path.exists()
        if not existed:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self._report(rel, existed)

    def _gitignore(self):
        path = self.project / ".gitignore"
        existed = path.exists()
        text = path.read_text(encoding="utf-8") if existed else ""
        present = set(text.splitlines())
        missing = [line for line in _GITIGNORE_LINES if line not in present]
        if missing:
            prefix = "\n" if text and not text.endswith("\n") else ""
            with open(path, "a", encoding="utf-8", newline="") as fh:
                fh.write(prefix + "".join(line + "\n" for line in missing))
        self._report(".gitignore", existed)

    def skeleton(self):
        for rel in ("specs/product", "specs/components", "specs/decisions"):
            self._ensure_dir(rel)
            self._ensure_file(rel + "/.gitkeep", b"")
        self._ensure_dir("gen")
        self._ensure_dir("verification")
        self._ensure_file("verification/.gitkeep", b"")
        self._ensure_file("specs/glossary.md", _GLOSSARY.encode("utf-8"))
        self._ensure_file(
            ".secret-allowlist.json",
            (json.dumps({"version": 1, "entries": []}, indent=2) + "\n").encode("utf-8"),
        )
        self._gitignore()
        self._ensure_file(
            ".hotdocs-tool.json",
            (json.dumps({"tool_version": TOOL_VERSION}, indent=2) + "\n").encode("utf-8"),
        )

    def example(self):
        source = Path(self.tool_root) / "examples" / "slugify"
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            rel = path.relative_to(source).as_posix()
            dest = self.project / rel
            existed = dest.exists()
            if not existed:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
            self._report(rel, existed)

    # -- provider step ------------------------------------------------------

    def _ask(self, text, default):
        question = f"{text} [{default}]:" if default else f"{text}:"
        return self.input_fn(question + " ").strip() or default

    def _detect(self):
        if self.env is None:
            return self.endpoint.detect_providers()
        return self.endpoint.detect_providers(env=self.env)

    def _choose(self):
        """Return (provider, model, base_url, api_key_env) or None."""
        opts = self.opts
        providers = _get(self.endpoint, "PROVIDERS")
        if opts["provider"] is not None:
            provider = opts["provider"]
            info = providers[provider]
            return (
                provider,
                opts["model"] or _get(info, "suggested_model"),
                opts["base_url"],
                opts["api_key_env"] or _get(info, "default_api_key_env"),
            )
        entries = list(self._detect())
        available = [e for e in entries if _get(e, "available")]
        if opts["yes"]:
            if not available:
                self.out("no provider is available: provider not configured")
                return None
            entry = available[0]
            provider = _get(entry, "provider")
            return (
                provider,
                _get(entry, "suggested_model"),
                None,
                _get(providers[provider], "default_api_key_env"),
            )
        names = [_get(e, "provider") for e in entries]
        self.out("Providers:")
        for number, entry in enumerate(entries, 1):
            status = "available" if _get(entry, "available") else "not available"
            reason = _get(entry, "reason")
            self.out(f"  {number}. {_get(entry, 'provider')} ({status}) {reason or ''}".rstrip())
        default = _get((available or entries)[0], "provider")
        provider = None
        while provider is None:
            answer = self._ask("Provider", default)
            if answer in names:
                provider = answer
            elif answer.isdigit() and 1 <= int(answer) <= len(names):
                provider = names[int(answer) - 1]
        entry = entries[names.index(provider)]
        info = providers[provider]
        model = None
        while not model:
            model = self._ask("Model", _get(entry, "suggested_model"))
        base_url = None
        if _get(info, "needs_base_url"):
            while not base_url:
                base_url = self._ask("Base URL", _get(info, "default_base_url"))
        api_key_env = None
        if provider != "claude-cli":
            api_key_env = self._ask(
                "API-key environment variable name", _get(info, "default_api_key_env")
            ) or None
        return provider, model, base_url, api_key_env

    def provider_step(self):
        """Return (chosen provider or None, status: saved|not-saved|failed)."""
        chosen = self._choose()
        if chosen is None:
            return None, "not-saved"
        provider, model, base_url, api_key_env = chosen
        kwargs = {
            key: value
            for key, value in (
                ("base_url", base_url),
                ("api_key_env", api_key_env),
                ("auth", self.opts["auth"]),
            )
            if value
        }
        if not self.opts["no_test"]:
            ok = False
            try:
                result = self.endpoint.check_connection(provider, model, **kwargs)
            except ValueError as exc:
                self.out(f"connection failed: invalid: {exc}")
            else:
                ok = bool(_get(result, "ok"))
                if ok:
                    self.out("connection ok")
                else:
                    error = _get(result, "error")
                    self.out(
                        f"connection failed: {_get(error, 'category')}: {_get(error, 'message')}"
                    )
            if not ok:
                if self.opts["provider"] is None and not self.opts["yes"]:
                    answer = self.input_fn("Save anyway? [y/N] ").strip().lower()
                    if answer not in ("y", "yes"):
                        self.out("hotdocs.toml: not saved")
                        return provider, "not-saved"
                else:
                    self.out("warning: saving although the connection test failed")
        try:
            self.endpoint.save_config(self.project / "hotdocs.toml", provider, model, **kwargs)
        except ValueError as exc:
            print(f"could not save: {exc}", file=sys.stderr)
            return provider, "failed"
        self.out(f"hotdocs.toml: saved provider {provider}")
        return provider, "saved"

    # -- prerequisites ------------------------------------------------------

    def prerequisites(self, provider):
        missing = []
        if sys.version_info < (3, 11):
            missing.append(("Python 3.11 or newer", "install Python 3.11 or newer"))
        tool_root_text = os.fspath(self.tool_root)
        requirements = Path(self.tool_root) / "requirements.txt"
        for raw in requirements.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if "==" not in line:
                continue
            name = line.split("==", 1)[0].strip()
            try:
                importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                missing.append(
                    (line, f"pip install -r {tool_root_text}/requirements.txt")
                )
        env_map = os.environ if self.env is None else self.env
        if provider == "claude-cli" and shutil.which("claude", path=env_map.get("PATH")) is None:
            missing.append(("claude on PATH", "install Claude Code and sign in"))
        for what, fix in missing:
            self.out(f"missing: {what}")
            self.out(f"  fix: {fix}")
        return bool(missing)

    def next_steps(self):
        self.out("Next steps:")
        self.out("  hotdocs lint")
        if self.opts["example"]:
            self.out("  hotdocs generate comp-slugify")
        self.out("  hotdocs verify")
        self.out("  see QUICKSTART.md")


def main(argv=None, *, tool_root=None, input_fn=None, output_fn=None, env=None, cwd=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    tool_root = _default_tool_root() if tool_root is None else tool_root
    input_fn = input if input_fn is None else input_fn
    output_fn = print if output_fn is None else output_fn
    try:
        opts, target = _parse(argv)
        _check_flags(opts)
    except _UsageError as exc:
        return _usage(exc)

    base = Path(cwd if cwd is not None else os.getcwd())
    project = base / (target or ".")
    root = Path(tool_root)

    if project.resolve() == root.resolve():
        print(
            f"init: refusing: {project} is the tool's own repository",
            file=sys.stderr,
        )
        return 1
    project_gen = project / "gen"
    collisions = (
        sorted(
            p.name
            for p in project_gen.iterdir()
            if p.is_dir() and (root / "gen" / p.name).is_dir()
        )
        if project_gen.is_dir()
        else []
    )
    if collisions:
        print(
            "init: refusing: these project components would shadow the tool's:",
            file=sys.stderr,
        )
        for name in collisions:
            print(f"  gen/{name}", file=sys.stderr)
        return 1

    if opts["reconfigure"] and not (project / ".hotdocs-tool.json").exists():
        print(
            f"init: {project} is not an initialised project "
            "(no .hotdocs-tool.json); run hotdocs init first",
            file=sys.stderr,
        )
        return 1

    endpoint = _load_endpoint(root)
    if endpoint is not None:
        try:
            _check_provider_flags(opts, _get(endpoint, "PROVIDERS"))
        except _UsageError as exc:
            return _usage(exc)

    run = _Init(opts, project, tool_root, endpoint, input_fn, output_fn, env)

    if opts["reconfigure"]:
        if endpoint is None:
            print("init: cannot reconfigure: gen/llm-endpoint is missing", file=sys.stderr)
            return 1
        _, status = run.provider_step()
        return 1 if status == "failed" else 0

    run.skeleton()
    if opts["example"]:
        run.example()

    provider = None
    config_path = project / "hotdocs.toml"
    if config_path.exists():
        output_fn("hotdocs.toml: skipped (exists)")
        if endpoint is not None:
            provider = _get(endpoint.load_config(config_path), "provider")
    elif endpoint is None:
        output_fn("provider not configured: gen/llm-endpoint is missing")
    else:
        provider, _ = run.provider_step()

    missing = run.prerequisites(provider)
    run.next_steps()
    return 3 if missing else 0
