# Testing kind-javascript

Tests import the module as `import kind_javascript` and call its
functions directly; this component's own tests never use an
`asset_runner` fixture. Node 24 or later is on `PATH` where tests run.

Fixtures: write each JavaScript file with
`path.write_text(text, encoding="utf-8")` (or `write_bytes` where a
criterion gives bytes) under pytest's `tmp_path`, exactly as the
criterion shows it, and pass the `Path`.

No node: make an empty directory and point `PATH` at it with
`monkeypatch.setenv("PATH", str(empty_dir))`. The module looks `node` up
at call time, so the change takes effect at once.

A fake node: in its own directory write a file named `node` holding
`#!/bin/sh\necho v18.2.0\n` (or another line in place of `v18.2.0`),
`chmod` it to `0o755`, and set `PATH` to that directory alone with
`monkeypatch.setenv`.

Catch failures with `pytest.raises(kind_javascript.AssetError)` and
compare `str(excinfo.value)` exactly where a criterion gives the
message. Compare `run` results with `==` against the exact values given.
Never start `node` yourself.
