# hotdocs-criterion: sha256:00cbbd065ff06681820d9286e524335ca4f4462a0c1fd9ac6dc33bb64a8c64d3
import provenance_checker

import hashlib
import json
from pathlib import Path

import pytest


COMP = "comp-foo"
H = "sha256:abc"
PK = "sha256:" + "a" * 64
PY_REASON = "python environment: requirements.lock does not pin pytest"
FAKE_REASON = "fake needs fakec >= 2"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def adapter_source(kind, log_path, conf_path, defaults, guidance):
    return (
        "import json\n"
        "import os\n"
        "\n"
        "KIND = " + repr(kind) + "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_CONF = " + repr(str(conf_path)) + "\n"
        "_DEFAULTS_JSON = " + repr(json.dumps(defaults)) + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr(guidance) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    with open(_LOG, 'a') as f:\n"
        "        f.write(" + repr(kind + "\n") + ")\n"
        "    result = json.loads(_DEFAULTS_JSON)\n"
        "    if os.path.exists(_CONF):\n"
        "        with open(_CONF) as f:\n"
        "            result.update(json.load(f))\n"
        "    return result\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {'names': []}\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        return None\n"
        "    return run\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )


ASSEMBLER_SRC = (
    "class SpecBundle:\n"
    "    def __init__(self, **kw):\n"
    "        self.__dict__.update(kw)\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return self.__dict__[key]\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return self.__dict__.get(key, default)\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root=None, mode='cold'):\n"
    "    return SpecBundle(\n"
    "        component_id=component_id,\n"
    "        spec_bundle_hash=" + repr(H) + ",\n"
    "        spec='',\n"
    "        interface='',\n"
    "        constraints='',\n"
    "        dependency_interfaces={},\n"
    "        dependency_context={},\n"
    "        dependency_usage={},\n"
    "        vars={},\n"
    "        glossary='',\n"
    "        hint_code=None,\n"
    "    )\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    raise RuntimeError('assemble_criterion must not be called')\n"
)

COMPILER_SRC = (
    "GATE_VERSION = " + repr("cc@1") + "\n"
    "\n"
    "\n"
    "def compile(component_id, repo_root, target='pytest', out_dir=None):\n"
    "    raise RuntimeError('compile must not be called')\n"
    "\n"
    "\n"
    "def compile_criterion(criterion, surface=None):\n"
    "    return {'status': 'error', 'message': 'line 1: not used'}\n"
)

TEST_AUTHOR_SRC = (
    "GATE_VERSION = " + repr("ta@1") + "\n"
    "\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    raise RuntimeError('author_test must not be called')\n"
)

VERIFIER_SRC = (
    "GATE_VERSION = " + repr("vo@1") + "\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    raise RuntimeError('verify must not be called')\n"
)

LICENSE_SRC = (
    "def gate_version(repo_root):\n"
    "    return " + repr("ls@1") + "\n"
    "\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    raise RuntimeError('license scan must not be called')\n"
)

SECRET_SRC = (
    "def gate_version(repo_root):\n"
    "    return " + repr("ss@1") + "\n"
    "\n"
    "\n"
    "def scan(repo_root):\n"
    "    raise RuntimeError('secret scan must not be called')\n"
    "\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    raise RuntimeError('secret scan_files must not be called')\n"
    "\n"
    "\n"
    "def propose(repo_root):\n"
    "    raise RuntimeError('propose must not be called')\n"
)

GENERATOR_SRC = (
    "GATE_VERSION = " + repr("gen@3") + "\n"
    "PROMPT_VERSION = " + repr("v11") + "\n"
)


def component_md(assets_line="assets: [fake:static/a.fake]", sealed=False):
    text = "---\n"
    text += "id: comp-foo\n"
    text += "title: Foo\n"
    text += "status: draft\n"
    text += "owners: [pipeline-team]\n"
    if sealed:
        text += "sealed: true\n"
        text += "source_path: legacy/foo/\n"
    if assets_line:
        text += assets_line + "\n"
    text += "---\n\n# Foo\n\nA fixture component.\n"
    return text


_MISSING = object()


class Env:
    def __init__(self, tmp_path):
        self.repo = tmp_path / "repo"
        self.side = tmp_path / "side"
        self.repo.mkdir()
        self.side.mkdir()
        self.py_log = self.side / "python.log"
        self.fake_log = self.side / "fake.log"
        self.py_conf = self.side / "python.json"
        self.fake_conf = self.side / "fake.json"

        self.py_adapter = self.repo / "gen" / "kind-python" / "kind_python.py"
        write(self.py_adapter, adapter_source(
            "python", self.py_log, self.py_conf,
            {"ok": True, "reason": "", "versions": {"python": "3.12.4", "packages": PK},
             "lockfile_sha256": None, "interpreter": "/fake/python"},
            {"generator": "", "test_author": ""},
        ))

        self.fake_adapter = self.repo / "gen" / "kind-fake" / "kind_fake.py"
        write(self.fake_adapter, adapter_source(
            "fake", self.fake_log, self.fake_conf,
            {"ok": True, "reason": "", "versions": {"fakec": "2.0.0"}, "lockfile_sha256": None},
            {"generator": "G.", "test_author": "T."},
        ))

        self.definition = self.repo / "specs" / "architecture" / "asset-kind-fake.md"
        write(self.definition, "# Asset kind fake\n\nA fixed fake definition.\n")

        self.component_md = self.repo / "specs" / "components" / "foo" / "component.md"
        write(self.component_md, component_md())

        write(self.repo / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SRC)
        write(self.repo / "pipeline" / "criterion-compiler" / "criterion_compiler.py", COMPILER_SRC)
        write(self.repo / "gen" / "test-author" / "test_author.py", TEST_AUTHOR_SRC)
        write(self.repo / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_SRC)
        write(self.repo / "gen" / "license-scanner" / "license_scanner.py", LICENSE_SRC)
        write(self.repo / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SRC)
        write(self.repo / "gen" / "generator" / "generator.py", GENERATOR_SRC)

    def P(self):
        return {"kind": "python", "path": ".", "definition_sha256": None,
                "adapter_sha256": sha(self.py_adapter),
                "versions": {"python": "3.12.4", "packages": PK},
                "lockfile_sha256": None}

    def fake_entry(self):
        return {"kind": "fake", "path": "static/a.fake",
                "definition_sha256": sha(self.definition),
                "adapter_sha256": sha(self.fake_adapter),
                "versions": {"fakec": "2.0.0"}, "lockfile_sha256": None}

    def E(self):
        return [self.P(), self.fake_entry()]

    def write_manifest(self, spec_hash=H, assets=_MISSING):
        manifest = {
            "spec_bundle_hash": spec_hash,
            "gate_versions": {},
            "verification_report": {"criteria": []},
            "license_scan": {},
            "secret_scan": {},
        }
        if assets is not _MISSING:
            manifest["assets"] = assets
        write(self.repo / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))

    def clear_logs(self):
        for p in (self.py_log, self.fake_log):
            if p.exists():
                p.unlink()

    def log_lines(self, path):
        if not path.exists():
            return []
        return [line for line in path.read_text().splitlines() if line.strip()]

    def check(self, spec_hash=H):
        return provenance_checker.check_provenance(COMP, spec_hash, {}, self.repo)

    def key(self):
        return provenance_checker.current_provenance_key(COMP, self.repo)


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def test_current_provenance_key_assets_is_E(env):
    key = env.key()
    assert field(key, "assets") == env.E()
    assert env.log_lines(env.py_log) == ["python"]
    assert env.log_lines(env.fake_log) == ["fake"]


