"""
Capability Scenario Verifier (comp-capability-scenario-verifier)

SPEC SUMMARY (see SpecBundle for the authoritative text; this module only
implements it):

  - R-SCENARIO-001: given a blast-radius component-id set, determine every
    product capability (`P-id`) whose `realizes`-set intersects it, and run
    each one's capability scenarios (`### CS-<id>` sections embedded in that
    capability's own `specs/product/<name>.md`) against the real, fully
    assembled `gen/` output. Each scenario is dispatched by its declared
    `kind` using exactly the mechanisms already wired for
    verifier-orchestrator: `criterion-compiler` (`compile_criterion`) for
    `compiled`, an injected `test_author` callable for `generated-test`, an
    injected `judge` callable for `llm-judge`. No new dispatch machinery.

  - R-SCENARIO-002: the capability-intersection lookup is, conceptually,
    `SELECT DISTINCT target_id FROM edges WHERE edge_type = 'realizes' AND
    source_id IN (<blast-radius ids>)` against the `edges` view. This
    component does not depend on `comp-graph-query-engine`, so it builds the
    equivalent edge set locally by scanning every
    `specs/components/*/component.md` for its own `realizes:` frontmatter
    field (the edge is declared per-component, never per-capability — D77).

Everything below is this component's own implementation choices, made where
the spec bundle leaves a literal mechanical detail unstated (e.g. the exact
in-process call shape used to invoke the injected `judge`/`test_author`
callables, or the Markdown field-extraction regexes); those choices are
documented inline as such, not presented as spec text.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Type alias for the return value (see interface/data/CapabilityScenarioReport.md)
# ---------------------------------------------------------------------------

CapabilityScenarioReport = Dict[str, Dict[str, Any]]


# ---------------------------------------------------------------------------
# Dependency resolution: comp-criterion-compiler
#
# `criterion_compiler` is never injected (it is deterministic, model-free,
# and sealed — R-SCENARIO-001 mandates using it directly, not a new
# mechanism), so it is imported lazily, by repo-relative location, the same
# way any other component in this corpus resolves a sibling component's
# module when it isn't already importable from `sys.path`.
# ---------------------------------------------------------------------------

_CRITERION_COMPILER_MODULE = "criterion_compiler"
_CRITERION_COMPILER_CANDIDATE_DIRS = (
    "pipeline/criterion-compiler",
    "gen/criterion-compiler",
)


def _import_dependency(repo_root: Path, module_name: str, candidate_dirs) -> Any:
    """Import `module_name`, adding known repo-relative locations to
    `sys.path` if a plain import doesn't already succeed.

    If `module_name` is already present in `sys.modules` (e.g. a test has
    pre-registered a fake there), that is what `importlib.import_module`
    returns — this is the intended seam for mocking `criterion_compiler` in
    this component's own acceptance tests, since `compile_criterion` itself
    is not an injectable parameter of `run_capability_scenarios`.
    """
    try:
        return importlib.import_module(module_name)
    except ImportError:
        pass

    repo_root = Path(repo_root)
    for rel in candidate_dirs:
        candidate = repo_root / rel
        if not candidate.exists():
            continue
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
        try:
            return importlib.import_module(module_name)
        except ImportError:
            continue

    # Nothing worked; raise a clear ImportError rather than silently
    # degrading — a missing criterion-compiler is a located, real failure.
    return importlib.import_module(module_name)


def _get_criterion_compiler(repo_root: Path) -> Any:
    return _import_dependency(
        repo_root, _CRITERION_COMPILER_MODULE, _CRITERION_COMPILER_CANDIDATE_DIRS
    )


def _compile_criterion(criterion: Any, surface: Any, repo_root: Path) -> dict:
    cc = _get_criterion_compiler(repo_root)
    return cc.compile_criterion(criterion, surface=surface)


# ---------------------------------------------------------------------------
# `realizes` edge lookup (R-SCENARIO-002), built locally from
# `specs/components/*/component.md` frontmatter — no
# `comp-graph-query-engine` dependency available to this component.
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Minimal YAML-subset frontmatter parser: `key: value`, inline
    `key: [a, b]` lists, and block `key:` / `  - item` lists. Returns
    `(frontmatter_dict, body_text)`. If `text` has no `---`-delimited
    frontmatter, returns `({}, text)` unchanged.
    """
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1 :])

    data: dict = {}
    i = 0
    key_re = re.compile(r"^([A-Za-z0-9_\-]+):\s*(.*)$")
    item_re = re.compile(r"^\s*-\s+(.*)$")
    while i < len(fm_lines):
        raw = fm_lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        m = key_re.match(stripped)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            data[key] = items
            i += 1
        elif val == "":
            items = []
            j = i + 1
            while j < len(fm_lines) and item_re.match(fm_lines[j]):
                item = item_re.match(fm_lines[j]).group(1).strip().strip("\"'")
                items.append(item)
                j += 1
            data[key] = items if items else val
            i = j if items else i + 1
        else:
            data[key] = val.strip("\"'")
            i += 1
    return data, body


