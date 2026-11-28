"""Spec Reviewer: checks whether each acceptance criterion can be implemented
from what its test author sees, and whether it expects unstated behavior.

Advisory only: it never changes a file under ``specs/`` and writes proposals
under ``<repo_root>/.hotdocs/proposals/`` only when asked.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

GAP_KINDS = ("guess", "unstated_behavior")

FRAMEWORK_SENTENCE = (
    "The pipeline fixes the test framework (pytest), the test file's name and "
    "location, and how the test reaches the component's code: never report any "
    "of these as a gap."
)

USAGE = (
    "usage: hotdocs spec check <target>... [--model=<model>] [--write-proposals] "
    "[--strict] [--format=json|text] [--repo-root=<dir>]"
)

UNPARSEABLE_MESSAGE = "reply was not the JSON object asked for"

_TOKEN_RE = re.compile(r"`([^`]*)`")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclasses.dataclass(eq=False)
class ReviewReport(Mapping):
    targets: list = dataclasses.field(default_factory=list)
    criteria_checked: list = dataclasses.field(default_factory=list)
    findings: list = dataclasses.field(default_factory=list)
    gaps: list = dataclasses.field(default_factory=list)
    writable: dict = dataclasses.field(default_factory=dict)
    lint_findings: list = dataclasses.field(default_factory=list)
    proposals: list = dataclasses.field(default_factory=list)
    degraded: bool = False

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def to_dict(self) -> dict:
        return {
            "targets": list(self.targets),
            "criteria_checked": list(self.criteria_checked),
            "findings": [dict(f) for f in self.findings],
            "gaps": [dict(g) for g in self.gaps],
            "writable": dict(self.writable),
            "lint_findings": [dict(f) for f in self.lint_findings],
            "proposals": list(self.proposals),
            "degraded": self.degraded,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load(slug: str, module: str, repo_root):
    base = Path(repo_root) / "gen" / slug if repo_root is not None else None
    if base is None or not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / f"{module}.py"
    search = None
    if not path.is_file():
        path = base / module / "__init__.py"
        search = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(
        module, path, submodule_search_locations=search
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    spec.loader.exec_module(mod)
    return mod


def _json_object(text):
    if not isinstance(text, str):
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _finding(criterion_id, kind, token, message):
    return {
        "criterion_id": criterion_id,
        "kind": kind,
        "token": token,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Target resolution (R-REVIEW-001)
# ---------------------------------------------------------------------------


def _resolve_targets(targets, repo_root: Path):
    components_dir = repo_root / "specs" / "components"
    criteria: dict = {}
    slugs: set = set()
    for target in targets:
        slug = target[len("comp-"):]
        if target.startswith("comp-") and slug and (components_dir / slug).is_dir():
            slugs.add(slug)
            for path in sorted((components_dir / slug / "acceptance").glob("AC-*.md")):
                criteria[path.stem] = target
            continue
        matches = sorted(components_dir.glob(f"*/acceptance/{target}.md"))
        if not matches:
            raise ValueError(f"unknown target id: {target}")
        comp_slug = matches[0].parent.parent.name
        slugs.add(comp_slug)
        criteria[target] = f"comp-{comp_slug}"
    return criteria, sorted(slugs)


# ---------------------------------------------------------------------------
# Asset interface check (R-REVIEW-008)
# ---------------------------------------------------------------------------


def _assets(component_md: Path):
    if not component_md.is_file():
        return []
    lines = component_md.read_text(encoding="utf-8").splitlines()
    marks = [i for i, line in enumerate(lines) if line.strip() == "---"][:2]
    if len(marks) < 2:
        return []
    for line in lines[marks[0] + 1 : marks[1]]:
        if line.startswith("assets:"):
            start = line.find("[")
            if start == -1:
                return []
            inner = line[start + 1 :].split("]", 1)[0]
            assets = []
            for item in inner.split(","):
                item = item.strip()
                if ":" not in item:
                    continue
                kind, path = item.split(":", 1)
                assets.append((kind.strip(), path.strip()))
            return assets
    return []


def _asset_findings(slugs, repo_root: Path):
    findings = []
    for slug in slugs:
        comp_dir = repo_root / "specs" / "components" / slug
        for _kind, path in _assets(comp_dir / "component.md"):
            file_name = path.rsplit("/", 1)[-1]
            if not (comp_dir / "interface" / "assets" / f"{file_name}.md").exists():
                findings.append(
                    _finding(
                        f"comp-{slug}",
                        "asset_interface_missing",
                        path,
                        f"`{path}` has no interface file "
                        f"specs/components/{slug}/interface/assets/{file_name}.md",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Invisible references (R-REVIEW-003)
# ---------------------------------------------------------------------------


def _step_tokens(criterion_text: str):
    tokens = []
    in_block = False
    step = None
    for line in (criterion_text or "").splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```gherkin"):
                in_block = True
            continue
        if stripped.startswith("```"):
            break
        words = line.split()
        if words and words[0] in ("Given", "When", "Then"):
            step = words[0]
        if step not in ("When", "Then"):
            continue
        for match in _TOKEN_RE.finditer(line):
            token = match.group(1).strip()
            token = token.split("<", 1)[0]
            if token and token not in tokens:
                tokens.append(token)
    return tokens


def _visible_text(bundle) -> str:
    deps = _get(bundle, "dependency_interfaces") or {}
    return (
        (_get(bundle, "requirement_text") or "")
        + (_get(bundle, "interface") or "")
        + (_get(bundle, "glossary") or "")
        + "".join(str(v) for v in deps.values())
    )


# ---------------------------------------------------------------------------
# Model review (R-REVIEW-004)
# ---------------------------------------------------------------------------

_BUNDLE_FIELDS = (
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
    "testing",
)


def _review_prompt(bundle) -> str:
    criterion_id = _get(bundle, "criterion_id")
    parts = [
        f"You are the author of the executable test for acceptance criterion "
        f"{criterion_id}. Below is everything you will see when writing it.",
        "Say whether the test can be written from this alone. List each fact you "
        "would have to guess (kind \"guess\") and each behavior the criterion "
        "checks that no requirement or interface text states (kind "
        "\"unstated_behavior\"), with the spec text that would close the gap and "
        "the spec file it belongs in.",
        FRAMEWORK_SENTENCE,
        "Reply with exactly one JSON object:",
        '{"writable": <bool>, "gaps": [{"kind": "guess" | "unstated_behavior", '
        '"missing": "<text>", "proposed_text": "<text>", "target_file": "<path>"}]}',
    ]
    for name in _BUNDLE_FIELDS:
        value = _get(bundle, name)
        if name == "dependency_interfaces":
            value = "\n\n".join(
                f"### {dep}\n{text}" for dep, text in (value or {}).items()
            )
        parts.append(f"## {name}\n{value if value is not None else ''}")
    return "\n\n".join(parts)


def _review(complete, bundle, criterion_id, model, llm_backend):
    """Return (writable, gaps, finding_or_None)."""
    response = complete(_review_prompt(bundle), model, backend=llm_backend)
    error = _get(response, "model_call_error")
    if error:
        return None, [], _finding(
            criterion_id, "model_unparseable", "", _get(error, "message")
        )
    obj = _json_object(_get(response, "text"))
    if obj is None or not isinstance(obj.get("writable"), bool):
        return None, [], _finding(
            criterion_id, "model_unparseable", "", UNPARSEABLE_MESSAGE
        )
    gaps = []
    for gap in obj.get("gaps") or []:
        if isinstance(gap, dict) and gap.get("kind") in GAP_KINDS:
            gaps.append(
                {
                    "criterion_id": criterion_id,
                    "kind": gap.get("kind"),
                    "missing": gap.get("missing", ""),
                    "proposed_text": gap.get("proposed_text", ""),
                    "target_file": gap.get("target_file", ""),
                }
            )
    return obj["writable"], gaps, None


# ---------------------------------------------------------------------------
# Glossary judge (R-REVIEW-006)
# ---------------------------------------------------------------------------


def _make_judge(model, llm_backend, repo_root):
    complete = _load("llm-endpoint", "llm_endpoint", repo_root).complete

    def judge(term, local_text, glossary_text):
        prompt = "\n\n".join(
            [
                "Does the component's local definition of a term conflict with "
                "the glossary's definition of it?",
                f"Term: {term}",
                f"Local definition:\n{local_text}",
                f"Glossary definition:\n{glossary_text}",
                'Reply with exactly one JSON object: '
                '{"conflicts": <bool>, "rationale": "<text>"}',
            ]
        )
        response = complete(prompt, model, backend=llm_backend)
        if _get(response, "model_call_error"):
            return None
        obj = _json_object(_get(response, "text"))
        if (
            obj is None
            or not isinstance(obj.get("conflicts"), bool)
            or not isinstance(obj.get("rationale"), str)
        ):
            return None
        return (obj["conflicts"], obj["rationale"])

    return judge


def glossary_judge(model: str, llm_backend=None):
    return _make_judge(model, llm_backend, None)


# ---------------------------------------------------------------------------
# Lint findings
# ---------------------------------------------------------------------------

_FINDING_FIELDS = ("rule_id", "severity", "file", "line", "message", "rationale")


def _lint_finding_dict(finding) -> dict:
    return {name: _get(finding, name) for name in _FINDING_FIELDS}


# ---------------------------------------------------------------------------
# Proposals (R-REVIEW-005)
# ---------------------------------------------------------------------------


def _write_proposals(gaps, repo_root: Path):
    by_criterion: dict = {}
    for gap in gaps:
        by_criterion.setdefault(gap["criterion_id"], []).append(gap)
    written = []
    out_dir = repo_root / ".hotdocs" / "proposals"
    for criterion_id, items in by_criterion.items():
        out_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"# Proposals for {criterion_id}"]
        for gap in items:
            lines += [
                "",
                f"- kind: {gap['kind']}",
                f"  missing: {gap['missing']}",
                f"  target_file: {gap['target_file']}",
                f"  proposed_text: {gap['proposed_text']}",
            ]
        (out_dir / f"{criterion_id}.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        written.append(f".hotdocs/proposals/{criterion_id}.md")
    return written


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


def check(
    targets: list,
    repo_root: Path,
    model: str | None = None,
    *,
    llm_backend=None,
    write_proposals: bool = False,
) -> ReviewReport:
    repo_root = Path(repo_root)
    criteria, slugs = _resolve_targets(targets, repo_root)

    findings = _asset_findings(slugs, repo_root)

    linter = _load("spec-linter", "spec_linter", repo_root)
    judge = _make_judge(model, llm_backend, repo_root) if model else None
    lint_report = linter.lint(
        [repo_root / "specs" / "components" / slug for slug in slugs],
        repo_root,
        judge=judge,
    )
    lint_findings = [
        _lint_finding_dict(f) for f in (_get(lint_report, "findings") or [])
    ]
    report = ReviewReport(
        targets=list(targets),
        findings=findings,
        lint_findings=lint_findings,
        degraded=model is None,
    )
    if any(f["severity"] == "fail" for f in lint_findings):
        return report

    assembler = _load("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    complete = (
        _load("llm-endpoint", "llm_endpoint", repo_root).complete if model else None
    )

    for criterion_id in sorted(criteria):
        report.criteria_checked.append(criterion_id)
        report.writable[criterion_id] = None
        try:
            bundle = assembler.assemble_criterion(
                criteria[criterion_id], criterion_id, repo_root
            )
        except Exception as exc:  # R-REVIEW-009
            findings.append(
                _finding(
                    criterion_id,
                    "bundle_unavailable",
                    "",
                    f"{criterion_id}: its bundle cannot be built: {exc}",
                )
            )
            continue

        visible = _visible_text(bundle)
        for token in _step_tokens(_get(bundle, "criterion_text")):
            if token not in visible:
                findings.append(
                    _finding(
                        criterion_id,
                        "invisible_reference",
                        token,
                        f"`{token}` appears in {criterion_id} but not in what "
                        f"its test author sees",
                    )
                )

        if model:
            writable, gaps, finding = _review(
                complete, bundle, criterion_id, model, llm_backend
            )
            report.writable[criterion_id] = writable
            report.gaps.extend(gaps)
            if finding is not None:
                findings.append(finding)

    if write_proposals and report.gaps:
        report.proposals = _write_proposals(report.gaps, repo_root)
    return report


# ---------------------------------------------------------------------------
# CLI (R-REVIEW-007)
# ---------------------------------------------------------------------------


class _UsageError(Exception):
    pass


def _parse(argv):
    opts = {
        "model": None,
        "write_proposals": False,
        "strict": False,
        "format": "text",
        "repo_root": None,
    }
    targets = []
    valued = {"--model": "model", "--format": "format", "--repo-root": "repo_root"}
    i = 0
    while i < len(argv):
        token = argv[i]
        i += 1
        if not token.startswith("-"):
            targets.append(token)
            continue
        name, eq, value = token.partition("=")
        if name in valued:
            if not eq:
                if i >= len(argv):
                    raise _UsageError(f"{name} needs a value")
                value = argv[i]
                i += 1
            opts[valued[name]] = value
        elif token == "--write-proposals":
            opts["write_proposals"] = True
        elif token == "--strict":
            opts["strict"] = True
        else:
            raise _UsageError(f"unknown argument: {token}")
    if opts["format"] not in ("json", "text"):
        raise _UsageError(f"invalid --format value: {opts['format']}")
    if not targets:
        raise _UsageError("at least one <target> is required")
    return targets, opts


def _usage_error(cause) -> int:
    print(f"usage error: {cause}", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        targets, opts = _parse(list(argv))
    except _UsageError as exc:
        return _usage_error(exc)
    repo_root = Path(opts["repo_root"]) if opts["repo_root"] is not None else Path.cwd()
    try:
        report = check(
            targets,
            repo_root,
            opts["model"],
            write_proposals=opts["write_proposals"],
        )
    except ValueError as exc:
        return _usage_error(exc)

    if opts["format"] == "json":
        print(json.dumps(report.to_dict()))
    else:
        for f in report.findings:
            print(f"{f['criterion_id']}: {f['kind']}: {f['message']}")
        for g in report.gaps:
            print(f"{g['criterion_id']}: {g['kind']}: {g['missing']}")
            print(f"  propose: {g['proposed_text']} (in {g['target_file']})")
        print(
            f"{len(report.criteria_checked)} criteria checked, "
            f"{len(report.findings)} findings, {len(report.gaps)} gaps"
        )

    if any(f["severity"] == "fail" for f in report.lint_findings):
        return 1
    if any(f["kind"] == "bundle_unavailable" for f in report.findings):
        return 1
    if opts["strict"] and (report.findings or report.gaps):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
