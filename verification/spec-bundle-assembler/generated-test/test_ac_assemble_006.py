"""AC-ASSEMBLE-006: assembling the same component twice over an unchanged
corpus yields byte-identical SpecBundles (R-ASSEMBLE-006)."""

import dataclasses
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import spec_bundle_assembler


COMPONENT_ID = "comp-spec-bundle-assembler"
COMPONENT_SLUG = "spec-bundle-assembler"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _find_repo_root():
    override = os.environ.get("HOTDOCS_REPO_ROOT")
    if override:
        return Path(override).resolve()
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        marker = candidate / "specs" / "components" / COMPONENT_SLUG / "component.md"
        if marker.is_file():
            return candidate
    for candidate in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        marker = candidate / "specs" / "components" / COMPONENT_SLUG / "component.md"
        if marker.is_file():
            return candidate
    pytest.fail(
        "could not locate the corpus repo root containing "
        f"specs/components/{COMPONENT_SLUG}/component.md"
    )


def _to_jsonable(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _to_jsonable(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "_asdict"):
        return _to_jsonable(value._asdict())
    if hasattr(value, "__dict__"):
        return {
            k: _to_jsonable(v)
            for k, v in vars(value).items()
            if not k.startswith("_")
        }
    return repr(value)


def _bundle_bytes(bundle):
    # Key order is preserved (no sort_keys) so that any nondeterminism in
    # field or mapping ordering also shows up as a byte difference.
    return json.dumps(
        _to_jsonable(bundle), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


@pytest.fixture(scope="module")
def repo_root():
    return _find_repo_root()


def test_assemble_twice_is_byte_identical(repo_root):
    first = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root)
    second = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root)

    assert _get(first, "component_id") == COMPONENT_ID
    assert _get(second, "component_id") == COMPONENT_ID

    first_bytes = _bundle_bytes(first)
    second_bytes = _bundle_bytes(second)
    assert first_bytes == second_bytes

    first_hash = _get(first, "spec_bundle_hash")
    second_hash = _get(second, "spec_bundle_hash")
    assert first_hash, "spec_bundle_hash must be populated"
    assert first_hash == second_hash


def test_assemble_twice_explicit_cold_mode_is_byte_identical(repo_root):
    first = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root, mode="cold")
    second = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root, mode="cold")

    assert _bundle_bytes(first) == _bundle_bytes(second)
    assert _get(first, "spec_bundle_hash") == _get(second, "spec_bundle_hash")
    assert _get(first, "hint_code") is None
    assert _get(second, "hint_code") is None


def test_cli_json_output_twice_is_byte_identical(repo_root):
    exe = shutil.which("hotdocs")
    if exe is None:
        pytest.skip("hotdocs CLI not on PATH; library-level determinism covered above")

    cmd = [
        exe,
        "assemble",
        COMPONENT_ID,
        f"--repo-root={repo_root}",
        "--format=json",
    ]
    first = subprocess.run(cmd, capture_output=True, cwd=str(repo_root))
    second = subprocess.run(cmd, capture_output=True, cwd=str(repo_root))

    assert first.returncode == 0, first.stderr.decode("utf-8", "replace")
    assert second.returncode == 0, second.stderr.decode("utf-8", "replace")
    assert first.stdout == second.stdout
    assert first.stdout.strip(), "expected a JSON SpecBundle on stdout"