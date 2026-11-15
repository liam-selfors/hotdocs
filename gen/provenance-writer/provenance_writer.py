"""Provenance writer: assembles and writes `.provenance.json` and
`.sealed-provenance.json` manifests from already-produced upstream results.

Collects, never invents.
"""

import dataclasses
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_VERSION = "v1"

_SEALED_KIND = "sealed-provenance"
_SEALED_VERSION = 1

_COMPONENT_ID_RE = r"comp-[a-z0-9]+(-[a-z0-9]+)*"
_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_SOURCE_HASH_RE = r"sha256:[0-9a-f]{64}"
_VERIFIER_VERSION_RE = r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+"

_REQUIRED_INPUTS = (
    "generation_result",
    "license_scan_result",
    "secret_scan_result",
    "provenance_hit",
    "attempts",
    "gate_versions",
)

_SEALED_INPUT_FIELDS = (
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "verification_report",
)


class MissingInputError(Exception):
    """A required upstream result was absent; no manifest is written."""


class InvalidSealedInputError(Exception):
    """The sealed inputs would not yield a valid sealed provenance manifest."""


@dataclasses.dataclass
class ProvenanceInputs:
    component_id: str
    generation_result: object
    verification_report: object
    license_scan_result: object
    secret_scan_result: object
    provenance_hit: bool
    attempts: int
    gate_versions: dict


@dataclasses.dataclass
class SealedProvenanceInputs:
    component_id: str
    owners: list
    source_path: str
    source_hash: str
    verifier_version: str
    verification_report: object


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _to_jsonable(value):
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _to_jsonable(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    result = {}
    for name in dir(value):
        if name.startswith("_"):
            continue
        attr = getattr(value, name)
        if callable(attr):
            continue
        result[name] = _to_jsonable(attr)
    return result


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(component_id):
    return component_id.removeprefix("comp-")


def build_manifest(inputs):
    """Assemble the provenance manifest dict (SPEC_GUIDELINES.md §7)."""
    for name in _REQUIRED_INPUTS:
        if _field(inputs, name) is None:
            raise MissingInputError(f"missing required input: {name}")

    generation_result = _field(inputs, "generation_result")
    verification_report = _field(inputs, "verification_report")
    if verification_report is None and _field(generation_result, "files"):
        raise MissingInputError(
            "missing required input: verification_report "
            "(generation_result has files)"
        )

    component_id = _field(inputs, "component_id")
    attempts = _field(inputs, "attempts")

    return {
        "spec_bundle_hash": _field(generation_result, "spec_bundle_hash"),
        "model_pin": _field(generation_result, "model"),
        "prompt_version": _field(generation_result, "prompt_version"),
        "retry_feedback": _field(generation_result, "retry_feedback"),
        "pipeline_version": PIPELINE_VERSION,
        "gate_versions": _field(inputs, "gate_versions"),
        "provenance_hit": _field(inputs, "provenance_hit"),
        "generated_at": _now_iso(),
        "verification_run_id": f"{_slug(component_id)}-attempt-{attempts}",
        "verification_report": _to_jsonable(verification_report),
        "license_scan": _to_jsonable(_field(inputs, "license_scan_result")),
        "secret_scan": _to_jsonable(_field(inputs, "secret_scan_result")),
    }


def write_provenance(component_id, inputs, repo_root):
    """Write the manifest identically to gen/<slug>/ and verification/<slug>/."""
    manifest = build_manifest(inputs)
    text = json.dumps(manifest, indent=2) + "\n"
    slug = _slug(component_id)
    root = Path(repo_root)
    for base in ("gen", "verification"):
        target_dir = root / base / slug
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / ".provenance.json").write_text(text, encoding="utf-8")


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _invalid(message):
    raise InvalidSealedInputError(message)


def write_sealed_provenance(component_id, inputs, repo_root):
    """Write <repo_root>/<source_path>/.sealed-provenance.json after validating."""
    values = {name: _field(inputs, name) for name in _SEALED_INPUT_FIELDS}
    for name, value in values.items():
        if value is None:
            _invalid(f"missing sealed input: {name}")

    if component_id != values["component_id"]:
        _invalid("component_id does not match inputs.component_id")

    report = values["verification_report"]
    overall = _field(report, "overall")
    criteria = _field(report, "criteria")
    if not criteria:
        _invalid("verification_report has no criteria")
    passed = 0
    for entry in criteria:
        result = _field(entry, "result")
        if result not in ("pass", "fail", "skipped"):
            _invalid(f"invalid criterion result: {result!r}")
        if result == "pass":
            passed += 1
    total = len(criteria)
    if overall not in ("pass", "fail"):
        _invalid(f"invalid overall: {overall!r}")
    if overall == "pass" and passed != total:
        _invalid("overall pass requires every criterion to pass")

    if not _matches(_COMPONENT_ID_RE, values["component_id"]):
        _invalid("invalid component_id")
    owners = values["owners"]
    if not isinstance(owners, list) or not owners:
        _invalid("owners must be a non-empty list")
    for owner in owners:
        if not _matches(_OWNER_RE, owner):
            _invalid(f"invalid owner: {owner!r}")
    source_path = values["source_path"]
    if not _matches(_SOURCE_PATH_RE, source_path):
        _invalid("invalid source_path")
    if source_path.split("/")[0] == "gen":
        _invalid("source_path must not be under gen/")
    if not _matches(_SOURCE_HASH_RE, values["source_hash"]):
        _invalid("invalid source_hash")
    if not _matches(_VERIFIER_VERSION_RE, values["verifier_version"]):
        _invalid("invalid verifier_version")

    manifest = {
        "kind": _SEALED_KIND,
        "version": _SEALED_VERSION,
        "component_id": values["component_id"],
        "owners": owners,
        "source_path": source_path,
        "source_hash": values["source_hash"],
        "verifier_version": values["verifier_version"],
        "characterization": {
            "overall": overall,
            "criteria_passed": passed,
            "criteria_total": total,
        },
        "written_at": _now_iso(),
    }
    text = json.dumps(manifest, indent=2) + "\n"
    target_dir = Path(repo_root) / source_path
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / ".sealed-provenance.json").write_text(text, encoding="utf-8")


def main(argv):
    """hotdocs provenance write <component-id> [--repo-root=<dir>]"""
    if list(argv[:2]) != ["provenance", "write"]:
        return 2
    rest = list(argv[2:])
    positionals = []
    repo_root = "."
    i = 0
    while i < len(rest):
        token = rest[i]
        if token == "--repo-root":
            if i + 1 >= len(rest):
                return 2
            repo_root = rest[i + 1]
            i += 2
            continue
        if token.startswith("--repo-root="):
            repo_root = token[len("--repo-root="):]
        elif token.startswith("--"):
            return 2
        else:
            positionals.append(token)
        i += 1
    if len(positionals) != 1:
        return 2
    try:
        inputs = json.loads(sys.stdin.read())
    except ValueError:
        return 2
    try:
        write_provenance(positionals[0], inputs, Path(repo_root))
    except MissingInputError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
