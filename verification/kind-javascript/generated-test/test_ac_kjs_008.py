# hotdocs-criterion: sha256:e607b949d7ed87901e343f6c8b9eb9e4b5b13d8d54af61f89a6756750b0fc788
import re

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_kjs_008_provision_with_node_24_or_later(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())
    assert before == []

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
    assert re.match(r"^\d+\.\d+\.\d+$", node_version), node_version
    assert re.fullmatch(r"\d+\.\d+\.\d+", node_version), node_version
    major = int(node_version.split(".")[0])
    assert major >= 24

    after = sorted(p.name for p in tmp_path.iterdir())
    assert after == []