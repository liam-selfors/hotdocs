"""Agentic generation: the model works through tools in a sandbox holding
only its spec bundle, writing and running its own code and tests, until it
calls ``finish``. Returns ``generator``'s ``GenerationResult``."""

import contextlib
import hashlib
import importlib.util
import json
import os
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

AGENT_PROMPT_VERSION = "agent-v2"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
BWRAP = "bwrap"

_RESULT_LIMIT = 8192
_CONTENT_LIMIT = 524288
_FILE_LIMIT = 200
_RUN_SECONDS = 60

_PROFILE = """(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath (param "ROOT")) (literal "/dev/null"))
(deny file-read-data (subpath (param "REPO")))
(allow file-read-data (subpath (param "PREFIX")) (subpath (param "ROOT")))
"""

_TOOL_TABLE = [
    ("list_files",
     "List every file at any depth under a directory, one path per line, "
     "relative to the sandbox root (e.g. bundle/01-spec.md).",
     ("path",)),
    ("read_file",
     "Read a file, given its path relative to the sandbox root.",
     ("path",)),
    ("write_file",
     "Write content to a file under work/ or scratch/, making parent "
     "directories.",
     ("path", "content")),
    ("delete_file",
     "Delete a file under work/ or scratch/.",
     ("path",)),
    ("check_import",
     "Import your module with work/ on PYTHONPATH; returns the exit code "
     "and output.",
     ()),
    ("run_scratch_tests",
     "Run pytest over scratch/ with work/ on PYTHONPATH; returns the exit "
     "code and output.",
     ()),
    ("finish",
     "Call when work/ holds your finished module; give a short summary.",
     ("summary",)),
]

_TOOL_ARGS = {name: args for name, _, args in _TOOL_TABLE}


def _tool_specs():
    return [
        {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {arg: {"type": "string"} for arg in args},
                "required": list(args),
            },
        }
        for name, description, args in _TOOL_TABLE
    ]


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent.parent


def _load(repo_dir, rel, want_file):
    local = Path(repo_dir) / rel
    found = local.is_file() if want_file else local.parent.is_dir()
    path = local if found else _tool_root() / rel
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    name = "_agentic_dep_%s_%s" % (re.sub(r"[^A-Za-z0-9]", "_", path.stem), digest)
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _isolation(allow):
    if sys.platform == "darwin" and os.path.exists(SANDBOX_EXEC):
        return "sandbox-exec"
    if sys.platform.startswith("linux") and shutil.which(BWRAP):
        return "bwrap"
    return "unisolated" if allow else "none"


def _set_limits():
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


def _slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _declared_asset_paths(repo_dir, slug):
    path = Path(repo_dir) / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    paths = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("assets:"):
            inner = line[line.find("[") + 1:line.rfind("]")]
            for item in inner.split(","):
                item = item.strip()
                if item:
                    paths.append(item.split(":", 1)[1].strip())
    return paths


