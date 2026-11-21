"""Agentic generation: the model works through tools inside a sandbox that
holds only its spec bundle, writes and tests its own code, and calls
`finish`; the candidate under `work/` becomes a `GenerationResult`."""

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
import uuid
from pathlib import Path

AGENT_PROMPT_VERSION = "agent-v2"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
BWRAP = "bwrap"

_TEXT_LIMIT = 8192
_MAX_BYTES = 524288
_MAX_FILES = 200
_RUN_SECONDS = 60

_PROFILE = """(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath (param "ROOT")) (literal "/dev/null"))
(deny file-read-data (subpath (param "REPO")))
(allow file-read-data (subpath (param "PREFIX")) (subpath (param "ROOT")))
"""

_TOOLS = (
    ("list_files",
     "List every file at any depth under a directory, one path per line, "
     "relative to the sandbox root, ready to pass to read_file.",
     ("path",)),
    ("read_file", "Read a file's text.", ("path",)),
    ("write_file",
     "Write text to a file under work/ or scratch/, making parent directories.",
     ("path", "content")),
    ("delete_file", "Delete a file under work/ or scratch/.", ("path",)),
    ("check_import",
     "Import the component's module from work/; returns the exit code and output.",
     ()),
    ("run_scratch_tests",
     "Run pytest over scratch/; returns the exit code and output.",
     ()),
    ("finish",
     "Finish: work/ is your final output. Every later call is refused.",
     ("summary",)),
)
_ARGS = {name: args for name, _description, args in _TOOLS}
_WRITE_TOOLS = ("write_file", "delete_file")


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_file(path):
    name = f"_agentic_generator_dep_{path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependency(repo_root, slug, module_name):
    directory = Path(repo_root) / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    return _load_file(directory / f"{module_name}.py")


def _load_python_adapter(repo_root):
    path = Path(repo_root) / "gen" / "kind-python" / "kind_python.py"
    if not path.is_file():
        path = _tool_root() / "gen" / "kind-python" / "kind_python.py"
    return _load_file(path)


def _isolation(allow_unisolated_exec):
    if sys.platform == "darwin" and os.path.exists(SANDBOX_EXEC):
        return "sandbox-exec"
    if sys.platform.startswith("linux") and shutil.which(BWRAP):
        return "bwrap"
    return "unisolated" if allow_unisolated_exec else "none"


def _limit_child():
    resource.setrlimit(resource.RLIMIT_CPU, (_RUN_SECONDS, _RUN_SECONDS))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


def _declared_asset_paths(repo_root, slug):
    path = Path(repo_root) / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("assets:"):
            inner = line.split("[", 1)[1].split("]", 1)[0]
            return [item.strip().split(":", 1)[1].strip()
                    for item in inner.split(",") if item.strip()]
    return []