def _collect_realizes_edges(repo_root: Path) -> Dict[str, List[str]]:
    """component_id -> list of capability ids (`P-id`s) it `realizes`.

    Scans every `specs/components/*/component.md`'s own frontmatter for its
    `id:` and `realizes:` fields (D77: the edge is declared per-component,
    never per-capability).
    """
    edges: Dict[str, List[str]] = {}
    comp_dir = Path(repo_root) / "specs" / "components"
    if not comp_dir.is_dir():
        return edges
    for comp_md in sorted(comp_dir.glob("*/component.md")):
        try:
            text = comp_md.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, _ = _parse_frontmatter(text)
        cid = fm.get("id")
        if not cid:
            continue
        realizes = fm.get("realizes") or []
        if isinstance(realizes, str):
            realizes = [realizes]
        edges[cid] = list(realizes)
    return edges


def _capabilities_for_blast_radius(blast_radius: List[str], repo_root: Path) -> List[str]:
    """`SELECT DISTINCT target_id FROM edges WHERE edge_type = 'realizes'
    AND source_id IN (<blast_radius>)`, computed locally.
    """
    edges = _collect_realizes_edges(repo_root)
    targets: set = set()
    for component_id in blast_radius:
        for p_id in edges.get(component_id, []):
            targets.add(p_id)
    return sorted(targets)


# ---------------------------------------------------------------------------
# Locating and parsing a capability's own `### CS-<id>` scenario sections,
# embedded inside its `specs/product/<name>.md` file (R-SCENARIO-001, D75).
# ---------------------------------------------------------------------------

_CS_HEADING_RE = re.compile(r"(?m)^#{2,6}\s+(CS-[A-Za-z0-9_\-]+)\s*$")
_FENCE_RE = re.compile(r"```[a-zA-Z0-9_\-]*\s*\n(.*?)```", re.DOTALL)
_STEP_LINE_RE = re.compile(r"^\s*(Given|When|Then|And|But)\b")


def _file_declares_capability(text: str, frontmatter: dict, p_id: str) -> bool:
    if frontmatter.get("id") == p_id:
        return True
    # Fallback: some capability files may not carry a frontmatter `id:`
    # field; look for the P-id as a whole-word token near the top of the
    # file (e.g. in its title heading).
    head = text[:2000]
    return re.search(r"\b" + re.escape(p_id) + r"\b", head) is not None


