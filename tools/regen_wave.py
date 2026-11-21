"""Lands an ordered list of components, stopping at the first that cannot land.

For each component, in the order given (use tools/cascade_plan.py to get a
dependency-first order):

1. provenance already hits            -> skipped
2. manifest hash equals current hash  -> tools/rerecord_provenance.py
   (only scans or verification are stale; the code is unchanged)
3. otherwise                          -> tools/bootstrap_component.py, trying
   seeds `--seed` .. `--seed + --seeds - 1` until one lands. `--hand-suite`
   is added when verification/<slug>/ has hand tests, `--sealed-install`
   when the component is sealed.

    python tools/regen_wave.py --model=claude-opus-5-5 [--seed=1] [--seeds=3] comp-a comp-b ...

Runs bootstrap in a subprocess, so the environment it inherits applies;
for the claude-cli provider set CLAUDE_CODE_MAX_OUTPUT_TOKENS and
MAX_THINKING_TOKENS (QUICKSTART section 6). Writes a log line per
component to stdout. Exit 0 when every component landed, 1 otherwise.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable


def _sealed(slug: str) -> bool:
    front = (REPO / "specs" / "components" / slug / "component.md").read_text(encoding="utf-8").split("\n---", 1)[0]
    return bool(re.search(r"^sealed:\s*true\s*$", front, re.M))


def _has_hand_suite(slug: str) -> bool:
    vdir = REPO / "verification" / slug
    return vdir.is_dir() and any(p.name.startswith("test_") and p.suffix == ".py" for p in vdir.iterdir())


def _provenance_state(component_id: str) -> str:
    """'hit', 'rerecordable' or 'stale', read through the real provenance-checker."""
    code = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, %r)\n"
        "import provenance_checker as pc\n"
        "r = Path(%r); cid = %r\n"
        "g = lambda o, k: o.get(k) if isinstance(o, dict) else getattr(o, k, None)\n"
        "if pc.current_sealed_key(cid, r) is not None:\n"
        "    print('hit' if g(pc.check_sealed_provenance(cid, r), 'hit') else 'stale'); sys.exit()\n"
        "k = pc.current_provenance_key(cid, r)\n"
        "if g(pc.check_provenance(cid, g(k, 'spec_bundle_hash'), g(k, 'gate_versions'), r), 'hit'):\n"
        "    print('hit'); sys.exit()\n"
        "m = r / 'gen' / cid.removeprefix('comp-') / '.provenance.json'\n"
        "same = m.is_file() and json.loads(m.read_text()).get('spec_bundle_hash') == g(k, 'spec_bundle_hash')\n"
        "print('rerecordable' if same else 'stale')\n"
    ) % (str(REPO / "gen" / "provenance-checker"), str(REPO), component_id)
    out = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=REPO)
    return out.stdout.strip().splitlines()[-1] if out.returncode == 0 and out.stdout.strip() else "stale"


def _bootstrap(component_id: str, model: str, seed: int) -> tuple[bool, str]:
    slug = component_id.removeprefix("comp-")
    cmd = [PY, "-u", str(REPO / "tools" / "bootstrap_component.py"), component_id,
           f"--model={model}", f"--seed={seed}"]
    if _sealed(slug):
        cmd.append("--sealed-install")
    if _has_hand_suite(slug):
        cmd.append("--hand-suite")
    # The caller's directory: llm-endpoint finds hotdocs.toml (provider,
    # timeout) from the current directory (R-ENDPOINT-007).
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
    lines = (proc.stdout + proc.stderr).splitlines()
    summary = next((l for l in reversed(lines) if l.startswith(("PASS", "FAIL"))), lines[-1] if lines else "")
    landed = proc.returncode == 0 and summary.startswith("PASS") and not any(
        l.startswith("PROVENANCE MISS") for l in lines)
    return landed, summary


def main(argv) -> int:
    opts = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in argv if a.startswith("--") and "=" in a}
    components = [a for a in argv if not a.startswith("--")]
    model = opts.get("--model")
    if not model or not components:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    seed, seeds = int(opts.get("--seed", "1")), int(opts.get("--seeds", "3"))
    for component_id in components:
        state = _provenance_state(component_id)
        if state == "hit":
            print(f"{component_id}: provenance hit, skipped", flush=True)
            continue
        if state == "rerecordable":
            proc = subprocess.run([PY, str(REPO / "tools" / "rerecord_provenance.py"), component_id],
                                  capture_output=True, text=True, cwd=REPO)
            print((proc.stdout or proc.stderr).strip(), flush=True)
            if proc.returncode == 0:
                continue
        for s in range(seed, seed + seeds):
            landed, summary = _bootstrap(component_id, model, s)
            print(f"{component_id}: seed {s}: {summary}", flush=True)
            if landed:
                break
        else:
            print(f"{component_id}: did not land in {seeds} seed(s); stopping the wave", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
