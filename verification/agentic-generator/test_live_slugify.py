"""Live suite (`D315`): a real model generates the slugify example in
agentic mode, skipped unless HOTDOCS_LIVE=1. Never part of a bootstrap,
a gate, or `hotdocs verify`."""
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = os.environ.get("HOTDOCS_LIVE_MODEL", "claude-cli:claude-opus-5-5")
pytestmark = pytest.mark.skipif(os.environ.get("HOTDOCS_LIVE") != "1", reason="live suite: set HOTDOCS_LIVE=1")


def _load(slug, module):
    spec = importlib.util.spec_from_file_location(module, REPO_ROOT / "gen" / slug / f"{module}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def test_agentic_slugify(tmp_path):
    shutil.copytree(REPO_ROOT / "examples" / "slugify" / "specs", tmp_path / "specs")
    (tmp_path / "specs" / "glossary.md").write_text("# Glossary\n\n- **Slug** — a URL-safe title.\n")
    assembler = _load("spec-bundle-assembler", "spec_bundle_assembler")
    agentic = _load("agentic-generator", "agentic_generator")
    bundle = assembler.assemble("comp-slugify", repo_root=tmp_path, mode="cold")
    result = agentic.generate_agentic(bundle, MODEL, repo_root=tmp_path, max_turns=30, wall_seconds=1500)
    assert result.model_call_error is None, result.model_call_error
    assert result.isolation in ("sandbox-exec", "bwrap")
    probe = subprocess.run(
        [sys.executable, "-c", "import slugify; print(slugify.slugify('Café Déjà Vu'))"],
        cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(tmp_path / "gen" / "slugify")},
        capture_output=True, text=True,
    )
    assert probe.stdout.strip() == "cafe-deja-vu", probe.stderr
