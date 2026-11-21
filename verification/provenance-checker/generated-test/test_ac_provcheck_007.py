# hotdocs-criterion: sha256:94a54a930bb25ea4c73b83753d5be51466384725ad1059095b72a5a36b980875
import hashlib
import json
from pathlib import Path

import provenance_checker


MANIFEST_HASH = "sha256:" + "1" * 64
OTHER_CALLER_HASH = "sha256:" + "2" * 64
STANDIN_ASSEMBLE_HASH = "sha256:" + "3" * 64
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _python_adapter_source():
    return (
        'KIND = "python"\n'
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr({
            "ok": True,
            "reason": "",
            "versions": {"python": "3.12.4", "packages": PK},
            "lockfile_sha256": None,
            "interpreter": "/fake/python",
        }) + "\n"
    )


def _log_header(log_path, name):
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(event):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(event + '\\n')\n"
        "\n"
        "\n"
        "_log(" + repr("load " + name) + ")\n"
        "\n"
    )


def _assembler_source(log_path):
    return (
        _log_header(log_path, "spec-bundle-assembler")
        + "class SpecBundle:\n"
        "    _FIELDS = ('component_id', 'spec_bundle_hash', 'spec', 'interface',\n"
        "               'constraints', 'dependency_interfaces', 'dependency_context',\n"
        "               'dependency_usage', 'vars', 'glossary', 'hint_code')\n"
        "\n"
        "    def __init__(self, **kw):\n"
        "        for k in self._FIELDS:\n"
        "            setattr(self, k, kw[k])\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        if key not in self._FIELDS:\n"
        "            raise KeyError(key)\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        return getattr(self, key) if key in self._FIELDS else default\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble ' + str(component_id) + ' ' + str(mode))\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash=" + repr(STANDIN_ASSEMBLE_HASH) + ",\n"
        "        spec='', interface='', constraints='',\n"
        "        dependency_interfaces={}, dependency_context={},\n"
        "        dependency_usage={}, vars={}, glossary='', hint_code=None,\n"
        "    )\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion')\n"
        "    raise RuntimeError('not used')\n"
    )


def _simple_gate_source(log_path, name, constants, functions):
    src = _log_header(log_path, name)
    for key, value in constants:
        src += key + " = " + repr(value) + "\n"
    src += "\n"
    for fname, params in functions:
        src += (
            "\n"
            "def " + fname + "(" + params + "):\n"
            "    _log(" + repr(name + " " + fname) + ")\n"
            "    raise RuntimeError('stand-in: not used')\n"
        )
    return src


def _gate_version_fn(log_path, name, value):
    return (
        "\n"
        "def gate_version(repo_root):\n"
        "    _log(" + repr(name + " gate_version") + ")\n"
        "    return " + repr(value) + "\n"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "dependency-calls.log"

    # Fake python adapter (implicit asset kind).
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    _write(adapter, _python_adapter_source())

    # Component frontmatter, no assets line, not sealed.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )

    # Dependency stand-ins: any load or call is recorded.
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _assembler_source(log_path),
    )
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        _simple_gate_source(
            log_path, "criterion-compiler",
            [("GATE_VERSION", "cc@1")],
            [("compile", "component_id, repo_root, target='pytest', out_dir=None"),
             ("compile_criterion", "criterion, surface=None")],
        ),
    )
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        _simple_gate_source(
            log_path, "test-author",
            [("GATE_VERSION", "ta@1")],
            [("author_test", "bundle, model, seed=0, *, repo_root=None, llm_backend=None")],
        ),
    )
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        _simple_gate_source(
            log_path, "verifier-orchestrator",
            [("GATE_VERSION", "vo@1"), ("DEFAULT_TEST_TIMEOUT", 300.0)],
            [("verify", "component_id, repo_root, judge=None, test_author=None")],
        ),
    )
    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        _simple_gate_source(
            log_path, "license-scanner", [],
            [("scan", "component_id, repo_root")],
        ) + _gate_version_fn(log_path, "license-scanner", "ls@1"),
    )
    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        _simple_gate_source(
            log_path, "secret-scanner", [],
            [("scan", "repo_root"),
             ("scan_files", "paths, repo_root=None"),
             ("propose", "repo_root")],
        ) + _gate_version_fn(log_path, "secret-scanner", "ss@1"),
    )
    _write(
        repo_root / "gen" / "generator" / "generator.py",
        _simple_gate_source(
            log_path, "generator",
            [("GATE_VERSION", "gen@3"), ("PROMPT_VERSION", "v11")],
            [("generate", "bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None"),
             ("commit_cache", "result, repo_root=None")],
        ),
    )

    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha(adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    manifest = {
        "spec_bundle_hash": MANIFEST_HASH,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest))

    return repo_root, log_path, manifest


def _log_lines(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def test_caller_supplied_hash_matching_manifest_is_a_hit_even_though_assemble_would_differ(tmp_path):
    repo_root, log_path, manifest = build_repo(tmp_path)

    result = provenance_checker.check_provenance("comp-foo", MANIFEST_HASH, {}, repo_root)

    # The caller's hash equals the manifest's own field: a hit, though the
    # stand-in assembler would have produced a different hash.
    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "verification_report") == manifest["verification_report"]

    # check_provenance never computed a spec_bundle_hash of its own: no
    # dependency was loaded or called.
    assert _log_lines(log_path) == []


def test_caller_supplied_hash_differing_from_manifest_is_a_miss_even_though_assemble_would_match(tmp_path):
    repo_root, log_path, _ = build_repo(tmp_path)
    # Make the stand-in assembler agree with the manifest, so only the
    # caller-supplied value can explain a miss.
    src_path = repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py"
    src_path.write_text(
        src_path.read_text().replace(repr(STANDIN_ASSEMBLE_HASH), repr(MANIFEST_HASH))
    )

    result = provenance_checker.check_provenance("comp-foo", OTHER_CALLER_HASH, {}, repo_root)

    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert _log_lines(log_path) == []


def test_stand_in_assembler_is_reachable_so_its_silence_is_meaningful(tmp_path):
    repo_root, log_path, _ = build_repo(tmp_path)

    # Control: the documented key computation does reach the stand-in and
    # yields a hash different from the manifest's, which check_provenance
    # above never consulted.
    key = provenance_checker.current_provenance_key("comp-foo", repo_root)
    assert field(key, "spec_bundle_hash") == STANDIN_ASSEMBLE_HASH
    assert field(key, "spec_bundle_hash") != MANIFEST_HASH
    assert any(line.startswith("assemble ") for line in _log_lines(log_path))

    log_path.unlink()
    result = provenance_checker.check_provenance("comp-foo", MANIFEST_HASH, {}, repo_root)
    assert field(result, "hit") is True
    assert _log_lines(log_path) == []