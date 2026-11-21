# hotdocs-criterion: sha256:a695848b21508b518061e19619e0731e9f99fa3f9145b014016013cd585013c0
import re

import kind_javascript


def test_provision_with_node_24_or_later_reports_ok(tmp_path):
    result = kind_javascript.provision(tmp_path)

    assert isinstance(result, dict)
    assert set(result.keys()) == {"ok", "reason", "versions", "lockfile_sha256"}
    assert len(result) == 4

    assert result["ok"] is True
    assert result["reason"] == ""
    assert result["lockfile_sha256"] is None

    versions = result["versions"]
    assert isinstance(versions, dict)
    assert list(versions.keys()) == ["node"]
    version = versions["node"]
    assert isinstance(version, str)
    assert re.match(r"^\d+\.\d+\.\d+$", version), version
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
    major = int(version.split(".")[0])
    assert major >= 24

    assert list(tmp_path.iterdir()) == []