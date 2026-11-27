# hotdocs-criterion: sha256:b0bad0fddd1164d34997425174ef2940f0eaf9f540fb3cacba7afaef394b968a
import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def log_lines(path):
    path = Path(path)
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def plant_python_adapter(repo_root):
    pk = "sha256:" + "a" * 64
    src = "\n".join([
        "KIND = 'python'",
        "",
        "",
        "def guidance():",
        "    return {'generator': '', 'test_author': ''}",
        "",
        "",
        "def provision(repo_root):",
        "    return {'ok': True, 'reason': '', 'versions': {'python': '3.12.4', 'packages': " + repr(pk) + "}, 'lockfile_sha256': None, 'interpreter': '/fake/python'}",
        "",
    ])
    write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def plant_component(repo_root):
    src = "\n".join([
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "---",
        "",
        "# Foo",
        "",
    ])
    write(repo_root / "specs" / "components" / "foo" / "component.md", src)


def plant_assembler(repo_root, log_path, fail):
    src = "\n".join([
        "import json",
        "",
        "LOG = " + repr(str(log_path)),
        "FAIL = " + repr(bool(fail)),
        "",
        "",
        "class SpecBundle:",
        "    def __init__(self, **kw):",
        "        for k, v in kw.items():",
        "            setattr(self, k, v)",
        "        self._keys = list(kw)",
        "",
        "    def __getitem__(self, k):",
        "        if k not in self._keys:",
        "            raise KeyError(k)",
        "        return getattr(self, k)",
        "",
        "    def get(self, k, default=None):",
        "        return getattr(self, k) if k in self._keys else default",
        "",
        "    def keys(self):",
        "        return list(self._keys)",
        "",
        "",
        "def _log(entry):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps(entry) + '\\n')",
        "",
        "",
        "def assemble(component_id, repo_root, mode='cold'):",
        "    _log({'call': 'assemble', 'component_id': component_id, 'mode': mode, 'repo_root': str(repo_root)})",
        "    if FAIL:",
        "        raise ValueError('assemble failed: boom')",
        "    return SpecBundle(",
        "        component_id=component_id,",
        "        spec_bundle_hash='sha256:abc',",
        "        spec='',",
        "        interface='',",
        "        constraints='',",
        "        dependency_interfaces={},",
        "        dependency_context={},",
        "        dependency_usage={},",
        "        vars={},",
        "        glossary='',",
        "        hint_code=None,",
        "        spec_bundle_parts={'spec': 'sha256:s', 'dependency_code': 'sha256:d'},",
        "    )",
        "",
        "",
        "def assemble_criterion(component_id, criterion_id, repo_root):",
        "    _log({'call': 'assemble_criterion'})",
        "    raise RuntimeError('assemble_criterion must not be called')",
        "",
    ])
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", src)


def plant_gate_constant(path, value, log_path, extra_names):
    lines = [
        "LOG = " + repr(str(log_path)),
        "GATE_VERSION = " + repr(value),
        "",
    ]
    for name in extra_names:
        lines += [
            "",
            "def " + name + "(*args, **kwargs):",
            "    with open(LOG, 'a', encoding='utf-8') as f:",
            "        f.write(" + repr(name + " called") + " + '\\n')",
            "    raise RuntimeError(" + repr(name + " must not be called") + ")",
            "",
        ]
    write(path, "\n".join(lines))


def plant_scanner(path, gate, scan_log, scan_names):
    lines = [
        "SCAN_LOG = " + repr(str(scan_log)),
        "",
        "",
        "def gate_version(repo_root):",
        "    return " + repr(gate),
        "",
    ]
    for name in scan_names:
        lines += [
            "",
            "def " + name + "(*args, **kwargs):",
            "    with open(SCAN_LOG, 'a', encoding='utf-8') as f:",
            "        f.write(" + repr(name + " called") + " + '\\n')",
            "    raise RuntimeError(" + repr(name + " must not be called") + ")",
            "",
        ]
    write(path, "\n".join(lines))


def plant_generator(repo_root, log_path):
    lines = [
        "LOG = " + repr(str(log_path)),
        "GATE_VERSION = 'gen@3'",
        "PROMPT_VERSION = 'v11'",
        "",
    ]
    for name in ["generate", "commit_cache"]:
        lines += [
            "",
            "def " + name + "(*args, **kwargs):",
            "    with open(LOG, 'a', encoding='utf-8') as f:",
            "        f.write(" + repr(name + " called") + " + '\\n')",
            "    raise RuntimeError(" + repr(name + " must not be called") + ")",
            "",
        ]
    write(repo_root / "gen" / "generator" / "generator.py", "\n".join(lines))


def build_repo(tmp_path, fail=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assemble_log = logs / "assemble.log"
    scan_log = logs / "scan.log"
    other_log = logs / "other.log"

    plant_python_adapter(repo_root)
    plant_component(repo_root)
    plant_assembler(repo_root, assemble_log, fail)
    plant_gate_constant(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "cc@1", other_log, ["compile", "compile_criterion"],
    )
    plant_gate_constant(
        repo_root / "gen" / "test-author" / "test_author.py",
        "ta@1", other_log, ["author_test"],
    )
    plant_gate_constant(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "vo@1", other_log, ["verify"],
    )
    plant_scanner(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        "ls@1", scan_log, ["scan"],
    )
    plant_scanner(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        "ss@1", scan_log, ["scan", "scan_files"],
    )
    plant_generator(repo_root, other_log)
    return repo_root, assemble_log, scan_log, other_log


def test_current_provenance_key_reads_bundle_and_gate_versions(tmp_path):
    repo_root, assemble_log, scan_log, other_log = build_repo(tmp_path)

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert field(key, "spec_bundle_hash") == "sha256:abc"
    assert dict(field(key, "spec_bundle_parts")) == {
        "spec": "sha256:s",
        "dependency_code": "sha256:d",
    }

    calls = [json.loads(line) for line in log_lines(assemble_log)]
    assemble_calls = [c for c in calls if c.get("call") == "assemble"]
    assert len(assemble_calls) >= 1
    for c in assemble_calls:
        assert c["component_id"] == "comp-foo"
        assert c["mode"] == "cold"

    assert dict(field(key, "gate_versions")) == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
        "generator": "gen@3+v11",
    }

    assert log_lines(scan_log) == []
    assert log_lines(other_log) == []


def test_current_provenance_key_propagates_assemble_value_error(tmp_path):
    repo_root, assemble_log, scan_log, other_log = build_repo(tmp_path, fail=True)

    with pytest.raises(ValueError, match="assemble failed: boom"):
        provenance_checker.current_provenance_key("comp-foo", repo_root)

    calls = [json.loads(line) for line in log_lines(assemble_log)]
    assert any(c.get("call") == "assemble" for c in calls)
    assert log_lines(scan_log) == []