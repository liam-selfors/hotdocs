# hotdocs-criterion: sha256:cd36f6dcd3697c3ba8d8846ff34188ac184ca29a2615809c0b0d52fcf864b07b
import re

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_kjs_008_provision_with_node_24_or_later(tmp_path):
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
    node_version = versions["node"]
    assert isinstance(node_version, str)
    assert re.match(r"^\d+\.\d+\.\d+$", node_version) is not None
    major = int(node_version.split(".")[0])
    assert major >= 24

    assert list(tmp_path.iterdir()) == []