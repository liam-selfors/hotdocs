# Testing kind-python

Tests import the module as `import kind_python` and call its functions
directly; this component's own tests never use an `asset_runner`
fixture. They run under the same Python as the module, so
`sys.executable` and `sys.version_info` give the values a
criterion compares with.

Fixtures: a code directory is a directory under pytest's `tmp_path`
named as the criterion names it; write each file with
`path.write_text(text, encoding="utf-8")` (or `write_bytes` where a
criterion gives bytes), creating parent directories first, exactly as
the criterion shows it, and pass the directory's `Path`. A fresh copy
is `shutil.copytree(src, dst)`.

No test may reach the network. Never call `pip` yourself, and never
write a lock that pins `pytest` without `--no-index` as its first
line.

A local lock: build an offline wheel with `zipfile` at
`tmp_path / "wheels" / "pytest-0.0.1-py3-none-any.whl` holding exactly
three members, `pytest-0.0.1.dist-info/METADATA` (text
`"Metadata-Version: 2.1\nName: pytest\nVersion: 0.0.1\n"`),
`pytest-0.0.1.dist-info/WHEEL` (text
`"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"`)
and `pytest-0.0.1.dist-info/RECORD` (empty). The local lock is
`f"--no-index\n--find-links {tmp_path / 'wheels'}\npytest==0.0.1\n"`.
pip installs it into the new environment without the network.

Every test starts with `monkeypatch.delenv("HOTDOCS_PYTHON",
raising=False)` so `surface` and `asset_runner` use `sys.executable`,
unless the criterion sets it.

Catch failures with `pytest.raises(kind_python.AssetError)` or
`pytest.raises(ValueError)` and compare `str(excinfo.value)` exactly
where a criterion gives the message. Never start Python yourself with
`subprocess`.