class _Sandbox:
    def __init__(self, root, module, repo_dir, allow):
        self.root = root
        self.module = module
        self.repo_dir = repo_dir
        self.allow = allow
        self.finished = False
        self.isolation = None
        self.interpreter = None
        self.prefix = None

    def execute(self, name, arguments):
        text, is_error = self._call(name, arguments)
        if len(text) > _RESULT_LIMIT:
            text = text[:_RESULT_LIMIT] + "\n[truncated]"
        return text, is_error

    def _call(self, name, arguments):
        if self.finished:
            return "already finished", True
        if name not in _TOOL_ARGS:
            return "bad call: unknown tool %s" % (name,), True
        args = arguments if isinstance(arguments, dict) else {}
        for arg in _TOOL_ARGS[name]:
            if not isinstance(args.get(arg), str):
                return "bad call: missing %s" % arg, True
        try:
            if "path" in _TOOL_ARGS[name]:
                path = args["path"]
                write = name in ("write_file", "delete_file")
                if not self._path_ok(path, write):
                    return "path not allowed: %s" % path, True
            return getattr(self, "_tool_" + name)(args)
        except Exception as exc:  # execute never raises
            return "%s failed: %s" % (name, exc), True

    def _path_ok(self, path, write):
        if not path or os.path.isabs(path):
            return False
        parts = path.split("/")
        if ".." in parts:
            return False
        allowed = ("work", "scratch") if write else ("bundle", "work", "scratch")
        if parts[0] not in allowed:
            return False
        current = self.root
        for part in parts:
            current = os.path.join(current, part)
            if os.path.islink(current):
                return False
        real = os.path.realpath(os.path.join(self.root, path))
        return real == self.root or real.startswith(self.root + os.sep)

    def _full(self, path):
        return os.path.join(self.root, path)

    def _tool_list_files(self, args):
        path = args["path"]
        full = self._full(path)
        if not os.path.isdir(full):
            return "not found: %s" % path, True
        found = []
        for dirpath, _dirnames, filenames in os.walk(full):
            for filename in filenames:
                rel = os.path.relpath(os.path.join(dirpath, filename), self.root)
                found.append(rel.replace(os.sep, "/"))
        return "\n".join(sorted(found)), False

    def _tool_read_file(self, args):
        path = args["path"]
        full = self._full(path)
        if not os.path.isfile(full):
            return "not found: %s" % path, True
        with open(full, "rb") as handle:
            return handle.read().decode("utf-8", "replace"), False

    def _count_files(self):
        return sum(
            len(filenames)
            for top in ("work", "scratch")
            for _dirpath, _dirnames, filenames in os.walk(os.path.join(self.root, top))
        )

    def _tool_write_file(self, args):
        path = args["path"]
        data = args["content"].encode("utf-8")
        if len(data) > _CONTENT_LIMIT:
            return "too large: %s is %d bytes, limit %d" % (path, len(data), _CONTENT_LIMIT), True
        full = self._full(path)
        if not os.path.exists(full) and self._count_files() >= _FILE_LIMIT:
            return "too many files: limit %d" % _FILE_LIMIT, True
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data)
        return "wrote %s" % path, False

    def _tool_delete_file(self, args):
        path = args["path"]
        full = self._full(path)
        if not os.path.isfile(full):
            return "not found: %s" % path, True
        os.remove(full)
        return "deleted %s" % path, False

    def _tool_check_import(self, args):
        return self._run(["-c", "import %s" % self.module])

    def _tool_run_scratch_tests(self, args):
        return self._run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--noconftest", "scratch"])

    def _tool_finish(self, args):
        self.finished = True
        return "finished", False

    def _python(self):
        if self.interpreter is None:
            adapter = _load(self.repo_dir, "gen/kind-python/kind_python.py", True)
            report = adapter.provision(self.repo_dir)
            self.interpreter = str(_get(report, "interpreter"))
        return self.interpreter

    def _prefix(self, python):
        if self.prefix is None:
            out = subprocess.run(
                [python, "-I", "-c", "import sys; print(sys.prefix)"],
                capture_output=True, text=True,
            ).stdout.strip()
            self.prefix = os.path.realpath(out)
        return self.prefix

    def _run(self, tail):
        level = _isolation(self.allow)
        if level == "none":
            return "no OS sandbox available: code is not run", True
        python = self._python()
        command = [python] + tail
        repo_real = os.path.realpath(str(self.repo_dir))
        if level == "sandbox-exec":
            profile = self.root + ".sb"
            with open(profile, "w", encoding="utf-8") as handle:
                handle.write(_PROFILE)
            argv = [
                SANDBOX_EXEC, "-f", profile,
                "-D", "ROOT=%s" % self.root,
                "-D", "REPO=%s" % repo_real,
                "-D", "PREFIX=%s" % self._prefix(python),
            ] + command
        elif level == "bwrap":
            prefix = self._prefix(python)
            argv = [
                shutil.which(BWRAP),
                "--ro-bind", "/", "/",
                "--tmpfs", repo_real,
                "--ro-bind", prefix, prefix,
                "--bind", self.root, self.root,
                "--dev", "/dev",
                "--proc", "/proc",
                "--unshare-net",
                "--die-with-parent",
                "--chdir", self.root,
                "--",
            ] + command
        else:
            argv = command
        self.isolation = level
        tmp = os.path.join(self.root, "tmp")
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": tmp,
            "TMPDIR": tmp,
            "PYTHONPATH": os.path.join(self.root, "work"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        proc = subprocess.Popen(
            argv, cwd=self.root, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            preexec_fn=_set_limits, start_new_session=True,
        )
        try:
            out, _ = proc.communicate(timeout=_RUN_SECONDS)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
            return "timeout\n" + out.decode("utf-8", "replace"), False
        return "%d\n%s" % (proc.returncode, out.decode("utf-8", "replace")), False


def _system_text(component_id, module, asset_paths):
    if asset_paths:
        assets = (
            "plus each of these declared asset files: "
            + ", ".join("work/%s" % path for path in asset_paths)
            + ", and no other non-.py file"
        )
    else:
        assets = "and no other non-.py file (this component declares no asset files)"
    return (
        "You are generating the code of the component %s inside a sandbox "
        "directory, <root>. Every path you give a tool is relative to <root> "
        "and written with '/'. The sandbox holds exactly these directories:\n"
        "- bundle/: your spec bundle, read-only.\n"
        "- work/: the only output. When you finish it must hold %s.py or "
        "%s/__init__.py, %s.\n"
        "- scratch/: your own tests, run by run_scratch_tests with pytest. "
        "It is discarded when you finish.\n"
        "- tmp/: HOME and TMPDIR of the code you run.\n"
        "You have no other access: no network, no repository, nothing outside "
        "the sandbox. check_import runs `import %s` with work/ on PYTHONPATH. "
        "When you are done, call the tool finish."
        % (component_id, module, module, assets, module)
    )


def _prompt_text(names, module):
    listing = "\n".join("- %s" % name for name in names)
    return (
        "Your spec bundle is these files, in order:\n"
        + listing
        + "\n\nRead them all with read_file before writing anything. Then "
        "write the module %s in work/, write tests in scratch/, run "
        "check_import and run_scratch_tests, revise until they pass, and "
        "call finish." % module
    )


def _remove(root):
    with contextlib.suppress(FileNotFoundError):
        os.chmod(os.path.join(root, "bundle"), 0o755)
    shutil.rmtree(root, ignore_errors=True)
    with contextlib.suppress(FileNotFoundError):
        os.remove(root + ".sb")


def _collect(work):
    paths = {}
    for dirpath, _dirnames, filenames in os.walk(work):
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            if stat.S_ISREG(os.lstat(full).st_mode):
                paths[os.path.relpath(full, work).replace(os.sep, "/")] = full
    return dict(sorted(paths.items()))


def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,
                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,
                     wall_seconds=1800.0, claude_command="claude"):
    repo_dir = Path(repo_root) if repo_root is not None else Path.cwd()
    gen = _load(repo_dir, "gen/generator/generator.py", False)
    component_id = bundle["component_id"]
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    module = slug.replace("-", "_")

    def result(**fields):
        base = {
            "component_id": component_id,
            "spec_bundle_hash": bundle["spec_bundle_hash"],
            "model": model,
            "prompt_version": AGENT_PROMPT_VERSION,
            "cache_hit": False,
            "files": {},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": retry_feedback,
            "mode": "agentic",
            "transcript_sha256": None,
            "turns": 0,
            "tool_calls": 0,
            "isolation": _isolation(allow_unisolated_exec),
        }
        base.update(fields)
        return gen.GenerationResult(**base)

    reason = gen.check_write_allowed(bundle, repo_root)
    if reason is not None:
        return result(refused=reason)
    category, messages = gen.check_asset_environment(component_id, repo_root)
    if category is not None:
        return result(model_call_error={"category": category, "message": "\n".join(messages)})

    tool_endpoint = _load(repo_dir, "gen/llm-tool-endpoint/llm_tool_endpoint.py", False)
    sections = gen.render_prompt_sections(bundle, retry_feedback)
    asset_paths = _declared_asset_paths(repo_dir, slug)

    root = os.path.realpath(tempfile.mkdtemp(prefix="hotdocs-agent-"))
    try:
        bundle_dir = os.path.join(root, "bundle")
        os.mkdir(bundle_dir)
        names = []
        for position, (title, text) in enumerate(sections, start=1):
            filename = "%02d-%s.md" % (position, _slugify(title))
            full = os.path.join(bundle_dir, filename)
            with open(full, "wb") as handle:
                handle.write(text.encode("utf-8"))
            os.chmod(full, 0o444)
            names.append("bundle/" + filename)
        os.chmod(bundle_dir, 0o555)
        for name in ("work", "scratch", "tmp"):
            os.mkdir(os.path.join(root, name))

        sandbox = _Sandbox(root, module, repo_dir, allow_unisolated_exec)
        loop = tool_endpoint.run_tool_loop(
            _system_text(component_id, module, asset_paths),
            _prompt_text(names, module),
            model,
            _tool_specs(),
            sandbox.execute,
            max_turns=max_turns,
            max_tool_calls=max_tool_calls,
            wall_seconds=wall_seconds,
            repo_root=repo_root,
            claude_command=claude_command,
        )
        transcript = _get(loop, "transcript")
        digest = hashlib.sha256(
            json.dumps(transcript, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        common = {
            "turns": _get(loop, "turns"),
            "tool_calls": _get(loop, "tool_calls"),
            "transcript_sha256": "sha256:" + digest,
            "isolation": sandbox.isolation or _isolation(allow_unisolated_exec),
        }

        if not sandbox.finished:
            stop = _get(loop, "stop")
            if stop == "error":
                error = _get(loop, "model_call_error")
            elif stop == "budget_exhausted":
                error = {"category": "agent_budget_exhausted",
                         "message": "the agent stopped without calling finish: %s" % stop}
            else:
                error = {"category": "agent_unfinished",
                         "message": "the agent stopped without calling finish: %s" % stop}
            return result(model_call_error=error, **common)

        files = {}
        for rel, full in _collect(os.path.join(root, "work")).items():
            with open(full, "rb") as handle:
                data = handle.read()
            try:
                files[rel] = data.decode("utf-8")
            except UnicodeDecodeError:
                return result(model_call_error={
                    "category": "undecodable_file",
                    "message": "work/%s is not valid UTF-8" % rel,
                }, **common)
        if "%s.py" % module not in files and "%s/__init__.py" % module not in files:
            return result(model_call_error={
                "category": "missing_module",
                "message": "work/ holds neither %s.py nor %s/__init__.py" % (module, module),
            }, **common)
        asset_category, asset_messages = gen.check_assets(component_id, files, repo_root=repo_root)
        if asset_category is not None:
            return result(model_call_error={
                "category": asset_category,
                "message": "\n".join(asset_messages),
            }, **common)
        if bundle["hint_code"] is None:
            gen.write_files(component_id, files, repo_root=repo_root)
        return result(files=files, **common)
    finally:
        _remove(root)
