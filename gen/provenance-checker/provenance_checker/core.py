"""Core (library) logic for the Provenance Checker.

Implements R-PROVCHECK-001 through R-PROVCHECK-004: a pure, read-only
function of the working tree's current state plus
`VAR-TRUST-JUDGE-PROVENANCE` — no network access, no model call, and
never a `cache-manager` client (see `constraints.md`).
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional, Union

_PROVENANCE_FILENAME = ".provenance.json"
_COMPONENT_ID_PREFIX = "comp-"

# No dependency-provided var-resolution mechanism is available to this
# component (see DEPENDENCY INTERFACES: {}), so VAR-TRUST-JUDGE-PROVENANCE
# is resolved from the environment directly, with the spec's documented
# "absent means true" default.
_ENV_VAR_TRUST_JUDGE_PROVENANCE = "VAR_TRUST_JUDGE_PROVENANCE"

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


@dataclasses.dataclass(frozen=True)
class ProvenanceCheckResult:
    """See `interface/data/ProvenanceCheckResult.md`.

    `verification_report`/`license_scan`/`secret_scan` are populated only
    when `hit` is True — always `None` on a miss, and always the matching
    manifest's own fields copied verbatim on a hit (R-PROVCHECK-002,
    R-PROVCHECK-003).
    """

    hit: bool
    verification_report: Optional[Mapping[str, Any]] = None
    license_scan: Optional[Mapping[str, Any]] = None
    secret_scan: Optional[Mapping[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "hit": self.hit,
            "verification_report": self.verification_report,
            "license_scan": self.license_scan,
            "secret_scan": self.secret_scan,
        }


def _component_slug(component_id: str) -> str:
    """Strip the leading `comp-` prefix, if present, to get the bare slug
    used everywhere a `gen/<slug>/`-shaped path is built from a component
    id — per `specs/glossary.md`'s "Component id / component slug" entry,
    which calls out a real prior `provenance-checker` candidate that got
    this wrong and silently treated every real hit as a miss.
    """
    if component_id.startswith(_COMPONENT_ID_PREFIX):
        return component_id[len(_COMPONENT_ID_PREFIX):]
    return component_id


def _provenance_path(component_id: str, repo_root: Union[str, Path]) -> Path:
    slug = _component_slug(component_id)
    return Path(repo_root) / "gen" / slug / _PROVENANCE_FILENAME


def _miss() -> ProvenanceCheckResult:
    return ProvenanceCheckResult(
        hit=False, verification_report=None, license_scan=None, secret_scan=None
    )


def _resolve_trust_judge_provenance(override: Optional[bool] = None) -> bool:
    """Resolve VAR-TRUST-JUDGE-PROVENANCE. Absent means True (`D1`'s cheap
    cold-regen default — a deliberate exception to this corpus's otherwise
    conservative absent-value defaults, per the var's own description).

    An explicit `override` (e.g. supplied by a caller that already
    resolved vars some other way) always wins over the environment.
    """
    if override is not None:
        return override
    raw = os.environ.get(_ENV_VAR_TRUST_JUDGE_PROVENANCE)
    if raw is None:
        return True
    normalized = raw.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    # Unrecognized value: fall back to the documented absent default
    # rather than guessing.
    return True


def _has_llm_judge_criterion(verification_report: Mapping[str, Any]) -> bool:
    criteria = verification_report.get("criteria")
    if not isinstance(criteria, list):
        return False
    for criterion in criteria:
        if isinstance(criterion, Mapping) and criterion.get("kind") == "llm-judge":
            return True
    return False


def _gate_versions_match(
    manifest_gate_versions: Any, current_gate_versions: Mapping[str, str]
) -> bool:
    """A hit requires every `gate_versions` entry to match exactly — gate
    version is part of the key, not metadata checked after
    (R-PROVCHECK-001, mirroring R-CACHE-005's rule for a different store).
    """
    if not isinstance(manifest_gate_versions, Mapping):
        return False
    if set(manifest_gate_versions.keys()) != set(current_gate_versions.keys()):
        return False
    for key, value in current_gate_versions.items():
        if manifest_gate_versions.get(key) != value:
            return False
    return True


def check_provenance(
    component_id: str,
    spec_bundle_hash: str,
    gate_versions: Mapping[str, str],
    repo_root: Union[str, Path],
    *,
    trust_judge_provenance: Optional[bool] = None,
) -> ProvenanceCheckResult:
    """Decide whether `gen/<component>/.provenance.json`, as it currently
    sits in the working tree, proves the given component was already
    verified against the exact supplied spec state.

    Pure function of the working tree's current state plus
    `VAR-TRUST-JUDGE-PROVENANCE` (R-PROVCHECK-001..004): no network
    access, no model call, never writes anything, and never consults
    `cache-manager`.

    `trust_judge_provenance`, if given, overrides the resolved value of
    `VAR-TRUST-JUDGE-PROVENANCE` (useful for callers that already resolve
    vars elsewhere); otherwise it is read from the environment with the
    documented "absent means true" default.
    """
    path = _provenance_path(component_id, repo_root)

    if not path.is_file():
        return _miss()

    try:
        with path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _miss()

    if not isinstance(manifest, Mapping):
        return _miss()

    if manifest.get("spec_bundle_hash") != spec_bundle_hash:
        return _miss()

    if not _gate_versions_match(manifest.get("gate_versions"), gate_versions):
        return _miss()

    verification_report = manifest.get("verification_report")
    license_scan = manifest.get("license_scan")
    secret_scan = manifest.get("secret_scan")

    if isinstance(verification_report, Mapping) and _has_llm_judge_criterion(
        verification_report
    ):
        if not _resolve_trust_judge_provenance(trust_judge_provenance):
            # R-PROVCHECK-002's exception applies: an llm-judge-kind
            # criterion is present and the var says not to trust a
            # feature-branch claim about it. R-PROVCHECK-003 makes this a
            # definitive miss, not a partial-credit result.
            return _miss()

    return ProvenanceCheckResult(
        hit=True,
        verification_report=verification_report,
        license_scan=license_scan,
        secret_scan=secret_scan,
    )