# hotdocs-criterion: sha256:d2840510ef738d207e51477e15de876851364fa5b863972bdd945d69212cbf91
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


H = "sha256:" + "c" * 64
PK = "sha256:" + "a" * 64
FAKE_REASON = "fake needs fakec >= 2"
PYTHON_REASON = "python environment: requirements.lock does not pin pytest"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def adapter_source(kind, guidance, versions, cfg_path, log_path, python):
    ok_result = (
        "{'ok': True, 'reason': '', 'versions': "
        + repr(versions)
        + ", 'lockfile_sha256': None"
    )
    fail_result = "{'ok': False, 'reason': cfg['reason'], 'versions': {}, 'lockfile_sha256': None"
    if python:
        ok_result += ", 'interpreter': '/fake/python'"
        fail_result += ", 'interpreter': None"
    ok_result += "}"
    fail_result += "}"
    return (
        "import json\n"
        "import os\n"
        "\n"
        "KIND = " + repr(kind) + "\n"
        "_CFG = " + repr(str(cfg_path)) + "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr(guidance) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('provision\\n')\n"
        "    cfg = {}\n"
        "    if os.path.exists(_CFG):\n"
        "        with open(_CFG, encoding='utf-8') as fh:\n"
        "            cfg = json.load(fh)\n"
        "    if cfg.get('ok', True) is False:\n"
        "        return " + fail_result + "\n"
        "    return " + ok_result + "\n"
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


def log_prelude(log_path):
    return (
        "_CALLS = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _record(name):\n"
        "    with open(_CALLS, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
        "\n"
    )


def stub(name):
    return (
        "def " + name + "(*args, **kwargs):\n"
        "    _record(" + repr(name) + ")\n"
        "    raise RuntimeError(" + repr(name + " stand-in must not be called") + ")\n"
        "\n"
        "\n"
    )


def assembler_source(log_path):
    return (
        log_prelude(log_path)
        + "class SpecBundle:\n"
        "    _FIELDS = ('component_id', 'spec_bundle_hash', 'spec', 'interface', 'constraints',\n"
        "               'dependency_interfaces', 'dependency_context', 'dependency_usage',\n"
        "               'vars', 'glossary', 'hint_code', 'spec_bundle_parts')\n"
        "\n"
        "    def __init__(self, component_id, spec_bundle_hash, spec='', interface='',\n"
        "                 constraints='', dependency_interfaces=None, dependency_context=None,\n"
        "                 dependency_usage=None, vars=None, glossary='', hint_code=None,\n"
        "                 spec_bundle_parts=None):\n"
        "        self.component_id = component_id\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.spec = spec\n"
        "        self.interface = interface\n"
        "        self.constraints = constraints\n"
        "        self.dependency_interfaces = dependency_interfaces or {}\n"
        "        self.dependency_context = dependency_context or {}\n"
        "        self.dependency_usage = dependency_usage or {}\n"
        "        self.vars = vars or {}\n"
        "        self.glossary = glossary\n"
        "        self.hint_code = hint_code\n"
        "        self.spec_bundle_parts = spec_bundle_parts or {}\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        if key not in self._FIELDS:\n"
        "            raise KeyError(key)\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key) if key in self._FIELDS else default\n"
        "\n"
        "    def keys(self):\n"
        "        return list(self._FIELDS)\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _record('assemble')\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:abc',\n"
        "        spec_bundle_parts={'spec': 'sha256:s', 'dependency_code': 'sha256:d'},\n"
        "    )\n"
        "\n"
        "\n"
        + stub("assemble_criterion")
    )


def plant_standins(root, log_path):
    write(root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
          assembler_source(log_path))
    write(root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
          log_prelude(log_path)
          + "GATE_VERSION = 'cc@1'\n\n\n"
          + stub("compile") + stub("compile_criterion"))
    write(root / "gen" / "test-author" / "test_author.py",
          log_prelude(log_path)
          + "GATE_VERSION = 'ta@1'\n\n\n"
          + stub("author_test"))
    write(root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
          log_prelude(log_path)
          + "GATE_VERSION = 'vo@1'\nDEFAULT_TEST_TIMEOUT = 300.0\n\n\n"
          + stub("verify"))
    write(root / "gen" / "license-scanner" / "license_scanner.py",
          log_prelude(log_path)
          + "def gate_version(repo_root):\n    return 'ls@1'\n\n\n"
          + stub("scan"))
    write(root / "gen" / "secret-scanner" / "secret_scanner.py",
          log_prelude(log_path)
          + "def gate_version(repo_root):\n    return 'ss@1'\n\n\n"
          + stub("scan") + stub("scan_files") + stub("propose"))
    write(root / "gen" / "generator" / "generator.py",
          log_prelude(log_path)
          + "GATE_VERSION = 'gen@3'\nPROMPT_VERSION = 'v11'\n\n\n"
          + stub("generate") + stub("commit_cache") + stub("check_write_allowed")
          + stub("render_prompt_sections") + stub("write_files") + stub("check_assets")
          + stub("check_asset_environment"))


class Repo:
    def __init__(self, tmp_path, assets_line="assets: [fake:static/a.fake]", extra_lines=()):
        self.root = tmp_path / "repo"
        self.side = tmp_path / "side"
        self.root.mkdir(parents=True)
        self.side.mkdir(parents=True)
        self.python_log = self.side / "python_provision.log"
        self.fake_log = self.side / "fake_provision.log"
        self.python_cfg = self.side / "python_cfg.json"
        self.fake_cfg = self.side / "fake_cfg.json"
        self.calls_log = self.side / "standin_calls.log"

        self.python_adapter = self.root / "gen" / "kind-python" / "kind_python.py"
        write(self.python_adapter, adapter_source(
            "python", {"generator": "", "test_author": ""},
            {"python": "3.12.4", "packages": PK},
            self.python_cfg, self.python_log, True))

        self.fake_definition = self.root / "specs" / "architecture" / "asset-kind-fake.md"
        write(self.fake_definition, "# Fake asset kind\n\nA fixed fake definition.\n")
        self.fake_adapter = self.root / "gen" / "kind-fake" / "kind_fake.py"
        write(self.fake_adapter, adapter_source(
            "fake", {"generator": "G.", "test_author": "T."},
            {"fakec": "2.0.0"},
            self.fake_cfg, self.fake_log, False))

        self.component_md = self.root / "specs" / "components" / "foo" / "component.md"
        lines = ["---", "id: comp-foo", "title: Foo", "status: draft",
                 "owners: [pipeline-team]", "depends_on: []"]
        if assets_line:
            lines.append(assets_line)
        lines.extend(extra_lines)
        lines.extend(["---", "", "# Foo", "", "## Purpose", "", "A fixture component.", ""])
        write(self.component_md, "\n".join(lines))

        plant_standins(self.root, self.calls_log)

    def P(self):
        return {"kind": "python", "path": ".", "definition_sha256": None,
                "adapter_sha256": sha(self.python_adapter),
                "versions": {"python": "3.12.4", "packages": PK},
                "lockfile_sha256": None}

    def E(self):
        return [self.P(), {"kind": "fake", "path": "static/a.fake",
                           "definition_sha256": sha(self.fake_definition),
                           "adapter_sha256": sha(self.fake_adapter),
                           "versions": {"fakec": "2.0.0"},
                           "lockfile_sha256": None}]

    def write_manifest(self, assets, spec_bundle_hash=H, omit_assets=False):
        manifest = {
            "spec_bundle_hash": spec_bundle_hash,
            "gate_versions": {},
            "verification_report": {"criteria": []},
            "license_scan": {},
            "secret_scan": {},
        }
        if not omit_assets:
            manifest["assets"] = assets
        write(self.root / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))

    def reset_logs(self):
        for p in (self.python_log, self.fake_log):
            if p.exists():
                p.unlink()

    def calls(self, log):
        if not log.exists():
            return 0
        return len([l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()])

    def check(self):
        return provenance_checker.check_provenance("comp-foo", H, {}, self.root)

    def key(self):
        return provenance_checker.current_provenance_key("comp-foo", self.root)


