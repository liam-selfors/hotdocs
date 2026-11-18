"""Provenance writer: assembles and writes `.provenance.json` manifests and
sealed `.sealed-provenance.json` manifests from already-produced results."""

import dataclasses
import enum
import json
import math
import pathlib
import re
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_VERSION = "v1"


class MissingInputError(Exception):
    """A required upstream result was absent."""


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


def _get(obj, name):
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)


def to_json(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {
            (k if isinstance(k, str) else str(k)): to_json(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [to_json(v) for v in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, pathlib.PurePath):
        return str(value)
    if isinstance(value, enum.Enum):
        return to_json(value.value)
    if callable(getattr(value, "to_dict", None)):
        return to_json(value.to_dict())
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: to_json(getattr(value, f.name))
            for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            k: to_json(v)
            for k, v in vars(value).items()
            if not k.startswith("_") and not callable(v)
        }
    return repr(value)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(component_id):
    return component_id.removeprefix("comp-")


def build_manifest(inputs):
    generation_result = _get(inputs, "generation_result")
    verification_report = _get(inputs, "verification_report")
    license_scan_result = _get(inputs, "license_scan_result")
    secret_scan_result = _get(inputs, "secret_scan_result")
    provenance_hit = _get(inputs, "provenance_hit")
    attempts = _get(inputs, "attempts")
    gate_versions = _get(inputs, "gate_versions")

    if generation_result is None:
        raise MissingInputError("generation_result is missing")
    if license_scan_result is None:
        raise MissingInputError("license_scan_result is missing")
    if secret_scan_result is None:
        raise MissingInputError("secret_scan_result is missing")
    if verification_report is None and _get(generation_result, "files"):
        raise MissingInputError(
            "verification_report is missing for a non-empty candidate"
        )

    slug = _slug(_get(inputs, "component_id"))
    return {
        "spec_bundle_hash": to_json(_get(generation_result, "spec_bundle_hash")),
        "model_pin": to_json(_get(generation_result, "model")),
        "prompt_version": to_json(_get(generation_result, "prompt_version")),
        "retry_feedback": to_json(_get(generation_result, "retry_feedback")),
        "pipeline_version": PIPELINE_VERSION,
        "gate_versions": to_json(gate_versions),
        "provenance_hit": to_json(provenance_hit),
        "generated_at": _now(),
        "verification_run_id": f"{slug}-attempt-{attempts}",
        "verification_report": to_json(verification_report),
        "license_scan": to_json(license_scan_result),
        "secret_scan": to_json(secret_scan_result),
    }


def write_provenance(component_id, inputs, repo_root):
    manifest = build_manifest(inputs)
    text = json.dumps(manifest, indent=2) + "\n"
    slug = _slug(component_id)
    root = Path(repo_root)
    for base in ("gen", "verification"):
        target = root / base / slug / ".provenance.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


_COMPONENT_ID_RE = r"comp-[a-z0-9]+(-[a-z0-9]+)*"
_OWNER_RE = r"[a-z0-9]+(-[a-z0-9]+)*"
_SOURCE_PATH_RE = r"[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?"
_SOURCE_HASH_RE = r"sha256:[0-9a-f]{64}"
_VERIFIER_VERSION_RE = r"verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+"
_SEALED_FIELDS = (
    "component_id",
    "owners",
    "source_path",
    "source_hash",
    "verifier_version",
    "verification_report",
)


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _build_sealed_manifest(component_id, inputs):
    values = {name: _get(inputs, name) for name in _SEALED_FIELDS}
    for name, value in values.items():
        if value is None:
            raise InvalidSealedInputError(f"{name} is missing")
    if component_id != values["component_id"]:
        raise InvalidSealedInputError("component_id does not match inputs")

    report = to_json(values["verification_report"])
    if not isinstance(report, dict):
        raise InvalidSealedInputError("verification_report is not an object")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise InvalidSealedInputError("verification_report has no criteria")
    passed = 0
    for entry in criteria:
        result = _get(entry, "result")
        if result not in ("pass", "fail", "skipped"):
            raise InvalidSealedInputError("criterion result is invalid")
        if result == "pass":
            passed += 1
    overall = report.get("overall")
    if overall not in ("pass", "fail"):
        raise InvalidSealedInputError("verification_report overall is invalid")
    total = len(criteria)

    manifest = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": to_json(values["component_id"]),
        "owners": to_json(values["owners"]),
        "source_path": to_json(values["source_path"]),
        "source_hash": to_json(values["source_hash"]),
        "verifier_version": to_json(values["verifier_version"]),
        "characterization": {
            "overall": overall,
            "criteria_passed": passed,
            "criteria_total": total,
        },
        "written_at": _now(),
    }

    if not _matches(_COMPONENT_ID_RE, manifest["component_id"]):
        raise InvalidSealedInputError("component_id is invalid")
    owners = manifest["owners"]
    if not isinstance(owners, list) or not owners:
        raise InvalidSealedInputError("owners must be a non-empty list")
    for owner in owners:
        if not _matches(_OWNER_RE, owner):
            raise InvalidSealedInputError("owners entry is invalid")
    source_path = manifest["source_path"]
    if not _matches(_SOURCE_PATH_RE, source_path):
        raise InvalidSealedInputError("source_path is invalid")
    if source_path.split("/")[0] == "gen":
        raise InvalidSealedInputError("source_path may not be under gen/")
    if not _matches(_SOURCE_HASH_RE, manifest["source_hash"]):
        raise InvalidSealedInputError("source_hash is invalid")
    if not _matches(_VERIFIER_VERSION_RE, manifest["verifier_version"]):
        raise InvalidSealedInputError("verifier_version is invalid")
    if overall == "pass" and passed != total:
        raise InvalidSealedInputError("overall pass requires every criterion to pass")
    return manifest


def write_sealed_provenance(component_id, inputs, repo_root):
    manifest = _build_sealed_manifest(component_id, inputs)
    text = json.dumps(manifest, indent=2) + "\n"
    directory = Path(repo_root) / manifest["source_path"]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".sealed-provenance.json").write_text(text, encoding="utf-8")


def _usage(message):
    print(f"usage error: {message}", file=sys.stderr)
    return 2


def main(argv):
    argv = list(argv)
    if argv[:2] != ["provenance", "write"]:
        return _usage("expected 'provenance write <component-id>'")
    positionals = []
    repo_root = "."
    rest = argv[2:]
    i = 0
    while i < len(rest):
        token = rest[i]
        if token.startswith("--repo-root="):
            repo_root = token[len("--repo-root="):]
        elif token == "--repo-root":
            if i + 1 >= len(rest):
                return _usage("--repo-root requires a value")
            i += 1
            repo_root = rest[i]
        elif token.startswith("--"):
            return _usage(f"unrecognized flag {token}")
        else:
            positionals.append(token)
        i += 1
    if len(positionals) != 1:
        return _usage("expected exactly one <component-id>")
    try:
        inputs = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        return _usage(f"malformed JSON on stdin: {exc}")
    try:
        write_provenance(positionals[0], inputs, Path(repo_root))
    except MissingInputError as exc:
        print(f"missing input: {exc}", file=sys.stderr)
        return 1
    return 0
