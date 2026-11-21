# hotdocs-criterion: sha256:8b2c75b3cbdc8a8eb8d4ade9f963a132e0e818e5e54c8eea7675d9e66f14af84
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
X = "sha256:" + "b" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def adapter_source(kind, state_path, default_versions, with_interpreter, guidance):
    lines = []
    lines.append("import json")
    lines.append("import os")
    lines.append("")
    lines.append("KIND = " + repr(kind))
    lines.append("_STATE = " + repr(str(state_path)))
    lines.append("")
    lines.append("")
    lines.append("def guidance():")
    lines.append("    return " + repr(guidance))
    lines.append("")
    lines.append("")
    lines.append("def provision(repo_root):")
    lines.append("    versions = " + repr(default_versions))
    lines.append("    lock = None")
    lines.append("    if os.path.exists(_STATE):")
    lines.append("        with open(_STATE, 'r', encoding='utf-8') as f:")
    lines.append("            data = json.load(f)")
    lines.append("        if 'versions' in data:")
    lines.append("            versions = data['versions']")
    lines.append("        if 'lockfile_sha256' in data:")
    lines.append("            lock = data['lockfile_sha256']")
    lines.append("    result = {'ok': True, 'reason': '', 'versions': versions, 'lockfile_sha256': lock}")
    if with_interpreter:
        lines.append("    result['interpreter'] = '/fake/python'")
    lines.append("    return result")
    lines.append("")
    return "\n".join(lines)


def write_state(path, versions, lockfile_sha256):
    Path(path).write_text(
        json.dumps({"versions": versions, "lockfile_sha256": lockfile_sha256}),
        encoding="utf-8",
    )


def build(tmp_path):
    repo_root = tmp_path / "repo"
    state_dir = tmp_path / "state"
    repo_root.mkdir()
    state_dir.mkdir()
    py_state = state_dir / "python.json"
    fake_state = state_dir / "fake.json"
    write_state(py_state, {"python": "3.12.4", "packages": PK}, None)
    write_state(fake_state, {"fakec": "2.0.0"}, None)

    py_adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    py_adapter.parent.mkdir(parents=True)
    py_adapter.write_text(
        adapter_source(
            "python",
            py_state,
            {"python": "3.12.4", "packages": PK},
            True,
            {"generator": "", "test_author": ""},
        ),
        encoding="utf-8",
    )

    fake_adapter = repo_root / "gen" / "kind-fake" / "kind_fake.py"
    fake_adapter.parent.mkdir(parents=True)
    fake_adapter.write_text(
        adapter_source(
            "fake",
            fake_state,
            {"fakec": "2.0.0"},
            False,
            {"generator": "G.", "test_author": "T."},
        ),
        encoding="utf-8",
    )

    definition = repo_root / "specs" / "architecture" / "asset-kind-fake.md"
    definition.parent.mkdir(parents=True)
    definition.write_text("# Asset kind fake\n\nFixed definition text.\n", encoding="utf-8")

    component_md = repo_root / "specs" / "components" / "foo" / "component.md"
    component_md.parent.mkdir(parents=True)
    component_md.write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "assets: [fake:static/a.fake]\n"
        "---\n"
        "\n"
        "# Foo\n",
        encoding="utf-8",
    )

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha(py_adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    fake_entry = {
        "kind": "fake",
        "path": "static/a.fake",
        "definition_sha256": sha(definition),
        "adapter_sha256": sha(fake_adapter),
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    E = [p_entry, fake_entry]

    return {
        "repo_root": repo_root,
        "py_state": py_state,
        "fake_state": fake_state,
        "definition": definition,
        "P": p_entry,
        "E": E,
    }


def write_manifest(ctx, assets, gate_versions=None):
    manifest = {
        "spec_bundle_hash": "H",
        "gate_versions": {} if gate_versions is None else gate_versions,
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": assets,
    }
    path = ctx["repo_root"] / "gen" / "foo" / ".provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")


def check(ctx):
    return provenance_checker.check_provenance("comp-foo", "H", {}, ctx["repo_root"])


def _python_newer(ctx):
    write_state(ctx["py_state"], {"python": "3.12.5", "packages": PK}, None)


def _python_packages(ctx):
    write_state(ctx["py_state"], {"python": "3.12.4", "packages": X}, None)


def _fake_versions(ctx):
    write_state(ctx["fake_state"], {"fakec": "2.1.0"}, None)


def _fake_lockfile(ctx):
    write_state(ctx["fake_state"], {"fakec": "2.0.0"}, X)


def _both(ctx):
    _python_newer(ctx)
    _fake_versions(ctx)


@pytest.mark.parametrize(
    "change",
    [_python_newer, _python_packages, _fake_versions, _fake_lockfile, _both],
    ids=["python-version", "python-packages", "fake-versions", "fake-lockfile", "both"],
)
def test_only_versions_or_lockfile_differ_is_environment_differs(tmp_path, change):
    ctx = build(tmp_path)
    write_manifest(ctx, ctx["E"])
    change(ctx)
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "environment differs"


def _definition_changes(ctx):
    write_manifest(ctx, ctx["E"])
    ctx["definition"].write_text("# Asset kind fake\n\nChanged definition text.\n", encoding="utf-8")


def _assets_only_p(ctx):
    write_manifest(ctx, [ctx["P"]])


def _assets_reversed(ctx):
    write_manifest(ctx, list(reversed(ctx["E"])))


def _assets_appended(ctx):
    write_manifest(ctx, ctx["E"] + [dict(ctx["E"][1])])


def _fake_adapter_hash(ctx):
    e = [dict(entry) for entry in ctx["E"]]
    e[1]["adapter_sha256"] = X
    write_manifest(ctx, e)


def _fake_lacks_definition(ctx):
    e = [dict(entry) for entry in ctx["E"]]
    del e[1]["definition_sha256"]
    write_manifest(ctx, e)


@pytest.mark.parametrize(
    "variant",
    [
        _definition_changes,
        _assets_only_p,
        _assets_reversed,
        _assets_appended,
        _fake_adapter_hash,
        _fake_lacks_definition,
    ],
    ids=[
        "definition-changes",
        "only-p",
        "reversed",
        "appended",
        "adapter-hash",
        "lacks-definition",
    ],
)
def test_other_differences_stay_assets_differ(tmp_path, variant):
    ctx = build(tmp_path)
    _python_newer(ctx)
    variant(ctx)
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "assets differ"


def test_gate_versions_differ_takes_precedence(tmp_path):
    ctx = build(tmp_path)
    _python_newer(ctx)
    write_manifest(ctx, ctx["E"], gate_versions={"verifier": "v@0"})
    result = check(ctx)
    assert field(result, "hit") is False
    assert field(result, "reason") == "gate_versions differ"


def test_versions_set_back_hits(tmp_path):
    ctx = build(tmp_path)
    write_manifest(ctx, ctx["E"])
    _both(ctx)
    first = check(ctx)
    assert field(first, "hit") is False
    assert field(first, "reason") == "environment differs"

    write_state(ctx["py_state"], {"python": "3.12.4", "packages": PK}, None)
    write_state(ctx["fake_state"], {"fakec": "2.0.0"}, None)
    result = check(ctx)
    assert field(result, "hit") is True