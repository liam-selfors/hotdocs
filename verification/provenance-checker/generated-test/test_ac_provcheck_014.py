# hotdocs-criterion: sha256:1cab5a03167dc0dd76694641fcf877ad4b817c7af73c9cb0060058315e1fd85d
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
MISSING = object()


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def log_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line.strip()]


ADAPTER_STUBS = (
    "\n"
    "def layout_errors(asset_file):\n"
    "    return []\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {'names': []}\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    def run(entry_point, args):\n"
    "        return None\n"
    "    return run\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return []\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    return None\n"
)


def python_adapter_source(log, ok=True, reason=""):
    return (
        "KIND = 'python'\n"
        "LOG = " + repr(str(log)) + "\n"
        "OK = " + repr(ok) + "\n"
        "REASON = " + repr(reason) + "\n"
        "PK = " + repr(PK) + "\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "\n"
        "def provision(repo_root):\n"
        "    with open(LOG, 'a') as handle:\n"
        "        handle.write('provision\\n')\n"
        "    return {'ok': OK, 'reason': REASON,\n"
        "            'versions': {'python': '3.12.4', 'packages': PK},\n"
        "            'lockfile_sha256': None,\n"
        "            'interpreter': '/fake/python' if OK else None}\n"
        + ADAPTER_STUBS
    )


def fake_adapter_source(log, ok=True, reason=""):
    return (
        "KIND = 'fake'\n"
        "LOG = " + repr(str(log)) + "\n"
        "OK = " + repr(ok) + "\n"
        "REASON = " + repr(reason) + "\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': 'G.', 'test_author': 'T.'}\n"
        "\n"
        "def provision(repo_root):\n"
        "    with open(LOG, 'a') as handle:\n"
        "        handle.write('provision\\n')\n"
        "    return {'ok': OK, 'reason': REASON,\n"
        "            'versions': {'fakec': '2.0.0'},\n"
        "            'lockfile_sha256': None}\n"
        + ADAPTER_STUBS
    )


def assembler_source(log):
    return (
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "class SpecBundle:\n"
        "    def __init__(self, component_id):\n"
        "        self.component_id = component_id\n"
        "        self.spec_bundle_hash = 'sha256:abc'\n"
        "        self.spec = ''\n"
        "        self.interface = ''\n"
        "        self.constraints = ''\n"
        "        self.dependency_interfaces = {}\n"
        "        self.dependency_context = {}\n"
        "        self.dependency_usage = {}\n"
        "        self.vars = {}\n"
        "        self.glossary = ''\n"
        "        self.hint_code = None\n"
        "        self.spec_bundle_parts = {'spec': 'sha256:" + "1" * 64 + "',\n"
        "                                  'dependency_code': 'sha256:" + "2" * 64 + "'}\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key, default)\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    with open(LOG, 'a') as handle:\n"
        "        handle.write('assemble ' + str(component_id) + ' ' + str(mode) + '\\n')\n"
        "    return SpecBundle(component_id)\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    raise RuntimeError('not used')\n"
    )


def license_source(log):
    return (
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ls@1'\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    with open(LOG, 'a') as handle:\n"
        "        handle.write('license scan\\n')\n"
        "    return {'component_id': component_id, 'gate_version': 'ls@1',\n"
        "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
        "            'similarity_score': None, 'block_threshold': None,\n"
        "            'blocked': False, 'matches': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n"
    )


def secret_source(log):
    return (
        "LOG = " + repr(str(log)) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ss@1'\n"
        "\n"
        "def _result(scope):\n"
        "    return {'scope': scope, 'gate_version': 'ss@1', 'flagged': False,\n"
        "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
        "            'notified': False, 'notification_delivery_error': None,\n"
        "            'cache_hit': False}\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(LOG, 'a') as handle:\n"
        "        handle.write('secret scan\\n')\n"
        "    return _result('full')\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    with open(LOG, 'a') as handle:\n"
        "        handle.write('secret scan_files\\n')\n"
        "    return _result('precommit')\n"
    )


def component_md(assets_line, extra_lines=()):
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
    ]
    if assets_line is not None:
        lines.append(assets_line)
    lines.extend(extra_lines)
    lines.append("---")
    lines.append("")
    lines.append("# Foo")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("Foo does foo things.")
    lines.append("")
    return "\n".join(lines)


