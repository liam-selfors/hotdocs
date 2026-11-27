# hotdocs-criterion: sha256:6eb7819f271daa0d5b50154f9767341c82206ea636ea2c77c8b5273b367fe9ba
import kind_css


EXPECTED = {"ok": True, "reason": "", "versions": {}, "lockfile_sha256": None}


def test_ac_kcss_005_provision_twice_new_dicts_nothing_touched(tmp_path):
    repo_root = tmp_path

    first = kind_css.provision(repo_root)
    second = kind_css.provision(repo_root)

    assert isinstance(first, dict)
    assert isinstance(second, dict)
    assert first == EXPECTED
    assert second == EXPECTED
    assert set(first.keys()) == {"ok", "reason", "versions", "lockfile_sha256"}
    assert set(second.keys()) == {"ok", "reason", "versions", "lockfile_sha256"}

    assert first is not second

    assert list(tmp_path.iterdir()) == []


def test_ac_kcss_005_results_independent(tmp_path):
    first = kind_css.provision(tmp_path)
    second = kind_css.provision(tmp_path)

    first["ok"] = False
    first["versions"]["x"] = "1"

    third = kind_css.provision(tmp_path)
    assert third == EXPECTED
    assert second == EXPECTED
    assert list(tmp_path.iterdir()) == []