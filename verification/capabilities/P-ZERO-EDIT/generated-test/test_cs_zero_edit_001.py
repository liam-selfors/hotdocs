# hotdocs-criterion: sha256:b746c794ed30b9be8b3a42099c7787c522aca73001639020f1fbc90bf9c5aa49
"""CS-ZERO-EDIT-001 (covers P-ZERO-EDIT).

Given a ratified, non-sealed component spec bundle with complete,
agent-checkable acceptance criteria, when a spec change is merged and the
pipeline then runs (generation -> verification -> gates -> merge), the
resulting gen/<component>/ passes every gate with zero commits to
gen/<component>/ authored by a human between the spec merge commit and the
pipeline's own merge commit.

The pipeline is driven through `component_gate_runner.run_component_gates`.
The model is a mock `llm_backend`. Dependencies whose own behaviour is not
what this capability is about, or whose internals this bundle does not fully
describe, are replaced by flat-module fakes written under the temporary
`repo_root`: the two scanners, the run environment, the `python` asset
adapter and the verifier. The fake verifier really runs the criterion's
test against the generated code, so its verdict reflects the code itself.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import component_gate_runner


SLUG = "shout"
COMPONENT_ID = "comp-shout"
CAPABILITY_ID = "P-SHOUT"
MODEL = "claude-sonnet-5"

HUMAN_NAME = "Spec Author"
HUMAN_EMAIL = "spec-author@example.invalid"
PIPELINE_NAME = "hotdocs-pipeline"
PIPELINE_EMAIL = "pipeline@hotdocs.invalid"

GENERATED_CODE = 'def shout(text):\n    return text.upper() + "!"\n'

CRITERION_TEST_SOURCE = (
    "import shout\n"
    "\n"
    "\n"
    "def test_ac_shout_001():\n"
    "    assert shout.shout(" + repr("hi") + ") == " + repr("HI!") + "\n"
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def opt_field(value, name):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git_env(name, email):
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = name
    env["GIT_AUTHOR_EMAIL"] = email
    env["GIT_COMMITTER_NAME"] = name
    env["GIT_COMMITTER_EMAIL"] = email
    return env


def git(repo, *args, name=HUMAN_NAME, email=HUMAN_EMAIL):
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + os.devnull, *args],
        cwd=str(repo),
        env=git_env(name, email),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, "git " + " ".join(args) + " failed:\n" + proc.stdout + proc.stderr
    return proc.stdout


# --------------------------------------------------------------------------
# fixture corpus
# --------------------------------------------------------------------------

def build_corpus(repo):
    write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Shout** — a piece of text upper-cased and followed by one `!`.\n",
    )
    write(
        repo / "specs" / "components" / SLUG / "component.md",
        "---\n"
        "id: comp-shout\n"
        "title: Shout\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [demo-team]\n"
        "depends_on: []\n"
        "realizes: [P-SHOUT]\n"
        "---\n"
        "\n"
        "# Shout\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Turns a piece of text into a shout.\n",
    )
    write(
        repo / "specs" / "components" / SLUG / "requirements" / "R-SHOUT-001.md",
        "# R-SHOUT-001\n\n`shout(text)` MUST return `text` upper-cased, followed by `!`.\n",
    )
    write(
        repo / "specs" / "components" / SLUG / "acceptance" / "AC-SHOUT-001.md",
        "# AC-SHOUT-001\n"
        "\n"
        "Covers: R-SHOUT-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the text \"hi\"\n"
        "When shout is called with it\n"
        "Then the result is \"HI!\"\n"
        "```\n",
    )
    write(
        repo / "specs" / "components" / SLUG / "interface" / "library.md",
        "# Library\n\nOne module file, `shout.py`.\n\n```\nshout(text: str) -> str\n```\n",
    )
    write(
        repo / "specs" / "components" / SLUG / "constraints.md",
        "# Constraints\n\nStandard library only.\n",
    )
    write(
        repo / "specs" / "product" / "P-SHOUT.md",
        "---\n"
        "id: P-SHOUT\n"
        "title: Shouting\n"
        "status: ratified\n"
        "last_ratified_commit: 0000000\n"
        "owners: [demo-team]\n"
        "---\n"
        "\n"
        "# Shouting\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Text can be turned into a shout.\n"
        "\n"
        "## Scope\n"
        "\n"
        "In scope: shouting a single string.\n"
        "\n"
        "## Capability scenario\n"
        "\n"
        "### CS-SHOUT-001\n"
        "Covers: P-SHOUT\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a piece of text\n"
        "When it is shouted\n"
        "Then the result reads as a shout\n"
        "```\n",
    )
    write(repo / ".gitignore", ".hotdocs/\n__pycache__/\n*.pyc\n.pytest_cache/\n")


# --------------------------------------------------------------------------
# fakes, written as flat modules under <repo_root>/gen/<slug>/
# --------------------------------------------------------------------------

def write_fakes(repo, log_path):
    log = repr(str(log_path))

    write(
        repo / "gen" / "license-scanner" / "license_scanner.py",
        "LOG = " + log + "\n"
        "GATE = 'license_scanner@0.0.0+fixture'\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return GATE\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('license_scan ' + component_id + '\\n')\n"
        "    return {'component_id': component_id, 'gate_version': GATE,\n"
        "            'similarity_score': 0.0, 'blocked': False, 'matches': []}\n",
    )

    write(
        repo / "gen" / "secret-scanner" / "secret_scanner.py",
        "LOG = " + log + "\n"
        "GATE = 'secret_scanner@0.0.0+fixture'\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return GATE\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('secret_scan\\n')\n"
        "    return {'scope': 'repo', 'gate_version': GATE, 'flagged': False, 'matches': []}\n",
    )

    write(
        repo / "gen" / "kind-python" / "kind_python.py",
        "import hashlib\n"
        "import platform\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "KIND = 'python'\n"
        "GATE_VERSION = 'kind-python@1.0.0'\n"
        "\n"
        "class AssetError(Exception):\n"
        "    pass\n"
        "\n"
        "def _module_present(asset_file):\n"
        "    d = Path(asset_file)\n"
        "    module = d.name.replace('-', '_')\n"
        "    return (d / (module + '.py')).is_file() or (d / module / '__init__.py').is_file()\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    d = Path(asset_file)\n"
        "    if not d.is_dir():\n"
        "        return ['not a directory']\n"
        "    py = [p for p in d.rglob('*.py') if '__pycache__' not in p.parts]\n"
        "    if not py:\n"
        "        return ['no python files']\n"
        "    return []\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {'names': []}\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': '',\n"
        "            'versions': {'python': platform.python_version(),\n"
        "                         'packages': 'sha256:' + hashlib.sha256(b'fixture').hexdigest()},\n"
        "            'lockfile_sha256': None, 'interpreter': sys.executable}\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(name, args):\n"
        "        raise AssetError('not supported by fixture')\n"
        "    return run\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n",
    )

    write(
        repo / "gen" / "run-environment" / "run_environment.py",
        "import hashlib\n"
        "import json\n"
        "import platform\n"
        "import sys\n"
        "\n"
        "LOG = " + log + "\n"
        "\n"
        "def _assets():\n"
        "    return [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "             'adapter_sha256': 'sha256:' + hashlib.sha256(b'kind-python-fixture').hexdigest(),\n"
        "             'versions': {'python': platform.python_version()},\n"
        "             'lockfile_sha256': None}]\n"
        "\n"
        "class RunEnvironment:\n"
        "    def __init__(self, assets):\n"
        "        self.ok = True\n"
        "        self.failure_message = None\n"
        "        self.interpreter = sys.executable\n"
        "        self.assets = assets\n"
        "        self.drivers = []\n"
        "        self.plugin_dir = None\n"
        "    def __getitem__(self, name):\n"
        "        return getattr(self, name)\n"
        "    def get(self, name, default=None):\n"
        "        return getattr(self, name, default)\n"
        "    def pytest_args(self):\n"
        "        return []\n"
        "    def driver_fixtures(self):\n"
        "        return []\n"
        "    def env_for(self, code_dir):\n"
        "        assets = [dict(a, file=str(code_dir) + '/' + a['path']) for a in self.assets]\n"
        "        return {'HOTDOCS_ASSETS': json.dumps(assets), 'HOTDOCS_DRIVERS': json.dumps([])}\n"
        "    def close(self):\n"
        "        self.plugin_dir = None\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'failure_message': self.failure_message,\n"
        "                'interpreter': self.interpreter, 'assets': self.assets,\n"
        "                'drivers': self.drivers, 'plugin_dir': self.plugin_dir}\n"
        "\n"
        "def prepare(component_id, repo_root):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('prepare ' + component_id + '\\n')\n"
        "    return RunEnvironment(_assets())\n"
        "\n"
        "def prepare_capability(capability_id, repo_root):\n"
        "    return RunEnvironment([])\n",
    )

    write(
        repo / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "import hashlib\n"
        "import os\n"
        "import platform\n"
        "import shutil\n"
        "import subprocess\n"
        "import sys\n"
        "import tempfile\n"
        "from pathlib import Path\n"
        "\n"
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "LOG = " + log + "\n"
        "TEST_SOURCE = " + repr(CRITERION_TEST_SOURCE) + "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('verify ' + component_id + '\\n')\n"
        "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
        "    code_dir = Path(repo_root) / 'gen' / slug\n"
        "    tmp = tempfile.mkdtemp()\n"
        "    try:\n"
        "        test_file = Path(tmp) / 'test_ac_shout_001.py'\n"
        "        test_file.write_text(TEST_SOURCE, encoding='utf-8')\n"
        "        env = dict(os.environ)\n"
        "        env['PYTHONPATH'] = str(code_dir)\n"
        "        env['PYTHONDONTWRITEBYTECODE'] = '1'\n"
        "        proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',\n"
        "                               str(test_file)], cwd=tmp, env=env, capture_output=True,\n"
        "                              text=True, timeout=DEFAULT_TEST_TIMEOUT)\n"
        "        passed = proc.returncode == 0\n"
        "        output = proc.stdout + proc.stderr\n"
        "    finally:\n"
        "        shutil.rmtree(tmp, ignore_errors=True)\n"
        "    entry = {'id': 'AC-SHOUT-001', 'covers': 'R-SHOUT-001', 'kind': 'generated-test',\n"
        "             'result': 'pass' if passed else 'fail'}\n"
        "    if not passed:\n"
        "        entry['failure_detail'] = {'message': output[-2000:], 'expected': None, 'actual': None}\n"
        "        entry['failure_origin'] = 'implementation'\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('verify_result ' + entry['result'] + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [entry],\n"
        "        'requirement_results': {'R-SHOUT-001': entry['result']},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 1.0,\n"
        "        'mutation_error': None,\n"
        "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                    'adapter_sha256': 'sha256:' + hashlib.sha256(b'kind-python-fixture').hexdigest(),\n"
        "                    'versions': {'python': platform.python_version()},\n"
        "                    'lockfile_sha256': None}],\n"
        "        'drivers': [],\n"
        "        'overall': 'pass' if passed else 'fail',\n"
        "    }\n",
    )


def make_backend(log_path):
    """Mock model: answers a generator prompt with the shout module."""

    def backend(prompt, model, **params):
        match = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("model_call " + ("generator" if match else "other") + "\n")
        if not match:
            return {
                "text": None,
                "model": model,
                "backend": "mock",
                "model_call_error": {"category": "network", "message": "unexpected prompt"},
            }
        nonce = match.group(1)
        reply = (
            "-----BEGIN FILE " + nonce + ": shout.py-----\n"
            + GENERATED_CODE
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": reply, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def assert_gates_pass(result):
    assert field(result, "blocked") is False, "pipeline blocked: " + repr(result)
    assert field(result, "block_reason") is None
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass", repr(verification)
    for criterion in field(verification, "criteria"):
        assert field(criterion, "result") == "pass", repr(criterion)
    license_scan = field(result, "license_scan")
    assert opt_field(license_scan, "blocked") is not True, repr(license_scan)
    secret_scan = field(result, "secret_scan")
    assert opt_field(secret_scan, "flagged") is not True, repr(secret_scan)


# --------------------------------------------------------------------------
# the test
# --------------------------------------------------------------------------

def test_cs_zero_edit_001_pipeline_merge_has_no_human_commits_to_gen(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git is required to observe commit authorship")

    repo = tmp_path / "repo"
    repo.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.chdir(repo)

    # --- Given: a ratified, non-sealed, lint-clean component spec bundle ---
    build_corpus(repo)
    write_fakes(repo, log_path)

    gen_dir = next(
        p for p in Path(component_gate_runner.__file__).resolve().parents if p.name == "gen"
    )
    base = gen_dir / "spec-linter"
    linter_path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec_linter = load_module(linter_path, "spec_linter")
    lint_result = spec_linter.lint(None, repo)
    assert lint_result.hard_failures == 0, repr(lint_result)

    component_md = (repo / "specs" / "components" / SLUG / "component.md").read_text()
    assert "sealed: true" not in component_md
    assert "status: ratified" in component_md

    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial corpus")

    # --- a spec change, merged by a human ---
    git(repo, "checkout", "-q", "-b", "spec-change")
    write(
        repo / "specs" / "components" / SLUG / "requirements" / "R-SHOUT-001.md",
        "# R-SHOUT-001\n\n`shout(text)` MUST return `text` upper-cased, followed by exactly one `!`.\n",
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "spec: tighten R-SHOUT-001")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", "Merge spec change", "spec-change")
    spec_merge = git(repo, "rev-parse", "HEAD").strip()

    lint_after = spec_linter.lint(None, repo)
    assert lint_after.hard_failures == 0, repr(lint_after)

    # --- When: the pipeline generates, verifies, gates and merges ---
    git(repo, "checkout", "-q", "-b", "pipeline/" + SLUG, name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    backend = make_backend(log_path)
    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo, MODEL, seed=0, llm_backend=backend
    )

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert "model_call generator" in calls, calls
    assert "verify " + COMPONENT_ID in calls, calls
    assert "license_scan " + COMPONENT_ID in calls, calls
    assert "secret_scan" in calls, calls

    assert field(result, "provenance_hit") is False
    assert_gates_pass(result)

    generated = repo / "gen" / SLUG / "shout.py"
    assert generated.is_file(), "pipeline wrote no gen/" + SLUG + "/shout.py"
    assert generated.read_text(encoding="utf-8") == GENERATED_CODE

    git(repo, "add", "-A", name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    git(repo, "commit", "-q", "-m", "pipeline: regenerate " + COMPONENT_ID,
        name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    git(repo, "checkout", "-q", "main", name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    git(repo, "merge", "-q", "--no-ff", "-m", "pipeline merge " + COMPONENT_ID,
        "pipeline/" + SLUG, name=PIPELINE_NAME, email=PIPELINE_EMAIL)
    pipeline_merge = git(repo, "rev-parse", "HEAD").strip()

    merge_author = git(repo, "log", "-1", "--format=%ae", pipeline_merge).strip()
    assert merge_author == PIPELINE_EMAIL

    # --- Then: zero human-authored commits to gen/<component>/ ---
    log_lines = [
        line
        for line in git(
            repo, "log", "--full-history", "--format=%H%x09%an%x09%ae",
            spec_merge + ".." + pipeline_merge, "--", "gen/" + SLUG + "/",
        ).splitlines()
        if line.strip()
    ]
    assert log_lines, "no commit touched gen/" + SLUG + "/ between the two merges"
    human = [line for line in log_lines if line.split("\t")[2] != PIPELINE_EMAIL]
    assert human == [], "human-authored commits to gen/" + SLUG + "/: " + repr(human)

    # gen/<component>/ at the pipeline merge is exactly what the pipeline wrote.
    status = git(repo, "status", "--porcelain", "--", "gen/" + SLUG + "/")
    assert status.strip() == "", status
    committed = git(repo, "show", pipeline_merge + ":gen/" + SLUG + "/shout.py")
    assert committed == GENERATED_CODE

    # --- and the merged gen/<component>/ still passes every gate ---
    rerun = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo, MODEL, seed=0, llm_backend=backend
    )
    assert_gates_pass(rerun)
    diff = subprocess.run(
        ["git", "diff", "--quiet", pipeline_merge, "--", "gen/" + SLUG + "/shout.py"],
        cwd=str(repo), env=git_env(PIPELINE_NAME, PIPELINE_EMAIL),
    )
    assert diff.returncode == 0, "re-running the gates changed the merged code"