def test_current_provenance_key_assets_is_exactly_E(tmp_path):
    repo = Repo(tmp_path)
    key = repo.key()
    assert field(key, "assets") == repo.E()


def test_manifest_with_E_is_a_hit(tmp_path):
    repo = Repo(tmp_path)
    repo.write_manifest(repo.E())
    result = repo.check()
    assert field(result, "hit") is True
    assert field(result, "reason") is None


def test_definition_changed_after_manifest_misses_with_assets_differ(tmp_path):
    repo = Repo(tmp_path)
    repo.write_manifest(repo.E())
    with open(repo.fake_definition, "a", encoding="utf-8") as fh:
        fh.write("A change made after the manifest was written.\n")
    result = repo.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_adapter_comment_appended_after_manifest_misses_with_assets_differ(tmp_path):
    repo = Repo(tmp_path)
    repo.write_manifest(repo.E())
    with open(repo.fake_adapter, "a", encoding="utf-8") as fh:
        fh.write("# a comment appended after the manifest was written\n")
    result = repo.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_fake_provision_not_ok_misses_with_its_reason(tmp_path):
    repo = Repo(tmp_path)
    repo.write_manifest(repo.E())
    write(repo.fake_cfg, json.dumps({"ok": False, "reason": FAKE_REASON}))
    result = repo.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == FAKE_REASON