def test_manifest_with_E_is_hit(env):
    env.write_manifest(assets=env.E())
    result = env.check()
    assert field(result, "hit") is True
    assert field(result, "reason") is None


def test_definition_changed_after_manifest_misses(env):
    env.write_manifest(assets=env.E())
    env.definition.write_text("# Asset kind fake\n\nA CHANGED fake definition.\n")
    result = env.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_adapter_comment_appended_after_manifest_misses(env):
    env.write_manifest(assets=env.E())
    with open(env.fake_adapter, "a") as f:
        f.write("# a comment appended after the manifest was written\n")
    result = env.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_fake_provision_not_ok_reason_verbatim(env):
    env.write_manifest(assets=env.E())
    env.fake_conf.write_text(json.dumps({"ok": False, "reason": FAKE_REASON,
                                         "versions": {}, "lockfile_sha256": None}))
    result = env.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == FAKE_REASON


def test_unknown_asset_kind(env):
    env.write_manifest(assets=env.E())
    env.component_md.write_text(component_md("assets: [nokind:static/b.x]"))
    result = env.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "unknown asset kind: nokind"


def test_python_provision_not_ok_stops_before_fake(env):
    env.write_manifest(assets=env.E())
    env.py_conf.write_text(json.dumps({"ok": False, "reason": PY_REASON,
                                       "versions": {}, "lockfile_sha256": None,
                                       "interpreter": None}))
    env.clear_logs()
    result = env.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == PY_REASON
    assert env.log_lines(env.fake_log) == []


def test_component_md_removed_assets_is_P_only(env):
    env.component_md.unlink()
    key = env.key()
    assert field(key, "assets") == [env.P()]
    env.write_manifest(assets=[env.P()])
    result = env.check()
    assert field(result, "hit") is True
    assert field(result, "reason") is None


def test_sealed_component_assets_empty_and_no_provision(env):
    env.component_md.write_text(component_md(sealed=True))
    env.clear_logs()
    key = env.key()
    assert field(key, "assets") == []
    assert env.log_lines(env.py_log) == []
    assert env.log_lines(env.fake_log) == []


@pytest.mark.parametrize("assets", [_MISSING, None], ids=["no-assets-field", "assets-null"])
@pytest.mark.parametrize("remove_component", [False, True], ids=["declared", "component-md-removed"])
def test_manifest_without_assets_misses(env, assets, remove_component):
    if remove_component:
        env.component_md.unlink()
    env.write_manifest(assets=assets)
    result = env.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_spec_bundle_hash_differs_calls_no_provision(env):
    env.write_manifest(spec_hash="OTHER", assets=env.E())
    env.clear_logs()
    result = env.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"
    assert env.log_lines(env.py_log) == []
    assert env.log_lines(env.fake_log) == []