# hotdocs-criterion: sha256:d0631e70595def894e562d437f2fc994a9ad4ff6d5881b863d2bc3f98ef93904
import re
import shutil
import subprocess

import pytest

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _node_major():
    node = shutil.which("node")
    if node is None:
        return None
    try:
        proc = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if out.startswith("v"):
        out = out[1:]
    m = re.match(r"^(\d+)\.\d+\.\d+$", out)
    if not m:
        return None
    return int(m.group(1))


def test_ac_kjs_008_provision_ok_with_node_24_or_later(tmp_path):
    major = _node_major()
    if major is None or major < 24:
        pytest.skip("precondition not met: Node 24 or later is not on PATH")

    assert list(tmp_path.iterdir()) == []

    result = kind_javascript.provision(tmp_path)

    assert isinstance(result, dict)
    assert set(result.keys()) == {"ok", "reason", "versions", "lockfile_sha256"}
    assert len(result) == 4

    assert field(result, "ok") is True
    assert field(result, "reason") == ""
    assert field(result, "lockfile_sha256") is None

    versions = field(result, "versions")
    assert isinstance(versions, dict)
    assert list(versions.keys()) == ["node"]
    version = versions["node"]
    assert isinstance(version, str)
    assert re.match(r"^\d+\.\d+\.\d+$", version) is not None
    assert int(version.split(".")[0]) >= 24

    assert list(tmp_path.iterdir()) == []