def test_unknown_asset_kind_misses(tmp_path):
    repo = Repo(tmp_path, assets_line="assets: [nokind:static/b.x]")
    repo.write_manifest(repo.E())
    result = repo.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "unknown asset kind: nokind"


def test_python_provision_not_ok_misses_and_fake_not_provisioned(tmp_path):
    repo = Repo(tmp_path)
    repo.write_manifest(repo.E())
    write(repo.python_cfg, json.dumps({"ok": False, "reason": PYTHON_REASON}))
    repo.reset_logs()
    result = repo.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == PYTHON_REASON
    assert repo.calls(repo.fake_log) == 0


def test_component_md_removed_assets_is_only_python(tmp_path):
    repo = Repo(tmp_path)
    repo.component_md.unlink()
    key = repo.key()
    assert field(key, "assets") == [repo.P()]
    repo.write_manifest([repo.P()])
    result = repo.check()
    assert field(result, "hit") is True
    assert field(result, "reason") is None


def test_sealed_component_assets_empty_and_no_provision(tmp_path):
    repo = Repo(tmp_path, extra_lines=("sealed: true", "source_path: legacy/foo/"))
    write(repo.root / "legacy" / "foo" / "foo.py", "X = 1\n")
    repo.reset_logs()
    key = repo.key()
    assert field(key, "assets") == []
    assert repo.calls(repo.python_log) == 0
    assert repo.calls(repo.fake_log) == 0


@pytest.mark.parametrize("remove_component_md", [False, True])
@pytest.mark.parametrize("shape", ["absent", "null"])
def test_manifest_without_assets_misses_with_assets_differ(tmp_path, shape, remove_component_md):
    repo = Repo(tmp_path)
    if remove_component_md:
        repo.component_md.unlink()
    repo.write_manifest(None, omit_assets=(shape == "absent"))
    result = repo.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_spec_bundle_hash_differs_and_no_provision(tmp_path):
    repo = Repo(tmp_path)
    repo.write_manifest(repo.E(), spec_bundle_hash="OTHER")
    repo.reset_logs()
    result = repo.check()
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"
    assert repo.calls(repo.python_log) == 0
    assert repo.calls(repo.fake_log) == 0