def build(tmp_path, assets_line="assets: [fake:static/a.fake]", extra_lines=(),
          python_ok=True, python_reason="", fake_ok=True, fake_reason=""):
    repo = tmp_path / "repo"
    logs = tmp_path / "logs"
    repo.mkdir()
    logs.mkdir()
    ctx = {
        "repo": repo,
        "python_log": logs / "python.log",
        "fake_log": logs / "fake.log",
        "deps_log": logs / "deps.log",
    }
    ctx["python_adapter"] = repo / "gen" / "kind-python" / "kind_python.py"
    ctx["fake_adapter"] = repo / "gen" / "kind-fake" / "kind_fake.py"
    ctx["definition"] = repo / "specs" / "architecture" / "asset-kind-fake.md"
    ctx["component_md"] = repo / "specs" / "components" / "foo" / "component.md"
    ctx["manifest"] = repo / "gen" / "foo" / ".provenance.json"

    write(ctx["python_adapter"], python_adapter_source(ctx["python_log"], python_ok, python_reason))
    write(ctx["fake_adapter"], fake_adapter_source(ctx["fake_log"], fake_ok, fake_reason))
    write(ctx["definition"], "# Asset kind fake\n\nA fixed definition text.\n")
    write(ctx["component_md"], component_md(assets_line, extra_lines))

    write(repo / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
          assembler_source(ctx["deps_log"]))
    write(repo / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
          "GATE_VERSION = " + repr("cc@1") + "\n")
    write(repo / "gen" / "test-author" / "test_author.py",
          "GATE_VERSION = " + repr("ta@1") + "\n")
    write(repo / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
          "GATE_VERSION = " + repr("vo@1") + "\n")
    write(repo / "gen" / "license-scanner" / "license_scanner.py",
          license_source(ctx["deps_log"]))
    write(repo / "gen" / "secret-scanner" / "secret_scanner.py",
          secret_source(ctx["deps_log"]))
    write(repo / "gen" / "generator" / "generator.py",
          "GATE_VERSION = " + repr("gen@3") + "\n" + "PROMPT_VERSION = " + repr("v11") + "\n")
    return ctx


def expected_p(ctx):
    return {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha(ctx["python_adapter"]),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }


def expected_e(ctx):
    return [
        expected_p(ctx),
        {
            "kind": "fake",
            "path": "static/a.fake",
            "definition_sha256": sha(ctx["definition"]),
            "adapter_sha256": sha(ctx["fake_adapter"]),
            "versions": {"fakec": "2.0.0"},
            "lockfile_sha256": None,
        },
    ]


def write_manifest(ctx, assets=MISSING, spec_bundle_hash="H"):
    manifest = {
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "drivers": [],
    }
    if assets is not MISSING:
        manifest["assets"] = assets
    write(ctx["manifest"], json.dumps(manifest))


def check(ctx):
    return provenance_checker.check_provenance("comp-foo", "H", {}, ctx["repo"])


def test_current_key_assets_is_e(tmp_path):
    ctx = build(tmp_path)
    key = provenance_checker.current_provenance_key("comp-foo", ctx["repo"])
    assert field(key, "assets") == expected_e(ctx)


def test_manifest_with_e_is_hit(tmp_path):
    ctx = build(tmp_path)
    write_manifest(ctx, expected_e(ctx))
    result = check(ctx)
    assert field(result, "hit") is True
    assert field(result, "reason") is None


def test_changed_definition_misses(tmp_path):
    ctx = build(tmp_path)
    write_manifest(ctx, expected_e(ctx))
    write(ctx["definition"], "# Asset kind fake\n\nA changed definition text.\n")
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_changed_adapter_misses(tmp_path):
    ctx = build(tmp_path)
    write_manifest(ctx, expected_e(ctx))
    with open(ctx["fake_adapter"], "a") as handle:
        handle.write("# a comment line\n")
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_fake_provision_failure_misses_with_its_reason(tmp_path):
    ctx = build(tmp_path)
    write_manifest(ctx, expected_e(ctx))
    write(ctx["fake_adapter"],
          fake_adapter_source(ctx["fake_log"], False, "fake needs fakec >= 2"))
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "fake needs fakec >= 2"


def test_unknown_kind_misses(tmp_path):
    ctx = build(tmp_path)
    write_manifest(ctx, expected_e(ctx))
    write(ctx["component_md"], component_md("assets: [nokind:static/b.x]"))
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "unknown asset kind: nokind"


def test_python_provision_failure_misses_before_fake(tmp_path):
    reason = "python environment: requirements.lock does not pin pytest"
    ctx = build(tmp_path, python_ok=False, python_reason=reason)
    write_manifest(ctx, expected_e(ctx))
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == reason
    assert log_lines(ctx["fake_log"]) == []


def test_removed_component_md_has_only_python_asset(tmp_path):
    ctx = build(tmp_path)
    ctx["component_md"].unlink()
    key = provenance_checker.current_provenance_key("comp-foo", ctx["repo"])
    p = expected_p(ctx)
    assert field(key, "assets") == [p]
    write_manifest(ctx, [p])
    result = check(ctx)
    assert field(result, "hit") is True
    assert field(result, "reason") is None


def test_sealed_component_has_no_assets_and_no_provision(tmp_path):
    ctx = build(tmp_path, extra_lines=("sealed: true", "source_path: legacy/foo/"))
    key = provenance_checker.current_provenance_key("comp-foo", ctx["repo"])
    assert field(key, "assets") == []
    assert log_lines(ctx["python_log"]) == []
    assert log_lines(ctx["fake_log"]) == []


@pytest.mark.parametrize("assets", [MISSING, None], ids=["no-field", "null"])
def test_manifest_without_assets_misses(tmp_path, assets):
    ctx = build(tmp_path)
    write_manifest(ctx, assets)
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


@pytest.mark.parametrize("assets", [MISSING, None], ids=["no-field", "null"])
def test_manifest_without_assets_misses_with_component_md_removed(tmp_path, assets):
    ctx = build(tmp_path)
    ctx["component_md"].unlink()
    write_manifest(ctx, assets)
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_other_spec_bundle_hash_misses_without_provision(tmp_path):
    ctx = build(tmp_path)
    write_manifest(ctx, expected_e(ctx), spec_bundle_hash="OTHER")
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"
    assert log_lines(ctx["python_log"]) == []
    assert log_lines(ctx["fake_log"]) == []