def _find_capability_file(p_id: str, repo_root: Path) -> Optional[Path]:
    product_dir = Path(repo_root) / "specs" / "product"
    if not product_dir.is_dir():
        return None
    for md in sorted(product_dir.glob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, _ = _parse_frontmatter(text)
        if _file_declares_capability(text, fm, p_id):
            return md
    return None


def _extract_field(block: str, field: str) -> Optional[str]:
    pattern = r"(?im)^[\s>]*\**\s*{field}:?\**\s*(.+?)\s*$".format(field=re.escape(field))
    m = re.search(pattern, block)
    if not m:
        return None
    return m.group(1).strip().strip("`*_ ").strip()


def _extract_gherkin(block: str) -> str:
    m = _FENCE_RE.search(block)
    if m:
        return m.group(1).strip()
    lines = [l for l in block.splitlines() if _STEP_LINE_RE.match(l)]
    return "\n".join(l.strip() for l in lines).strip()


def _parse_capability_scenarios(md_path: Path) -> List[dict]:
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return []
    _, body = _parse_frontmatter(text)
    headings = list(_CS_HEADING_RE.finditer(body))
    scenarios: List[dict] = []
    for idx, m in enumerate(headings):
        cs_id = m.group(1)
        start = m.end()
        end = headings[idx + 1].start() if idx + 1 < len(headings) else len(body)
        block = body[start:end]
        covers = _extract_field(block, "Covers")
        kind = (_extract_field(block, "Kind") or "").lower()
        gherkin = _extract_gherkin(block)
        scenarios.append(
            {
                "id": cs_id,
                "covers": covers,
                "kind": kind,
                "gherkin": gherkin,
                "file": str(md_path),
            }
        )
    return scenarios


# ---------------------------------------------------------------------------
# Per-scenario dispatch, by declared `kind` (read-only; never reinterpreted
# here) — exactly the mechanisms verifier-orchestrator already uses.
# ---------------------------------------------------------------------------


def _bundle_for_scenario(scenario: dict, p_id: str) -> dict:
    """The context handed to an injected `test_author`/`judge` callable for
    one capability scenario. A capability scenario is black-box against the
    whole assembled system (R-SCENARIO-001) so there is no single
    component's own `CriterionBundle`-shaped `interface`/`component_id` to
    supply here; this dict carries the equivalent fields for a
    cross-component scenario instead.
    """
    return {
        "capability_id": p_id,
        "scenario_id": scenario["id"],
        "covers": scenario.get("covers"),
        "kind": scenario.get("kind"),
        "gherkin": scenario.get("gherkin"),
        "file": scenario.get("file"),
    }


def _dispatch_compiled(scenario: dict, repo_root: Path) -> dict:
    cc = _get_criterion_compiler(repo_root)
    parsed_criterion = cc.ParsedCriterion(
        criterion_id=scenario["id"],
        covers=scenario.get("covers") or "",
        kind="compiled",
        gherkin=scenario.get("gherkin") or "",
        file=scenario.get("file") or "",
    )
    # R-SCENARIO-001: use compile_criterion (never compile's directory
    # scanning), with surface=None — a capability scenario is black-box
    # against the whole assembled system, not bound to one component's own
    # interface contract.
    outcome = cc.compile_criterion(parsed_criterion, surface=None)
    status = outcome.get("status")
    result = "pass" if status == "compiled" else "fail"
    return {"id": scenario["id"], "kind": "compiled", "result": result}


def _dispatch_generated_test(
    scenario: dict, p_id: str, test_author_fn: Optional[Callable[[dict], Any]]
) -> dict:
    entry = {"id": scenario["id"], "kind": "generated-test"}
    if test_author_fn is None:
        # "a generated-test scenario with nothing cached and no test_author
        # configured reports fail" (interface/library.md).
        entry["result"] = "fail"
        return entry

    bundle = _bundle_for_scenario(scenario, p_id)
    outcome = test_author_fn(bundle)

    if isinstance(outcome, dict):
        model_call_error = outcome.get("model_call_error")
        file_info = outcome.get("file")
    else:
        model_call_error = getattr(outcome, "model_call_error", None)
        file_info = getattr(outcome, "file", None)

    if model_call_error:
        entry["result"] = "fail"
    elif file_info:
        entry["result"] = "pass"
    else:
        entry["result"] = "fail"
    return entry


def _dispatch_llm_judge(
    scenario: dict, p_id: str, judge_fn: Optional[Callable[[dict], Any]]
) -> dict:
    entry = {"id": scenario["id"], "kind": "llm-judge"}
    if judge_fn is None:
        # Omitted judge -> skipped, no rationale (nothing was dispatched).
        entry["result"] = "skipped"
        return entry

    bundle = _bundle_for_scenario(scenario, p_id)
    outcome = judge_fn(bundle)

    if isinstance(outcome, dict):
        result = outcome.get("result") or outcome.get("verdict")
        rationale = outcome.get("rationale", "")
    else:
        result = outcome
        rationale = ""

    entry["result"] = result
    # SPEC_GUIDELINES.md §5: an llm-judge criterion MUST emit structured
    # rationale alongside its verdict, whenever it actually dispatched.
    entry["rationale"] = rationale
    return entry


def _dispatch_scenario(
    scenario: dict,
    p_id: str,
    repo_root: Path,
    judge: Optional[Callable[[dict], Any]],
    test_author: Optional[Callable[[dict], Any]],
) -> dict:
    kind = scenario.get("kind")
    if kind == "compiled":
        return _dispatch_compiled(scenario, repo_root)
    if kind == "generated-test":
        return _dispatch_generated_test(scenario, p_id, test_author)
    if kind == "llm-judge":
        return _dispatch_llm_judge(scenario, p_id, judge)
    # `kind` is fixed at spec-authoring time; an unrecognized kind is a
    # located failure here, never silently skipped or reinterpreted.
    return {"id": scenario.get("id"), "kind": kind, "result": "fail"}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_capability_scenarios(
    blast_radius: List[str],
    repo_root: Path,
    judge: Optional[Callable[[dict], Any]] = None,
    test_author: Optional[Callable[[dict], Any]] = None,
) -> CapabilityScenarioReport:
    """Run every product capability's capability scenarios whose
    `realizes`-set intersects `blast_radius`, against the real, fully
    assembled `gen/` output at `repo_root`.

    `judge`/`test_author` are the same injectable-callable pattern
    `verifier-orchestrator`'s own `verify()` uses. Omitting either degrades
    the same way: an `llm-judge` scenario reports `skipped`; a
    `generated-test` scenario with no `test_author` configured reports
    `fail`.

    Returns a `CapabilityScenarioReport` keyed by `P-id`
    (interface/data/CapabilityScenarioReport.md) — a distinct namespace
    from any single component's own `VerificationReport`.
    """
    repo_root = Path(repo_root)
    report: CapabilityScenarioReport = {}

    p_ids = _capabilities_for_blast_radius(blast_radius, repo_root)

    for p_id in p_ids:
        capability_file = _find_capability_file(p_id, repo_root)
        parsed_scenarios = (
            _parse_capability_scenarios(capability_file) if capability_file else []
        )

        scenario_entries: List[dict] = []
        for scenario in parsed_scenarios:
            entry = _dispatch_scenario(scenario, p_id, repo_root, judge, test_author)
            scenario_entries.append(entry)

        results = [entry.get("result") for entry in scenario_entries]
        if "fail" in results:
            overall = "fail"
        elif results and all(r == "skipped" for r in results):
            overall = "skipped"
        else:
            overall = "pass"

        report[p_id] = {"overall": overall, "scenarios": scenario_entries}

    return report