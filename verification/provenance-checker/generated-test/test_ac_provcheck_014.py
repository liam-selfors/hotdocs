# hotdocs-criterion: sha256:573aa95133b47ef7a82a5622c6a249266095987125fddeb2ae312215724780d1
import hashlib
import json
import os
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
_MISSING = object()


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _adapter_source(kind, guidance, log, override, default):
    return (
        "import json\n"
        "import os\n"
        "\n"
        "KIND = " + repr(kind) + "\n"
        "_LOG = " + repr(str(log)) + "\n"
        "_OVERRIDE = " + repr(str(override)) + "\n"
        "_DEFAULT = " + repr(default) + "\n"
        "_GUIDANCE = " + repr(guidance) + "\n"
        "\n"
        "\n"
        "class AssetError(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return dict(_GUIDANCE)\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('provision\\n')\n"
        "    result = json.loads(json.dumps(_DEFAULT))\n"
        "    if os.path.exists(_OVERRIDE):\n"
        "        with open(_OVERRIDE, encoding='utf-8') as fh:\n"
        "            result.update(json.load(fh))\n"
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
        "    def run(entry_point, args):\n"
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


def _plant_dependencies(repo_root, log):
    log = str(log)
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "_LOG = " + repr(log) + "\n"
        "\n"
        "\n"
        "class _Bundle:\n"
        "    def __init__(self, **kw):\n"
        "        for k, v in kw.items():\n"
        "            setattr(self, k, v)\n"
        "        self._fields = kw\n"
        "\n"
        "    def __getitem__(self, k):\n"
        "        return self._fields[k]\n"
        "\n"
        "    def get(self, k, default=None):\n"
        "        return self._fields.get(k, default)\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble ' + repr((component_id, str(repo_root), mode)) + '\\n')\n"
        "    return _Bundle(component_id=component_id, spec_bundle_hash='sha256:abc',\n"
        "                   spec='', interface='', constraints='',\n"
        "                   dependency_interfaces={}, dependency_context={},\n"
        "                   dependency_usage={}, vars={}, glossary='', hint_code=None)\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root=None):\n"
        "    return _Bundle(component_id=component_id, criterion_id=criterion_id,\n"
        "                   covers='', criterion_text='', requirement_text='',\n"
        "                   interface='', glossary='', dependency_interfaces={},\n"
        "                   testing='')\n",
    )
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = " + repr("cc@1") + "\n",
    )
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = " + repr("ta@1") + "\n",
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr("vo@1") + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n",
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        "_LOG = " + repr(log) + "\n"
        "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ls@1'\n"
        "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('license scan\\n')\n"
        "    return {'component_id': component_id, 'gate_version': 'ls@1',\n"
        "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
        "            'similarity_score': None, 'block_threshold': None,\n"
        "            'blocked': False, 'matches': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n",
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        "_LOG = " + repr(log) + "\n"
        "\n"
        "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def _result(scope):\n"
        "    return {'scope': scope, 'gate_version': 'ss@1', 'flagged': False,\n"
        "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
        "            'notified': False, 'notification_delivery_error': None,\n"
        "            'cache_hit': False}\n"
        "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'ss@1'\n"
        "\n"
        "\n"
        "def scan(repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('secret scan\\n')\n"
        "    return _result('full')\n"
        "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('secret scan_files\\n')\n"
        "    return _result('precommit')\n"
        "\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )
    _write(
        repo_root / "gen" / "generator" / "generator.py",
        "GATE_VERSION = " + repr("gen@3") + "\n"
        "PROMPT_VERSION = " + repr("v11") + "\n",
    )


def _component_md(assets_line=None, sealed=False):
    text = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
    )
    if sealed:
        text += "sealed: true\n"
    if assets_line is not None:
        text += "assets: [" + assets_line + "]\n"
    text += "---\n\n# Foo\n"
    return text


class Ctx:
    pass


def _build(tmp_path, assets_line="fake:static/a.fake"):
    ctx = Ctx()
    ctx.repo_root = tmp_path / "repo"
    ctx.repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    ctx.python_log = logs / "python.log"
    ctx.fake_log = logs / "fake.log"
    ctx.python_override = logs / "python_override.json"
    ctx.fake_override = logs / "fake_override.json"
    ctx.dep_log = logs / "deps.log"

    ctx.python_adapter = ctx.repo_root / "gen" / "kind-python" / "kind_python.py"
    _write(
        ctx.python_adapter,
        _adapter_source(
            "python",
            {"generator": "", "test_author": ""},
            ctx.python_log,
            ctx.python_override,
            {"ok": True, "reason": "", "versions": {"python": "3.12.4", "packages": PK},
             "lockfile_sha256": None, "interpreter": "/fake/python"},
        ),
    )
    ctx.fake_adapter = ctx.repo_root / "gen" / "kind-fake" / "kind_fake.py"
    _write(
        ctx.fake_adapter,
        _adapter_source(
            "fake",
            {"generator": "G.", "test_author": "T."},
            ctx.fake_log,
            ctx.fake_override,
            {"ok": True, "reason": "", "versions": {"fakec": "2.0.0"},
             "lockfile_sha256": None},
        ),
    )
    ctx.definition = ctx.repo_root / "specs" / "architecture" / "asset-kind-fake.md"
    _write(ctx.definition, "# Asset kind: fake\n\nA fixed fake definition.\n")

    ctx.component_md = ctx.repo_root / "specs" / "components" / "foo" / "component.md"
    _write(ctx.component_md, _component_md(assets_line))

    _plant_dependencies(ctx.repo_root, ctx.dep_log)
    ctx.manifest = ctx.repo_root / "gen" / "foo" / ".provenance.json"
    return ctx


