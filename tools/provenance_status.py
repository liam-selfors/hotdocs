"""Read-only: does every component's provenance check hit right now?

    python tools/provenance_status.py           # one line per miss, then a summary
    python tools/provenance_status.py --all     # one line per component

Uses the real provenance-checker: `check_sealed_provenance` for a sealed
component, otherwise `current_provenance_key` then `check_provenance`.
Exit 0 when every component hits, 1 otherwise.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "gen" / "provenance-checker"))
import provenance_checker as pc  # noqa: E402


def _get(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def status(component_id: str) -> tuple[bool, object]:
    if pc.current_sealed_key(component_id, REPO) is not None:
        result = pc.check_sealed_provenance(component_id, REPO)
    else:
        key = pc.current_provenance_key(component_id, REPO)
        gate_versions = dict(_get(key, "gate_versions"))
        if "generator" not in gate_versions:
            # D313: until the provenance-checker that names the generator
            # lands, compare against the key it will compute.
            gen = REPO / "gen" / "generator" / "generator.py"
            ns = {}
            for line in gen.read_text(encoding="utf-8").splitlines():
                if line.startswith(("GATE_VERSION =", "PROMPT_VERSION =")):
                    exec(line, ns)
            if "PROMPT_VERSION" in ns:
                gate_versions["generator"] = f"{ns['GATE_VERSION']}+{ns['PROMPT_VERSION']}"
        result = pc.check_provenance(component_id, _get(key, "spec_bundle_hash"), gate_versions, REPO)
    return bool(_get(result, "hit")), _get(result, "reason")


def main(argv) -> int:
    show_all = "--all" in argv
    misses = 0
    components = sorted(p.name for p in (REPO / "specs" / "components").iterdir() if p.is_dir())
    for slug in components:
        hit, reason = status("comp-" + slug)
        misses += not hit
        if show_all or not hit:
            print(f"comp-{slug}: {'hit' if hit else 'MISS'}{'' if hit or not reason else ' (' + str(reason) + ')'}")
    print(f"{len(components) - misses} of {len(components)} components hit")
    return 0 if misses == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