class _Sandbox:
    def __init__(self, root, module, repo_root, allow_unisolated_exec):
        self.root = root
        self.module = module
        self.repo_root = repo_root
        self.allow_unisolated_exec = allow_unisolated_exec
        self.finished = False
        self.isolation = None
        self._python = None

    def execute(self, name, arguments):
        text, is_error = self._call(name, arguments)
        if len(text) > _TEXT_LIMIT:
            text = text[:_TEXT_LIMIT] + "\n[truncated]"
        return text, is_error

    def _call(self, name, arguments):
        if self.finished:
            return "already finished", True
        if name not in _ARGS:
            return f"bad call: unknown tool {name}", True
        for arg in _ARGS[name]:
            if not isinstance(arguments.get(arg), str):
                return f"bad call: missing {arg}", True
        target = None
        if "path" in _ARGS[name]:
            target = self._resolve(arguments["path"], name in _WRITE_TOOLS)
            if target is None:
                return f"path not allowed: {arguments['path']}", True
        try:
            return getattr(self, "_tool_" + name)(target, arguments)
        except OSError as exc:
            return f"{name} failed: {exc}", True

    def _resolve(self, path, writable):
        allowed = ("work", "scratch") if writable else ("bundle", "work", "scratch")
        parts = path.split("/")
        if ".." in parts or parts[0] not in allowed:
            return None
        current = self.root
        for part in parts:
            current = os.path.join(current, part)
            if os.path.islink(current):
                return None
        target = os.path.join(self.root, path)
        real = os.path.realpath(target)
        if not real.startswith(self.root + os.sep):
            return None
        return target

    def _relative(self, full):
        return os.path.relpath(full, self.root).replace(os.sep, "/")

    def _count_files(self):
        return sum(len(files)
                   for top in ("work", "scratch")
                   for _dir, _subdirs, files in os.walk(os.path.join(self.root, top)))

    def _tool_list_files(self, target, arguments):
        if not os.path.isdir(target):
            return f"not found: {arguments['path']}", True
        names = [self._relative(os.path.join(dirpath, name))
                 for dirpath, _subdirs, files in os.walk(target)
                 for name in files]
        return "\n".join(sorted(names)), False

    def _tool_read_file(self, target, arguments):
        if not os.path.isfile(target):
            return f"not found: {arguments['path']}", True
        return Path(target).read_bytes().decode("utf-8", "replace"), False

    def _tool_write_file(self, target, arguments):
        path = arguments["path"]
        data = arguments["content"].encode("utf-8")
        if len(data) > _MAX_BYTES:
            return f"too large: {path} is {len(data)} bytes, limit {_MAX_BYTES}", True
        if not os.path.exists(target) and self._count_files() >= _MAX_FILES:
            return f"too many files: limit {_MAX_FILES}", True
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
        return f"wrote {path}", False

    def _tool_delete_file(self, target, arguments):
        if not os.path.isfile(target):
            return f"not found: {arguments['path']}", True
        os.remove(target)
        return f"deleted {arguments['path']}", False

    def _tool_check_import(self, target, arguments):
        return self._run(["-c", f"import {self.module}"])

    def _tool_run_scratch_tests(self, target, arguments):
        return self._run(["-m", "pytest", "-q", "-p", "no:cacheprovider",
                          "--noconftest", "scratch"])

    def _tool_finish(self, target, arguments):
        self.finished = True
        return "finished", False

    def _interpreter(self):
        if self._python is None:
            adapter = _load_python_adapter(self.repo_root)
            self._python = _get(adapter.provision(self.repo_root), "interpreter")
        return self._python

    def _prefix(self):
        done = subprocess.run(
            [self._interpreter(), "-I", "-c", "import sys; print(sys.prefix)"],
            capture_output=True, text=True)
        return os.path.realpath(done.stdout.strip())

    def _run(self, args):
        level = _isolation(self.allow_unisolated_exec)
        self.isolation = level
        if level == "none":
            return "no OS sandbox available: code is not run", True
        command = [self._interpreter()] + args
        repo = os.path.realpath(self.repo_root)
        if level == "sandbox-exec":
            command = [SANDBOX_EXEC, "-f", self.root + ".sb",
                       "-D", f"ROOT={self.root}", "-D", f"REPO={repo}",
                       "-D", f"PREFIX={self._prefix()}"] + command
        elif level == "bwrap":
            prefix = self._prefix()
            command = [shutil.which(BWRAP), "--ro-bind", "/", "/",
                       "--tmpfs", repo, "--ro-bind", prefix, prefix,
                       "--bind", self.root, self.root,
                       "--dev", "/dev", "--proc", "/proc",
                       "--unshare-net", "--die-with-parent",
                       "--chdir", self.root, "--"] + command
        tmp = os.path.join(self.root, "tmp")
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": tmp,
            "TMPDIR": tmp,
            "PYTHONPATH": os.path.join(self.root, "work"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        proc = subprocess.Popen(command, cwd=self.root, env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, preexec_fn=_limit_child,
                                start_new_session=True)
        try:
            output, _ = proc.communicate(timeout=_RUN_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            output, _ = proc.communicate()
            return "timeout\n" + output.decode("utf-8", "replace"), False
        return f"{proc.returncode}\n{output.decode('utf-8', 'replace')}", False


def _build_sandbox(root, sections):
    bundle_dir = os.path.join(root, "bundle")
    os.mkdir(bundle_dir)
    names = []
    for position, (title, text) in enumerate(sections, start=1):
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        name = f"bundle/{position:02d}-{slug}.md"
        path = os.path.join(root, name)
        Path(path).write_bytes(text.encode("utf-8"))
        os.chmod(path, 0o444)
        names.append(name)
    os.chmod(bundle_dir, 0o555)
    for directory in ("work", "scratch", "tmp"):
        os.mkdir(os.path.join(root, directory))
    return names


def _system_text(module, asset_paths):
    assets = ", ".join(f"work/{path}" for path in asset_paths) or "(none)"
    return (
        "You are generating one component's code inside a sandbox directory. "
        "Every path you pass to a tool is relative to the sandbox root, written with '/'.\n\n"
        "The sandbox holds exactly:\n"
        "- bundle/: the component's spec bundle, read-only, one Markdown file per section.\n"
        "- work/: your only output. When you finish it must hold "
        f"work/{module}.py or work/{module}/__init__.py, plus each asset file the "
        f"component declares ({assets}), and no other non-.py file.\n"
        "- scratch/: your own tests, run with pytest by run_scratch_tests. "
        "It is discarded when you finish.\n"
        "- tmp/: the HOME and TMPDIR of the code you run.\n\n"
        "You have no other access: no network, no repository, nothing outside this sandbox. "
        f"check_import runs `import {module}` with work/ on the path; "
        "run_scratch_tests runs pytest over scratch/.\n"
        "When you are done, call the tool finish."
    )


def _prompt_text(names):
    listing = "\n".join(f"- {name}" for name in names)
    return (
        "Read every file of your spec bundle, in this order, before writing anything:\n"
        f"{listing}\n\n"
        "Then write the component under work/, test it with your own tests under "
        "scratch/, revise until it is right, and call finish when done."
    )


def _candidate(root, module):
    work = os.path.join(root, "work")
    files = {}
    for dirpath, _subdirs, names in os.walk(work):
        for name in names:
            full = os.path.join(dirpath, name)
            if not stat.S_ISREG(os.lstat(full).st_mode):
                continue
            rel = os.path.relpath(full, work).replace(os.sep, "/")
            try:
                files[rel] = Path(full).read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                return None, {"category": "undecodable_file",
                              "message": f"work/{rel} is not valid UTF-8"}
    if f"{module}.py" not in files and f"{module}/__init__.py" not in files:
        return None, {"category": "missing_module",
                      "message": f"work/ holds neither {module}.py nor {module}/__init__.py"}
    return dict(sorted(files.items())), None


def _unfinished_error(outcome):
    stop = _get(outcome, "stop")
    if stop == "error":
        return _get(outcome, "model_call_error")
    category = "agent_budget_exhausted" if stop == "budget_exhausted" else "agent_unfinished"
    return {"category": category,
            "message": f"the tool loop stopped with {stop} before finish was called"}


def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,
                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,
                     wall_seconds=1800.0, claude_command="claude"):
    generator = _load_dependency(repo_root, "generator", "generator")
    component_id = bundle["component_id"]

    def result(**fields):
        return generator.GenerationResult(
            component_id=component_id,
            spec_bundle_hash=bundle["spec_bundle_hash"],
            model=model,
            prompt_version=AGENT_PROMPT_VERSION,
            cache_hit=False,
            retry_feedback=retry_feedback,
            mode="agentic",
            **fields,
        )

    reason = generator.check_write_allowed(bundle, repo_root)
    if reason is not None:
        return result(refused=reason, turns=0, tool_calls=0)
    category, messages = generator.check_asset_environment(component_id, repo_root)
    if category is not None:
        return result(model_call_error={"category": category, "message": "\n".join(messages)},
                      turns=0, tool_calls=0)

    sections = generator.render_prompt_sections(bundle, retry_feedback)
    slug = component_id.removeprefix("comp-")
    module = slug.replace("-", "_")
    root = os.path.realpath(tempfile.mkdtemp(prefix="hotdocs-agent-"))
    profile = root + ".sb"
    try:
        Path(profile).write_text(_PROFILE, encoding="utf-8")
        names = _build_sandbox(root, sections)
        system = _system_text(module, _declared_asset_paths(repo_root, slug))
        prompt = _prompt_text(names)
        tools = [{"name": name,
                  "description": description,
                  "input_schema": {"type": "object",
                                   "properties": {arg: {"type": "string"} for arg in args},
                                   "required": list(args)}}
                 for name, description, args in _TOOLS]
        loop = _load_dependency(repo_root, "llm-tool-endpoint", "llm_tool_endpoint")
        sandbox = _Sandbox(root, module, repo_root, allow_unisolated_exec)
        outcome = loop.run_tool_loop(
            system, prompt, model, tools, sandbox.execute,
            max_turns=max_turns, max_tool_calls=max_tool_calls,
            wall_seconds=wall_seconds, repo_root=repo_root,
            claude_command=claude_command)
        transcript = _get(outcome, "transcript")
        digest = hashlib.sha256(
            json.dumps(transcript, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        common = {
            "turns": _get(outcome, "turns"),
            "tool_calls": _get(outcome, "tool_calls"),
            "isolation": sandbox.isolation or _isolation(allow_unisolated_exec),
            "transcript_sha256": "sha256:" + digest,
        }
        if not sandbox.finished:
            return result(files={}, model_call_error=_unfinished_error(outcome), **common)
        files, error = _candidate(root, module)
        if error is not None:
            return result(files={}, model_call_error=error, **common)
        category, messages = generator.check_assets(component_id, files, repo_root=repo_root)
        if category is not None:
            return result(files={},
                          model_call_error={"category": category,
                                            "message": "\n".join(messages)},
                          **common)
        if bundle["hint_code"] is None:
            generator.write_files(component_id, files, repo_root=repo_root)
        return result(files=files, **common)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.chmod(os.path.join(root, "bundle"), 0o755)
        shutil.rmtree(root)
        Path(profile).unlink(missing_ok=True)