def _expected_p(ctx):
    return {"kind": "python", "path": ".", "definition_sha256": None,
            "adapter_sha256": _sha(ctx.python_adapter),
            "versions": {"python": "3.12.4", "packages": PK},
            "lockfile_sha256": None}


def _expected_e(ctx):
    return [
        _expected_p(ctx),
        {"kind": "fake", "path": "static/a.fake",
         "definition_sha256": _sha(ctx.definition),
         "adapter_sha256": _sha(ctx.fake_adapter),
         "versions": {"fakec": "2.0.0"}, "lockfile_sha256": None},
    ]


def _write_manifest(ctx, spec_hash="H", assets=_MISSING):
    manifest = {
        "spec_bundle_hash": spec_hash,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
    }
    if assets is not _MISSING:
        manifest["assets"] = assets
    _write(ctx.manifest, json.dumps(manifest))


def _clear_logs(ctx):
    for p in (ctx.python_log, ctx.fake_log):
        if p.exists():
            p.unlink()


def _calls(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _check(ctx):
    return provenance_checker.check_provenance("comp-foo", "H", {}, ctx.repo_root)


def test_current_provenance_key_assets_is_e(tmp_path):
    ctx = _build(tmp_path)
    key = provenance_checker.current_provenance_key("comp-foo", ctx.repo_root)
    assert field(key, "assets") == _expected_e(ctx)


def test_manifest_with_e_is_hit(tmp_path):
    ctx = _build(tmp_path)
    _write_manifest(ctx, assets=_expected_e(ctx))
    result = _check(ctx)
    assert field(result, "hit") is True
    assert field(result, "reason") is None


def test_definition_changed_after_manifest_misses(tmp_path):
    ctx = _build(tmp_path)
    _write_manifest(ctx, assets=_expected_e(ctx))
    _write(ctx.definition, "# Asset kind: fake\n\nA changed fake definition.\n")
    result = _check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_adapter_changed_after_manifest_misses(tmp_path):
    ctx = _build(tmp_path)
    _write_manifest(ctx, assets=_expected_e(ctx))
    with open(ctx.fake_adapter, "a", encoding="utf-8") as fh:
        fh.write("# a comment line appended after the manifest\n")
    result = _check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_fake_provision_not_ok_reason_verbatim(tmp_path):
    ctx = _build(tmp_path)
    _write_manifest(ctx, assets=_expected_e(ctx))
    _write(ctx.fake_override, json.dumps({"ok": False, "reason": "fake needs fakec >= 2"}))
    result = _check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "fake needs fakec >= 2"


def test_unknown_kind_misses(tmp_path):
    ctx = _build(tmp_path)
    _write_manifest(ctx, assets=_expected_e(ctx))
    _write(ctx.component_md, _component_md("nokind:static/b.x"))
    result = _check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "unknown asset kind: nokind"


def test_python_provision_not_ok_stops_before_fake(tmp_path):
    ctx = _build(tmp_path)
    _write_manifest(ctx, assets=_expected_e(ctx))
    reason = "python environment: requirements.lock does not pin pytest"
    _write(ctx.python_override, json.dumps({"ok": False, "reason": reason}))
    _clear_logs(ctx)
    result = _check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == reason
    assert _calls(ctx.fake_log) == []


def test_component_md_removed_assets_is_python_only(tmp_path):
    ctx = _build(tmp_path)
    ctx.component_md.unlink()
    p = _expected_p(ctx)
    key = provenance_checker.current_provenance_key("comp-foo", ctx.repo_root)
    assert field(key, "assets") == [p]
    _write_manifest(ctx, assets=[p])
    result = _check(ctx)
    assert field(result, "hit") is True
    assert field(result, "reason") is None


def test_sealed_component_assets_empty_no_provision(tmp_path):
    ctx = _build(tmp_path)
    _write(ctx.component_md, _component_md("fake:static/a.fake", sealed=True))
    _clear_logs(ctx)
    key = provenance_checker.current_provenance_key("comp-foo", ctx.repo_root)
    assert field(key, "assets") == []
    assert _calls(ctx.python_log) == []
    assert _calls(ctx.fake_log) == []


@pytest.mark.parametrize("assets", [_MISSING, None], ids=["no-assets-field", "assets-null"])
@pytest.mark.parametrize("remove_component", [False, True], ids=["declared", "component-removed"])
def test_manifest_without_assets_misses(tmp_path, assets, remove_component):
    ctx = _build(tmp_path)
    if remove_component:
        ctx.component_md.unlink()
    _write_manifest(ctx, assets=assets)
    result = _check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_spec_bundle_hash_differs_no_provision(tmp_path):
    ctx = _build(tmp_path)
    _write_manifest(ctx, spec_hash="OTHER", assets=_expected_e(ctx))
    _clear_logs(ctx)
    result = _check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"
    assert _calls(ctx.python_log) == []
    assert _calls(ctx.fake_log) == []